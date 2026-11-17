import html
import logging
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

import httpx
import redis
import streamlit as st
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry
from streamlit.errors import StreamlitSecretNotFoundError

from flora.auth import AccessDenied, SupabaseAuth
from flora.inaturalist import (
    HERO_PHOTO, PREVIEW_PLANTS, SPECIES_LIMIT, Species, fetch_species_photo, search_species,
)
from flora.products import (
    CATEGORIES,
    format_brl,
    image_url,
    normalize_search,
    order_message,
    order_total,
    parse_price,
    whatsapp_link,
)
from flora.settings import load_settings
from flora.storage import Products, RecentProducts


LOGGER = logging.getLogger(__name__)
CSS_PATH = Path(__file__).with_name("style.css")
CATALOG = "Catálogo"
CART = "Carrinho"
ADMIN = "Administração"
CLIENT_ACCESS = "client"
ADMIN_LOGIN = "admin_login"
PRODUCT_INPUTS = ("name", "description", "scientific_name", "category", "price", "image_url")


@st.cache_resource
def mongo_client(uri):
    return MongoClient(uri, serverSelectionTimeoutMS=5000, timeoutMS=6000)


@st.cache_resource
def redis_client(url):
    return redis.Redis.from_url(
        url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2,
    )


@st.cache_resource
def admin_redis_client(url):
    return redis.Redis.from_url(
        url, decode_responses=True, socket_connect_timeout=0.7, socket_timeout=0.7,
        retry=Retry(NoBackoff(), 0),
    )


def admin_auth(settings):
    cache = None
    if settings.redis_url:
        try:
            cache = admin_redis_client(settings.redis_url)
        except (RedisError, ValueError) as error:
            log_failure("Conexão do cache de sessões", error)
    return SupabaseAuth(settings.supabase_url, settings.supabase_key, cache=cache)


def log_failure(operation, error):
    code = f", código {error.code}" if isinstance(error, OperationFailure) and error.code is not None else ""
    LOGGER.warning("%s falhou (%s%s)", operation, type(error).__name__, code)


def read_products(settings):
    if not settings.mongodb_uri:
        st.info("O catálogo estará disponível quando a conexão com o MongoDB for configurada.")
        return None
    try:
        return product_store(settings).list()
    except (PyMongoError, ValueError) as error:
        log_failure("Listagem do MongoDB", error)
        st.error("Não foi possível carregar o catálogo. Tente novamente em instantes.")
        return None


def product_store(settings):
    return Products(mongo_client(settings.mongodb_uri)[settings.mongodb_database].products)


def recent_store(settings):
    return RecentProducts(redis_client(settings.redis_url), st.session_state.visitor_id)


def adjust_cart(product_id, change, settings):
    cart = st.session_state.cart
    quantity = cart.get(product_id, 0) + change
    if quantity <= 0:
        cart.pop(product_id, None)
    else:
        cart[product_id] = quantity

    if change > 0 and settings.redis_url:
        try:
            recent_store(settings).record(product_id)
        except (RedisError, ValueError) as error:
            log_failure("Registro no Redis", error)


def show_brand():
    st.html("""
        <div class="flora-brand">
            <span class="brand-icon material-symbols-rounded" aria-hidden="true">potted_plant</span>
            <span>FloraStore</span>
        </div>
    """)


def leave_access(settings):
    st.session_state.pop("access_mode", None)
    session = st.session_state.pop("admin_session", None)
    if session:
        st.session_state.reset_product_form = True
        st.session_state.pop("product_notice", None)
        auth = admin_auth(settings)
        try:
            auth.sign_out(session)
        except httpx.HTTPError as error:
            log_failure("Logout no Supabase", error)


def navigation(settings, is_admin):
    brand, menu, action = st.columns([2, 3, 1.3], vertical_alignment="center")
    with brand:
        show_brand()
    pages = [ADMIN, CATALOG, CART] if is_admin else [CATALOG, CART]
    with menu:
        count = sum(st.session_state.cart.values())
        page = st.segmented_control(
            "Navegação", pages, default=pages[0], key="admin_page" if is_admin else "customer_page",
            label_visibility="collapsed", selection_mode="single",
            format_func=lambda option: f"Carrinho ({count})" if option == CART and count else option,
        )
    with action:
        st.button(
            "Sair" if is_admin else "Trocar acesso", on_click=leave_access, args=(settings,),
            icon=":material/logout:" if is_admin else ":material/swap_horiz:", width="stretch",
        )
    return page or pages[0]


