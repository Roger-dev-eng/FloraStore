import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote, urlencode, urlsplit


CATEGORIES = ("Folhagens", "Pendentes", "Suculentas", "Floração")


@dataclass(frozen=True)
class Photo:
    url: str
    attribution: str
    source_url: str
    license: str


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    category: str
    description: str
    price_cents: int
    image_url: str = ""
    scientific_name: str = ""
    photo: Photo | None = None

    @classmethod
    def from_document(cls, document):
        return cls(
            id=str(document["_id"]),
            name=document["name"],
            category=document["category"],
            description=document["description"],
            price_cents=document["price_cents"],
            image_url=document.get("image_url", ""),
            scientific_name=document.get("scientific_name", ""),
            photo=Photo(**document["photo"]) if document.get("photo") else None,
        )


def normalize_search(text):
    return "".join(
        char for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


def parse_price(raw):
    value = raw.strip()
    if not re.fullmatch(r"[0-9]{1,6}(?:[,.][0-9]{1,2})?", value):
        raise ValueError("Informe um preço como 49,90, sem separador de milhares.")

    cents = int(Decimal(value.replace(",", ".")) * 100)
    if cents < 1:
        raise ValueError("Informe um preço maior que zero.")
    return cents


def image_url(raw):
    value = raw.strip()
    if value:
        try:
            parsed = urlsplit(value)
            if parsed.scheme == "https" and parsed.hostname and not parsed.username:
                if not any(char.isspace() or ord(char) < 32 for char in value):
                    return value
        except ValueError:
            pass
        raise ValueError("Use uma URL HTTPS válida para a imagem.")
    return ""


def format_brl(cents):
    reais, fraction = divmod(cents, 100)
    grouped_reais = f"{reais:,}".replace(",", ".")
    return f"R$ {grouped_reais},{fraction:02d}"


def order_total(items):
    return sum(product.price_cents * quantity for product, quantity in items)


def order_message(items):
    lines = ["Olá! Gostaria de fazer um pedido na FloraStore:", ""]
    lines.extend(
        f"{quantity}x {product.name} — {format_brl(product.price_cents * quantity)}"
        for product, quantity in items
    )
    lines.extend(("", f"Total: {format_brl(order_total(items))}"))
    return "\n".join(lines)


def whatsapp_link(number, message):
    if not re.fullmatch(r"[+() 0-9-]+", number):
        return None
    digits = re.sub(r"[^0-9]", "", number)
    if not re.fullmatch(r"[1-9][0-9]{7,14}", digits):
        return None
    query = urlencode({"text": message}, quote_via=quote)
    return f"https://wa.me/{digits}?{query}"
