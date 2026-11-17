from dataclasses import dataclass, replace

import httpx

from flora.products import Photo


API_URL = "https://api.inaturalist.org/v1"
USER_AGENT = "FloraStore/1.0 (+https://github.com/Roger-dev-eng/FloraStore)"
PHOTO_LICENSES = {"cc0": "CC0", "cc-by": "CC BY"}
SPECIES_LIMIT = 12
HERO_PHOTO = Photo(
    url="https://inaturalist-open-data.s3.amazonaws.com/photos/463215232/large.jpg",
    attribution="Trevor Van Loon",
    source_url="https://www.inaturalist.org/photos/463215232",
    license="CC BY",
)
PREVIEW_PLANTS = (
    ("Costela-de-adão", "Monstera deliciosa", HERO_PHOTO),
    ("Zamioculca", "Zamioculcas zamiifolia", Photo(
        url="https://inaturalist-open-data.s3.amazonaws.com/photos/628384145/medium.jpg",
        attribution="",
        source_url="https://www.inaturalist.org/photos/628384145",
        license="CC0",
    )),
    ("Jiboia", "Epipremnum aureum", Photo(
        url="https://inaturalist-open-data.s3.amazonaws.com/photos/584537294/medium.jpg",
        attribution="",
        source_url="https://www.inaturalist.org/photos/584537294",
        license="CC0",
    )),
)


@dataclass(frozen=True)
class Species:
    id: int
    scientific_name: str
    photo: Photo | None = None
    common_name: str = ""

    @property
    def label(self):
        if self.common_name:
            return f"{self.common_name} ({self.scientific_name})"
        return self.scientific_name


def _api_client():
    return httpx.Client(base_url=API_URL, headers={"User-Agent": USER_AGENT}, timeout=8)


def _search_taxa(client, path, query):
    response = client.get(path, params={
        "q": query, "rank": "species", "taxon_id": 47126,
        "is_active": "true", "per_page": SPECIES_LIMIT, "locale": "pt-BR",
    })
    response.raise_for_status()
    return [
        Species(item["id"], item["name"], common_name=item.get("preferred_common_name") or "")
        for item in response.json()["results"]
    ]


def search_species(query):
    with _api_client() as client:
        return _search_taxa(client, "/taxa/autocomplete", query)


def _find_photo(client, taxon_id):
    response = client.get("/observations", params={
        "taxon_id": taxon_id, "quality_grade": "research",
        "photo_license": ",".join(PHOTO_LICENSES), "order_by": "votes", "per_page": 10,
    })
    response.raise_for_status()
    for observation in response.json()["results"]:
        for candidate in observation["photos"]:
            license_name = PHOTO_LICENSES.get(candidate.get("license_code"))
            url = candidate.get("url") or ""
            if license_name and url.endswith("/square.jpg") and candidate.get("attribution"):
                attribution = candidate["attribution"].removeprefix("(c) ").split(
                    ", some rights reserved", 1
                )[0]
                return Photo(
                    url=url.removesuffix("/square.jpg") + "/medium.jpg",
                    attribution=attribution if license_name == "CC BY" else "",
                    source_url=f"https://www.inaturalist.org/photos/{candidate['id']}",
                    license=license_name,
                )
    return None


def fetch_species_photo(taxon_id):
    with _api_client() as client:
        return _find_photo(client, taxon_id)


def find_species(scientific_name):
    with _api_client() as client:
        matches = _search_taxa(client, "/taxa", scientific_name)
        for species in matches:
            if species.scientific_name.casefold() == scientific_name.casefold():
                return replace(species, photo=_find_photo(client, species.id))
    return None
