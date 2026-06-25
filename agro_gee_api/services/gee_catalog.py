from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GEECatalogItem:
    dataset_id: str
    provider: str
    title: str
    bands: list[str]


class GEECatalogRepository(Protocol):
    def list_datasets(self) -> list[dict[str, object]]: ...


class SeededGEECatalogRepository:
    _ROWS: list[dict[str, object]] = [
        {
            "dataset_id": "COPERNICUS/S2_SR_HARMONIZED",
            "provider": "gee",
            "title": "Sentinel-2 SR Harmonized",
            "bands": ["B2", "B3", "B4", "B8", "QA60"],
            "is_active": True,
        },
        {
            "dataset_id": "LANDSAT/LC08/C02/T1_L2",
            "provider": "gee",
            "title": "Landsat 8 Collection 2 Level 2",
            "bands": ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "QA_PIXEL"],
            "is_active": False,
        },
        {
            "dataset_id": "COPERNICUS/DEM/GLO30",
            "provider": "gee",
            "title": "Copernicus DEM GLO30",
            "bands": ["DEM"],
            "is_active": True,
        },
    ]

    def list_datasets(self) -> list[dict[str, object]]:
        return [dict(row) for row in self._ROWS]


class GEECatalogService:
    def __init__(self, *, repository: GEECatalogRepository | None = None) -> None:
        self._repository = repository or SeededGEECatalogRepository()

    def list_datasets(self) -> list[GEECatalogItem]:
        rows = self._repository.list_datasets()
        items: list[GEECatalogItem] = []
        for row in rows:
            if not bool(row.get("is_active")):
                continue
            bands = row.get("bands")
            if not isinstance(bands, list):
                continue
            items.append(
                GEECatalogItem(
                    dataset_id=str(row["dataset_id"]),
                    provider=str(row["provider"]),
                    title=str(row["title"]),
                    bands=[str(band) for band in bands],
                )
            )
        return items
