from agro_gee_api.services.gee_catalog import GEECatalogService


class FakeCatalogRepo:
    def list_datasets(self) -> list[dict[str, object]]:
        return [
            {
                "dataset_id": "COPERNICUS/S2_SR_HARMONIZED",
                "provider": "gee",
                "title": "Sentinel-2 SR Harmonized",
                "bands": ["B2", "B3", "B4", "B8"],
                "is_active": True,
            },
            {
                "dataset_id": "USGS/SRTMGL1_003",
                "provider": "gee",
                "title": "SRTM DEM",
                "bands": ["elevation"],
                "is_active": False,
            },
        ]


def test_list_datasets_returns_only_active_items() -> None:
    service = GEECatalogService(repository=FakeCatalogRepo())

    result = service.list_datasets()

    assert len(result) == 1
    assert result[0].dataset_id == "COPERNICUS/S2_SR_HARMONIZED"
    assert result[0].bands == ["B2", "B3", "B4", "B8"]


def test_list_datasets_uses_seeded_catalog_without_db_dependency() -> None:
    service = GEECatalogService()

    result = service.list_datasets()

    assert len(result) == 1
    assert result[0].dataset_id == "COPERNICUS/S2_SR_HARMONIZED"
    assert result[0].provider == "gee"
    assert result[0].title == "Sentinel-2 SR Harmonized"
    assert result[0].bands == ["B2", "B3", "B4", "B8", "QA60"]