def hero():
    photo = HERO_PHOTO
    st.html(f"""
        <section class="flora-hero" aria-labelledby="hero-title">
            <div class="hero-copy">
                <h1 id="hero-title">Mais verde<br><em>em casa.</em></h1>
                <p>Escolha suas plantas favoritas e faça seu pedido pelo WhatsApp.</p>
                <a class="hero-cta" href="#catalogo">Explorar plantas <span aria-hidden="true">↓</span></a>
            </div>
            <figure>
                <img src="{photo.url}" alt="Folhas de uma costela-de-adão" referrerpolicy="no-referrer">
                <figcaption><a href="{photo.source_url}" target="_blank" rel="noopener noreferrer">
                    {photo.attribution} · {photo.license}</a></figcaption>
            </figure>
        </section>
    """)


def plant_image(name, custom_image, photo, category=""):
    photo_url = photo.url if photo else custom_image
    if photo_url:
        image = (
            f'<img src="{html.escape(photo_url, quote=True)}" alt="{html.escape(name, quote=True)}" '
            'loading="lazy" referrerpolicy="no-referrer">'
        )
    else:
        image = """
          <div class="product-image-placeholder">
            <span class="material-symbols-rounded" aria-hidden="true">potted_plant</span>
            <span>Não há foto disponível</span>
          </div>
        """

    category_tag = f'<span class="category">{html.escape(category)}</span>' if category else ""
    credit = ""
    if photo:
        attribution = html.escape(photo.attribution or "iNaturalist")
        source = html.escape(photo.source_url, quote=True)
        credit = (
            f'<a href="{source}" target="_blank" rel="noopener noreferrer">'
            f'{attribution} · {html.escape(photo.license)}</a>'
        )
    return f'<div class="product-image">{image}{category_tag}{credit}</div>'


def product_markup(product):
    description = (
        f'<p class="description">{html.escape(product.description)}</p>'
        if product.description else ""
    )
    return f"""
        <article class="product-card">
          {plant_image(product.name, product.image_url, product.photo, product.category)}
          <h3>{html.escape(product.name)}</h3>
          <p class="species">{html.escape(product.scientific_name)}</p>
          {description}
          <p class="product-price">{format_brl(product.price_cents)}</p>
        </article>
    """


def show_recent(settings, products):
    if not settings.redis_url:
        return
    try:
        recent_ids = recent_store(settings).list()
    except (RedisError, ValueError) as error:
        log_failure("Leitura do Redis", error)
        st.caption("Os produtos recentes estão temporariamente indisponíveis.")
        return

    by_id = {product.id: product for product in products}
    recent = [by_id[product_id] for product_id in recent_ids if product_id in by_id]
    if recent:
        st.subheader("Selecionados recentemente")
        for product in recent:
            st.text(f"{product.name} · {format_brl(product.price_cents)}")


@st.fragment(run_every="5s")
def show_catalog(settings):
    st.header("Catálogo de plantas", anchor="catalogo")
    products = read_products(settings)
    if not products:
        if products is not None:
            st.info("Ainda não há plantas disponíveis para compra.")
        show_catalog_examples()
        return

    search_col, category_col = st.columns([2, 1])
    with search_col:
        query = st.text_input(
            "Buscar plantas", type="search", live="400ms",
            placeholder="Nome comum ou científico",
        )
    with category_col:
        category = st.selectbox("Categoria", ("Todas", *CATEGORIES))

    search_terms = normalize_search(query).split()
    visible_products = [
        product for product in products
        if (category == "Todas" or product.category == category) and product.matches_search(search_terms)
    ]
    count = len(visible_products)
    st.caption(f"{count} {'planta encontrada' if count == 1 else 'plantas encontradas'}")
    if not visible_products:
        st.info("Nenhuma planta corresponde a essa busca.")

    for start in range(0, count, 3):
        columns = st.columns(3, gap="medium")
        for column, product in zip(columns, visible_products[start:start + 3]):
            with column, st.container(key=f"product_{product.id}", border=True):
                st.html(product_markup(product))
                if st.button(
                    "Adicionar ao carrinho", key=f"add_{product.id}",
                    icon=":material/add_shopping_cart:", width="stretch",
                ):
                    adjust_cart(product.id, 1, settings)
                    st.toast(f"{product.name} entrou no carrinho.")
                    st.rerun()

    show_recent(settings, products)


