from dataclasses import dataclass

import httpx

from flora.products import Photo


API_URL = "https://api.inaturalist.org/v1"
USER_AGENT = "FloraStore/1.0 (+https://github.com/Roger-dev-eng/FloraStore)"
PHOTO_LICENSES = {"cc0": "CC0", "cc-by": "CC BY"}
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
    photo: Photo | None


def find_species(scientific_name):
    with httpx.Client(base_url=API_URL, headers={"User-Agent": USER_AGENT}, timeout=8) as client:
        response = client.get("/taxa", params={
            "q": scientific_name, "rank": "species", "taxon_id": 47126,
            "is_active": "true", "per_page": 10,
        })
        response.raise_for_status()
        taxa = response.json()["results"]
        taxon = next(
            (item for item in taxa if item["name"].casefold() == scientific_name.casefold()), None
        )
        if taxon is None:
            return None

        response = client.get("/observations", params={
            "taxon_id": taxon["id"], "quality_grade": "research",
            "photo_license": ",".join(PHOTO_LICENSES), "order_by": "votes", "per_page": 10,
        })
        response.raise_for_status()

    photo = None
    for observation in response.json()["results"]:
        for candidate in observation["photos"]:
            license_name = PHOTO_LICENSES.get(candidate.get("license_code"))
            url = candidate.get("url") or ""
            if license_name and url.endswith("/square.jpg") and candidate.get("attribution"):
                attribution = candidate["attribution"].removeprefix("(c) ").split(
                    ", some rights reserved", 1
                )[0]
                photo = Photo(
                    url=url.removesuffix("/square.jpg") + "/medium.jpg",
                    attribution=attribution if license_name == "CC BY" else "",
                    source_url=f"https://www.inaturalist.org/photos/{candidate['id']}",
                    license=license_name,
                )
                break
        if photo:
            break

    return Species(taxon["id"], taxon["name"], photo)
