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
)


def main():
    settings = load_settings()
    if not settings.mongodb_uri:
        raise SystemExit("Preencha MONGODB_URI em .streamlit/secrets.toml.")

    with MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000) as connection:
        collection = connection[settings.mongodb_database].products
        collection.create_index([("created_at", -1), ("_id", 1)], name="catalog_order")
        products = Products(collection)
        for scientific_name, name, category, price, description in STARTER_PRODUCTS:
            plant = find_species(scientific_name)
            if plant is None:
                print(f"Espécie não encontrada no iNaturalist: {scientific_name}.")
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


if __name__ == "__main__":
    main()