def show_cart(settings):
    st.header("Seu carrinho")
    cart = st.session_state.cart
    if not cart:
        st.info("Seu carrinho está vazio. Escolha uma planta no catálogo.")
        return

    products = read_products(settings)
    if products is None:
        return
    by_id = {product.id: product for product in products}
    unavailable = cart.keys() - by_id.keys()
    if unavailable:
        for product_id in unavailable:
            del cart[product_id]
        st.warning("Algumas plantas ficaram indisponíveis e foram removidas do carrinho.")

    items = [(by_id[product_id], quantity) for product_id, quantity in cart.items()]
    if not items:
        return

    cart_column, checkout_column = st.columns([2, 1], gap="large")
    with cart_column:
        for product, quantity in items:
            with st.container(border=True):
                st.text(product.name)
                st.caption(f"{quantity} × {format_brl(product.price_cents)} · {format_brl(quantity * product.price_cents)}")
                less, more, remove = st.columns([1, 1, 2])
                with less:
                    st.button(
                        "−", key=f"less_{product.id}", help=f"Diminuir quantidade de {product.name}",
                        on_click=adjust_cart, args=(product.id, -1, settings), width="stretch",
                    )
                with more:
                    st.button(
                        "+", key=f"more_{product.id}", help=f"Aumentar quantidade de {product.name}",
                        on_click=adjust_cart, args=(product.id, 1, settings), width="stretch",
                    )
                with remove:
                    st.button(
                        "Remover", key=f"remove_{product.id}", help=f"Remover {product.name}",
                        on_click=adjust_cart, args=(product.id, -quantity, settings), width="stretch",
                    )

    with checkout_column, st.container(border=True):
        st.subheader("Resumo do pedido")
        st.metric("Total", format_brl(order_total(items)))
        message = order_message(items)
        with st.expander("Prévia da mensagem"):
            st.text(message)
        destination = whatsapp_link(settings.whatsapp_number, message)
        if destination:
            st.link_button(
                "Comprar pelo WhatsApp", destination, type="primary", width="stretch",
                icon=":material/chat:",
            )
        else:
            st.warning("O WhatsApp da loja precisa ser configurado para finalizar o pedido.")


def show_login(settings):
    st.header("Acesso administrativo")
    if notice := st.session_state.pop("auth_notice", None):
        st.info(notice)
    if not settings.supabase_url or not settings.supabase_key:
        st.info("Configure o Supabase para acessar o painel.")
        return

    with st.form("admin_login", clear_on_submit=True, border=False):
        email = st.text_input("E-mail", autocomplete="username", max_chars=254)
        password = st.text_input("Senha", type="password", autocomplete="current-password")
        if not st.form_submit_button("Entrar", type="primary", width="stretch"):
            return
    if not email.strip() or not password:
        st.warning("Preencha o e-mail e a senha.")
        return
    auth = admin_auth(settings)
    try:
        st.session_state.admin_session = auth.sign_in(email.strip(), password)
    except AccessDenied as error:
        st.error(str(error))
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        log_failure("Login no Supabase", error)
        st.error("O serviço de login está indisponível. Tente novamente em instantes.")
    else:
        st.rerun()


def choose_access(mode):
    st.session_state.access_mode = mode


def show_catalog_examples():
    with st.container(key="catalog_examples"):
        st.subheader("Exemplos de plantas")
        for column, (name, scientific_name, photo) in zip(st.columns(len(PREVIEW_PLANTS)), PREVIEW_PLANTS):
            with column, st.container(border=True):
                st.html(f"""
                    <article class="product-card">
                        {plant_image(name, "", photo)}
                        <h3>{html.escape(name)}</h3>
                        <p class="species">{html.escape(scientific_name)}</p>
                    </article>
                """)


