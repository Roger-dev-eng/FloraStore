from dataclasses import asdict

from pymongo import MongoClient

from flora.inaturalist import find_species
from flora.settings import load_settings
from flora.storage import Products


STARTER_PRODUCTS = (
    ("Monstera deliciosa", "Costela-de-adão", "Folhagens", 7990,
     "Folhas largas e recortadas para dar volume a um canto iluminado."),
    ("Zamioculcas zamiifolia", "Zamioculca", "Folhagens", 5990,
     "Hastes firmes com folhas brilhantes, uma opção para ambientes internos."),
    ("Epipremnum aureum", "Jiboia", "Pendentes", 4490,
     "Ramos pendentes e folhas em forma de coração para prateleiras e vasos suspensos."),
    ("Crassula ovata", "Planta-jade", "Suculentas", 3590,
     "Suculenta de folhas carnosas e arredondadas, ideal para um lugar claro."),
    ("Chlorophytum comosum", "Clorofito", "Pendentes", 3290,
     "Folhas finas e arqueadas que formam uma cascata verde."),
    ("Anthurium andraeanum", "Antúrio", "Floração", 6990,
     "Folhas verdes brilhantes e inflorescências que dão cor ao ambiente."),
    ("Aloe vera", "Babosa", "Suculentas", 3990,
     "Roseta de folhas grossas e alongadas, com pequenas serrilhas nas bordas."),
    ("Sansevieria trifasciata", "Espada-de-são-jorge", "Folhagens", 5490,
     "Folhas retas e firmes com faixas verdes, que crescem na vertical."),
    ("Spathiphyllum wallisii", "Lírio-da-paz", "Floração", 6490,
     "Folhas verdes brilhantes e inflorescências envolvidas por uma bráctea branca."),
    ("Ficus elastica", "Ficus-borracha", "Folhagens", 8490,
     "Folhas grandes, brilhantes e firmes com formato oval."),
    ("Ficus lyrata", "Figueira-lira", "Folhagens", 11990,
     "Folhas largas em formato de lira, com nervuras bem marcadas."),
    ("Ficus benjamina", "Figueira-benjamim", "Folhagens", 9490,
     "Ramos arqueados e folhas pequenas que formam uma copa leve."),
    ("Codiaeum variegatum", "Cróton", "Folhagens", 6490,
     "Folhagem que pode combinar tons amarelos, verdes, laranja e vermelhos."),
    ("Dieffenbachia seguine", "Comigo-ninguém-pode", "Folhagens", 5590,
     "Folhas alongadas com manchas claras que se destacam sobre o verde."),
    ("Aglaonema commutatum", "Aglaonema", "Folhagens", 6290,
     "Folhas lanceoladas que podem apresentar marcas prateadas."),
    ("Maranta leuconeura", "Maranta", "Folhagens", 5990,
     "Folhas ovais com desenhos e nervuras coloridas."),
    ("Goeppertia orbifolia", "Calatéia-orbifólia", "Folhagens", 8990,
     "Folhas arredondadas com faixas largas em diferentes tons de verde."),
    ("Peperomia obtusifolia", "Peperômia", "Folhagens", 4290,
     "Planta compacta de folhas espessas, lisas e arredondadas."),
    ("Pilea peperomioides", "Planta-chinesa-do-dinheiro", "Folhagens", 5490,
     "Folhas circulares que crescem no alto de hastes delicadas."),
    ("Syngonium podophyllum", "Singônio", "Folhagens", 4490,
     "Folhas jovens em formato de seta em uma planta de crescimento trepador."),
    ("Tradescantia zebrina", "Lambari-roxo", "Pendentes", 3490,
     "Ramos pendentes com listras prateadas e folhas de verso arroxeado."),
    ("Callisia repens", "Dinheiro-em-penca", "Pendentes", 3290,
     "Ramos finos com folhas pequenas que se espalham pela borda do vaso."),
    ("Begonia maculata", "Begônia-maculata", "Folhagens", 7490,
     "Folhas assimétricas cobertas de pequenas pintas prateadas."),
    ("Rhipsalis baccifera", "Cacto-macarrão", "Pendentes", 4990,
     "Cacto de caules finos e pendentes que crescem em cascata."),
    ("Schlumbergera truncata", "Flor-de-maio", "Floração", 4590,
     "Cacto de segmentos achatados que pode produzir flores nas pontas dos ramos."),
    ("Kalanchoe blossfeldiana", "Flor-da-fortuna", "Floração", 3490,
     "Suculenta compacta que floresce em cachos de flores pequenas."),
    ("Echeveria elegans", "Rosa-de-pedra", "Suculentas", 2990,
     "Roseta compacta com folhas carnudas em tom verde-acinzentado."),
    ("Haworthiopsis attenuata", "Suculenta-zebra", "Suculentas", 3290,
     "Folhas firmes e pontudas com pequenas marcas brancas transversais."),
    ("Nephrolepis exaltata", "Samambaia", "Pendentes", 5490,
     "Folhagem fina e arqueada que cresce em volume ao redor do vaso."),
    ("Adiantum raddianum", "Avenca", "Folhagens", 4790,
     "Folíolos delicados em forma de leque sustentados por hastes finas."),
)


def main():
    settings = load_settings()
    if not settings.mongodb_uri:
        raise SystemExit("Preencha MONGODB_URI em .streamlit/secrets.toml.")

    missing = []
    with MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000) as connection:
        collection = connection[settings.mongodb_database].products
        collection.create_index([("created_at", -1), ("_id", 1)], name="catalog_order")
        products = Products(collection)
        for scientific_name, name, category, price, description in STARTER_PRODUCTS:
            plant = find_species(scientific_name)
            if plant is None:
                missing.append(scientific_name)
                continue

            saved = products.save(f"inat-{plant.id}", {
                "name": name,
                "scientific_name": plant.scientific_name,
                "category": category,
                "price_cents": price,
                "description": description,
                "photo": asdict(plant.photo) if plant.photo else None,
                "source": {"provider": "iNaturalist", "taxon_id": plant.id},
            })
            print(f"{name}: {'cadastrada' if saved else 'já cadastrada'}.")

    if missing:
        raise SystemExit(f"Espécies não encontradas no iNaturalist: {', '.join(missing)}.")


if __name__ == "__main__":
    main()
