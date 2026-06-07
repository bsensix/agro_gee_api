from dataclasses import dataclass
from typing import Protocol

from agro_gee_api.db import get_connection


@dataclass(frozen=True)
class GEECatalogItem:
    dataset_id: str
    provider: str
    title: str
    bands: list[str]


class GEECatalogRepository(Protocol):
    def list_datasets(self) -> list[dict[str, object]]: ...


class PostgresGEECatalogRepository:
    def list_datasets(self) -> list[dict[str, object]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT dataset_id, provider, title, bands, is_active
                    FROM core.gee_datasets
                    ORDER BY provider, dataset_id;
                    """
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]


class GEECatalogService:
    def __init__(self, *, repository: GEECatalogRepository) -> None:
        self._repository = repository

    def list_datasets(self) -> list[GEECatalogItem]:
        rows = self._repository.list_datasets()
        return [
            GEECatalogItem(
                dataset_id=str(row["dataset_id"]),
                provider=str(row["provider"]),
                title=str(row["title"]),
                bands=[str(band) for band in list(row["bands"])],
            )
            for row in rows
            if bool(row["is_active"])
        ]