def show_access(settings):
    with st.container(key="access_panel", border=True):
        show_brand()
        if st.session_state.get("access_mode") == ADMIN_LOGIN:
            show_login(settings)
            st.button(
                "Voltar", icon=":material/arrow_back:", on_click=choose_access,
                args=(None,), width="stretch",
            )
        else:
            st.header("Escolha como entrar")
            st.button(
                "Entrar como cliente", type="primary", icon=":material/shopping_bag:",
                on_click=choose_access, args=(CLIENT_ACCESS,), width="stretch",
            )
            st.button(
                "Entrar como administrador", icon=":material/admin_panel_settings:",
                on_click=choose_access, args=(ADMIN_LOGIN,), width="stretch",
            )


def lookup_species(settings, query):
    terms = normalize_search(query).split()
    matches = {}
    try:
        for product in product_store(settings).list():
            if product.inaturalist_taxon_id and product.scientific_name and product.matches_search(terms):
                species = Species(product.inaturalist_taxon_id, product.scientific_name, product.photo, product.name)
                matches.setdefault(species.id, species)
    except (PyMongoError, ValueError) as error:
        log_failure("Busca de espécies no catálogo", error)

    try:
        for species in search_species(query):
            matches.setdefault(species.id, species)
    except (httpx.HTTPError, ValueError, KeyError) as error:
        log_failure("Busca no iNaturalist", error)
        st.warning("O iNaturalist está indisponível. Você pode seguir com o cadastro manual.")
        if not matches:
            return None
    return list(matches.values())[:SPECIES_LIMIT]


def plant_lookup(settings):
    with st.expander("Buscar espécie no iNaturalist"):
        with st.form("lookup_species"):
            query = st.text_input(
                "Nome comum ou científico", placeholder="Ex. jiboia ou Epipremnum aureum", max_chars=180,
            )
            search = st.form_submit_button("Buscar espécie", icon=":material/search:")
        if search:
            st.session_state.pop("species_choice", None)
            st.session_state.species_matches = []
            if normalize_search(query):
                matches = lookup_species(settings, " ".join(query.split()))
                st.session_state.species_matches = matches or []
                if matches == []:
                    st.info("Nenhuma espécie encontrada. Tente outro nome comum ou científico.")
            else:
                st.info("Digite um nome comum ou científico para buscar.")

        if matches := st.session_state.get("species_matches"):
            choice = st.selectbox("Espécies encontradas", matches, format_func=lambda species: species.label,
                                  key="species_choice")
            if st.button("Usar espécie", icon=":material/check:"):
                if not choice.photo:
                    try:
                        choice = replace(choice, photo=fetch_species_photo(choice.id))
                    except (httpx.HTTPError, ValueError, KeyError) as error:
                        log_failure("Consulta de foto no iNaturalist", error)
                st.session_state.selected_species = choice
                st.session_state.product_name = choice.common_name or choice.scientific_name
                st.session_state.product_scientific_name = choice.scientific_name

        if plant := st.session_state.get("selected_species"):
            st.text(plant.label)
            if plant.photo:
                st.html(product_markup_preview(plant.photo.url, plant.scientific_name))
                st.link_button(f"Créditos da foto · {plant.photo.license}", plant.photo.source_url)
            else:
                st.caption("A consulta não encontrou uma foto com licença compatível.")


def product_markup_preview(url, name):
    return (
        f'<img class="lookup-image" src="{html.escape(url, quote=True)}" '
        f'alt="{html.escape(name, quote=True)}" referrerpolicy="no-referrer">'
    )


def product_form(settings, auth, session):
    if notice := st.session_state.pop("product_notice", None):
        st.success(notice)
    if not settings.mongodb_uri:
        st.info("Configure o MongoDB para cadastrar produtos.")
        return

    st.subheader("Cadastrar planta")
    plant_lookup(settings)
    with st.form("new_product", border=True):
        left, right = st.columns(2)
        with left:
            name = st.text_input("Nome da planta *", key="product_name", max_chars=100)
            scientific_name = st.text_input("Nome científico", key="product_scientific_name", max_chars=180)
        with right:
            category = st.selectbox("Categoria *", CATEGORIES, key="product_category")
            price = st.text_input("Preço em reais *", key="product_price", placeholder="49,90", max_chars=10)
        description = st.text_area("Descrição (opcional)", key="product_description", max_chars=500)
        custom_image = st.text_input("URL HTTPS da imagem", key="product_image_url", max_chars=2048,
                                    help="Se estiver vazia, usa a foto do iNaturalist quando disponível.")
        if not st.form_submit_button("Publicar no catálogo", type="primary", icon=":material/add:"):
            return

    name, scientific_name, description = name.strip(), scientific_name.strip(), description.strip()
    try:
        if not name:
            raise ValueError("Preencha o nome da planta.")
        price_cents = parse_price(price)
        custom_image = image_url(custom_image)
    except ValueError as error:
        st.warning(str(error))
        return

    admin = auth.require_admin(session, fresh=True)
    fields = {
        "name": name, "scientific_name": scientific_name, "category": category,
        "description": description, "price_cents": price_cents, "image_url": custom_image,
        "created_by": admin.id,
    }
    plant = st.session_state.get("selected_species")
    if plant and normalize_search(plant.scientific_name) == normalize_search(scientific_name):
        fields["source"] = {"provider": "iNaturalist", "taxon_id": plant.id}
        if plant.photo and not custom_image:
            fields["photo"] = asdict(plant.photo)

    if "product_id" not in st.session_state:
        st.session_state.product_id = uuid4().hex
    try:
        product_store(settings).save(st.session_state.product_id, fields)
    except (PyMongoError, ValueError) as error:
        log_failure("Cadastro no MongoDB", error)
        st.error("Não foi possível confirmar o cadastro. Tente publicar novamente.")
    else:
        st.session_state.product_notice = "Planta publicada. O catálogo já pode exibi-la."
        st.session_state.reset_product_form = True
        st.rerun()


def show_admin(settings):
    auth = admin_auth(settings)
    session = st.session_state.admin_session
    try:
        admin = auth.require_admin(session)
        st.header("Painel administrativo")
        st.caption(admin.email)
        product_form(settings, auth, session)
    except AccessDenied as error:
        st.session_state.pop("admin_session", None)
        st.session_state.access_mode = ADMIN_LOGIN
        st.session_state.auth_notice = str(error)
        st.session_state.reset_product_form = True
        st.session_state.pop("product_notice", None)
        st.rerun()
    except (httpx.HTTPError, ValueError, KeyError) as error:
        log_failure("Validação de acesso no Supabase", error)
        st.error("Não foi possível verificar sua sessão. Tente novamente em instantes.")


def main():
    st.set_page_config(
        page_title="FloraStore · Catálogo de plantas",
        page_icon=":material/potted_plant:",
        layout="wide",
    )
    st.html(CSS_PATH)
    try:
        try:
            secrets = st.secrets.to_dict()
        except StreamlitSecretNotFoundError:
            secrets = None
        settings = load_settings(secrets)
    except (OSError, ValueError) as error:
        log_failure("Leitura da configuração", error)
        st.error("Revise o formato de configuração dos serviços.")
        return

    if "cart" not in st.session_state:
        st.session_state.cart = {}
        st.session_state.visitor_id = uuid4().hex
    if st.session_state.pop("reset_product_form", False):
        for field in PRODUCT_INPUTS:
            st.session_state.pop(f"product_{field}", None)
        st.session_state.pop("selected_species", None)
        st.session_state.pop("species_matches", None)
        st.session_state.pop("species_choice", None)
        st.session_state.pop("product_id", None)

    is_admin = bool(st.session_state.get("admin_session"))
    if not is_admin and st.session_state.get("access_mode") != CLIENT_ACCESS:
        show_access(settings)
        return

    page = navigation(settings, is_admin)
    if page == ADMIN:
        show_admin(settings)
    elif page == CART:
        show_cart(settings)
    else:
        hero()
        show_catalog(settings)


if __name__ == "__main__":
    main()
