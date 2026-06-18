import math

import pytest

from agro_gee_api.services.gee_client import (
    EarthEngineClient,
    GEEAuthError,
    GEEUnavailableError,
    build_oauth_config,
    build_service_account_config,
)


def test_build_service_account_config_requires_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_EMAIL", raising=False)
    monkeypatch.delenv("GEE_PRIVATE_KEY", raising=False)

    with pytest.raises(GEEAuthError) as exc:
        build_service_account_config()

    assert exc.value.error_code == "GEE_AUTH_FAILED"


def test_build_service_account_config_reads_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    )

    config = build_service_account_config()

    assert config.service_account_email == "svc@example.iam.gserviceaccount.com"


def test_build_oauth_config_requires_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GEE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GEE_OAUTH_REFRESH_TOKEN", raising=False)

    with pytest.raises(GEEAuthError) as exc:
        build_oauth_config()

    assert exc.value.error_code == "GEE_AUTH_FAILED"


def test_build_oauth_config_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEE_OAUTH_CLIENT_ID", "oauth-client-id")
    monkeypatch.setenv("GEE_OAUTH_CLIENT_SECRET", "oauth-client-secret")
    monkeypatch.setenv("GEE_OAUTH_REFRESH_TOKEN", "oauth-refresh-token")

    config = build_oauth_config()

    assert config.client_id == "oauth-client-id"
    assert config.client_secret == "oauth-client-secret"
    assert config.refresh_token == "oauth-refresh-token"


class FakeRuntime:
    def __init__(self) -> None:
        self.ensure_initialized_calls = 0

    def ensure_initialized(self) -> None:
        self.ensure_initialized_calls += 1


class FakeInfoValue:
    def __init__(self, value: object, ee: "FakeEE | None" = None) -> None:
        self._value = value
        self._ee = ee

    def getInfo(self) -> object:
        if self._ee is not None and self._ee.in_map_callback:
            raise AssertionError("getInfo() called inside map callback")
        return self._value


class FakeDictValue:
    def __init__(self, values: dict[str, object], ee: "FakeEE") -> None:
        self._values = values
        self._ee = ee

    def get(self, key: str, default: object = None) -> object:
        if key not in self._values:
            return default
        return FakeInfoValue(self._values[key], self._ee)

    def getInfo(self) -> dict[str, object]:
        if self._ee.in_map_callback:
            raise AssertionError("getInfo() called inside map callback")
        return self._values


class FakeFeatureCollection:
    def __init__(self, features: list[object], ee: "FakeEE") -> None:
        self._features = features
        self._ee = ee

    def getInfo(self) -> dict[str, object]:
        if self._ee.feature_collection_info_override is not None:
            return self._ee.feature_collection_info_override

        def resolve(value: object) -> object:
            if isinstance(value, FakeInfoValue):
                return value.getInfo()
            if isinstance(value, dict):
                return {k: resolve(v) for k, v in value.items()}
            if isinstance(value, list):
                return [resolve(item) for item in value]
            return value

        return {
            "type": "FeatureCollection",
            "features": [resolve(feature) for feature in self._features],
        }


class FakeDate:
    def __init__(self, date_str: str, ee: "FakeEE") -> None:
        self._date_str = date_str
        self._ee = ee

    def format(self, _: str) -> FakeInfoValue:
        return FakeInfoValue(self._date_str, self._ee)


class FakeTimeseriesImage:
    def __init__(
        self,
        date_str: str,
        ndvi: object,
        cloud_pct: object,
        ee: "FakeEE",
        band_values: dict[str, float] | None = None,
    ) -> None:
        self._date_str = date_str
        self._ndvi = ndvi
        self._cloud_pct = cloud_pct
        self._ee = ee
        self._band_values = band_values or {}
        self._selected_band: str | None = None
        self._expression_value: float | None = None

    def normalizedDifference(self, _: list[str]) -> "FakeTimeseriesImage":
        return self

    def rename(self, _: str) -> "FakeTimeseriesImage":
        return self

    def copyProperties(
        self, _: "FakeTimeseriesImage", __: list[str]
    ) -> "FakeTimeseriesImage":
        return self

    def reduceRegion(self, **_: object) -> FakeDictValue:
        if self._expression_value is not None:
            return FakeDictValue({"INDEX": self._expression_value}, self._ee)
        if self._selected_band is not None:
            selected_value = self._band_values.get(self._selected_band)
            return FakeDictValue(
                {
                    "INDEX": selected_value,
                    self._selected_band: selected_value,
                },
                self._ee,
            )
        return FakeDictValue({"INDEX": self._ndvi}, self._ee)

    def get(self, key: str) -> object:
        if key == "CLOUDY_PIXEL_PERCENTAGE":
            return self._cloud_pct
        return None

    def select(self, _: str) -> "FakeTimeseriesImage":
        self._selected_band = _
        return self

    def expression(self, expr: str, values: dict[str, object]) -> "FakeTimeseriesImage":
        self._ee.last_expression = expr
        if "pow(10" in expr or "**" in expr:
            vv_image = values.get("VV")
            vh_image = values.get("VH")
            vv_band = (
                vv_image._selected_band
                if isinstance(vv_image, FakeTimeseriesImage)
                else None
            )
            vh_band = (
                vh_image._selected_band
                if isinstance(vh_image, FakeTimeseriesImage)
                else None
            )
            vv_db = self._band_values.get(vv_band) if vv_band is not None else None
            vh_db = self._band_values.get(vh_band) if vh_band is not None else None
            if isinstance(vv_db, float) and isinstance(vh_db, float):
                self._expression_value = (10 ** (vv_db / 10.0)) / (10 ** (vh_db / 10.0))
        return self

    def divide(self, other: object) -> "FakeTimeseriesImage":
        if isinstance(other, FakeTimeseriesImage):
            lhs = self._band_values.get(self._selected_band or "")
            rhs = self._band_values.get(other._selected_band or "")
            if isinstance(lhs, float) and isinstance(rhs, float):
                self._expression_value = lhs / rhs
        return self

    def date(self) -> FakeDate:
        return FakeDate(self._date_str, self._ee)


class FakeDatasetImage:
    def __init__(
        self,
        date_str: str,
        value: object,
        band_name: str,
        ee: "FakeEE",
    ) -> None:
        self._date_str = date_str
        self._value = value
        self._band_name = band_name
        self._ee = ee

    def normalizedDifference(self, _: list[str]) -> "FakeDatasetImage":
        return self

    def rename(self, _: str) -> "FakeDatasetImage":
        return self

    def copyProperties(
        self, _: "FakeDatasetImage", __: list[str]
    ) -> "FakeDatasetImage":
        return self

    def reduceRegion(self, **kwargs: object) -> FakeDictValue:
        self._ee.last_dataset_scale = kwargs.get("scale")
        return FakeDictValue({self._band_name: self._value}, self._ee)

    def date(self) -> FakeDate:
        return FakeDate(self._date_str, self._ee)


class FakeImage:
    def __init__(self, ee: "FakeEE") -> None:
        self._ee = ee
        self._selected_band: str | None = None
        self._expression_value: float | None = None

    def normalizedDifference(self, _: list[str]) -> "FakeImage":
        return self

    def rename(self, _: str) -> "FakeImage":
        return self

    def copyProperties(self, _: "FakeImage", __: list[str]) -> "FakeImage":
        return self

    def reduceRegion(self, **_: object) -> FakeDictValue:
        if self._expression_value is not None:
            return FakeDictValue({"INDEX": self._expression_value}, self._ee)
        if (
            self._selected_band is not None
            and self._selected_band in self._ee.sentinel1_mean_values
        ):
            value = self._ee.sentinel1_mean_values[self._selected_band]
            return FakeDictValue(
                {
                    "INDEX": value,
                    self._selected_band: value,
                },
                self._ee,
            )
        return FakeDictValue({"INDEX": self._ee.next_reduce_value}, self._ee)

    def get(self, key: str) -> object:
        if key == "CLOUDY_PIXEL_PERCENTAGE":
            return self._ee.default_cloud_pct
        return None

    def select(self, _: str) -> "FakeImage":
        self._selected_band = _
        return self

    def expression(self, expr: str, values: dict[str, object]) -> "FakeImage":
        self._ee.last_expression = expr
        if "pow(10" in expr or "**" in expr:
            vv_image = values.get("VV")
            vh_image = values.get("VH")
            vv_band = (
                vv_image._selected_band if isinstance(vv_image, FakeImage) else None
            )
            vh_band = (
                vh_image._selected_band if isinstance(vh_image, FakeImage) else None
            )
            vv_db = (
                self._ee.sentinel1_mean_values.get(vv_band)
                if vv_band is not None
                else None
            )
            vh_db = (
                self._ee.sentinel1_mean_values.get(vh_band)
                if vh_band is not None
                else None
            )
            if isinstance(vv_db, float) and isinstance(vh_db, float):
                self._expression_value = (10 ** (vv_db / 10.0)) / (10 ** (vh_db / 10.0))
        return self

    def divide(self, other: object) -> "FakeImage":
        if isinstance(other, FakeImage):
            lhs = self._ee.sentinel1_mean_values.get(self._selected_band or "")
            rhs = self._ee.sentinel1_mean_values.get(other._selected_band or "")
            if isinstance(lhs, float) and isinstance(rhs, float):
                self._expression_value = lhs / rhs
        return self

    def clip(self, _: object) -> "FakeImage":
        return self

    def getThumbURL(self, params: dict[str, object]) -> str:
        self._ee.last_thumb_params = params
        return self._ee.thumb_url


class FakeImageCollection:
    def __init__(self, ee: "FakeEE") -> None:
        self._ee = ee

    def filterBounds(self, geometry: object) -> "FakeImageCollection":
        self._ee.last_geometry = geometry
        return self

    def filterDate(self, start: str, end: str) -> "FakeImageCollection":
        self._ee.last_dates = (start, end)
        return self

    def filter(self, _: object) -> "FakeImageCollection":
        self._ee.applied_filters.append(_)
        return self

    def map(self, fn: object) -> "FakeImageCollection | FakeFeatureCollection":
        if callable(fn):
            if self._ee.mode == "timeseries" and self._ee.timeseries_samples:
                first_date, first_ndvi, first_cloud_pct = self._ee.timeseries_samples[0]
                self._ee.in_map_callback = True
                first_result = fn(
                    FakeTimeseriesImage(
                        first_date,
                        first_ndvi,
                        first_cloud_pct,
                        self._ee,
                    )
                )
                self._ee.in_map_callback = False
                if isinstance(first_result, dict) and "properties" in first_result:
                    features: list[object] = [first_result]
                    for date_str, ndvi, cloud_pct in self._ee.timeseries_samples[1:]:
                        self._ee.in_map_callback = True
                        features.append(
                            fn(FakeTimeseriesImage(date_str, ndvi, cloud_pct, self._ee))
                        )
                        self._ee.in_map_callback = False
                    return FakeFeatureCollection(features, self._ee)
            if self._ee.mode == "dataset" and self._ee.dataset_samples:
                first_date, first_value = self._ee.dataset_samples[0]
                self._ee.in_map_callback = True
                first_result = fn(
                    FakeDatasetImage(
                        first_date,
                        first_value,
                        self._ee.dataset_band_name,
                        self._ee,
                    )
                )
                self._ee.in_map_callback = False
                if isinstance(first_result, dict) and "properties" in first_result:
                    features = [first_result]
                    for date_str, value in self._ee.dataset_samples[1:]:
                        self._ee.in_map_callback = True
                        features.append(
                            fn(
                                FakeDatasetImage(
                                    date_str,
                                    value,
                                    self._ee.dataset_band_name,
                                    self._ee,
                                )
                            )
                        )
                        self._ee.in_map_callback = False
                    return FakeFeatureCollection(features, self._ee)
            if (
                self._ee.mode == "sentinel1_timeseries"
                and self._ee.sentinel1_timeseries_samples
            ):
                first_date, first_vv, first_vh = self._ee.sentinel1_timeseries_samples[
                    0
                ]
                self._ee.in_map_callback = True
                first_result = fn(
                    FakeTimeseriesImage(
                        first_date,
                        ndvi=first_vv,
                        cloud_pct=None,
                        ee=self._ee,
                        band_values={"VV": first_vv, "VH": first_vh},
                    )
                )
                self._ee.in_map_callback = False
                if isinstance(first_result, dict) and "properties" in first_result:
                    features = [first_result]
                    for date_str, vv, vh in self._ee.sentinel1_timeseries_samples[1:]:
                        self._ee.in_map_callback = True
                        features.append(
                            fn(
                                FakeTimeseriesImage(
                                    date_str,
                                    ndvi=vv,
                                    cloud_pct=None,
                                    ee=self._ee,
                                    band_values={"VV": vv, "VH": vh},
                                )
                            )
                        )
                        self._ee.in_map_callback = False
                    return FakeFeatureCollection(features, self._ee)
            fn(FakeImage(self._ee))
        return self

    def size(self) -> FakeInfoValue:
        return FakeInfoValue(self._ee.collection_size)

    def mean(self) -> FakeImage:
        return FakeImage(self._ee)


class FakeReducer:
    @staticmethod
    def mean() -> str:
        return "mean"


class FakeFilter:
    @staticmethod
    def lte(field: str, value: int) -> tuple[str, str, int]:
        return ("lte", field, value)

    @staticmethod
    def eq(field: str, value: str) -> tuple[str, str, str]:
        return ("eq", field, value)

    @staticmethod
    def listContains(field: str, value: str) -> tuple[str, str, str]:
        return ("listContains", field, value)


class FakeGeometryFactory:
    def __call__(self, geojson: dict[str, object]) -> dict[str, object]:
        return {"wrapped": geojson}


class FakeEE:
    def __init__(self) -> None:
        self.collection_size = 2
        self.next_reduce_value: object = 0.42
        self.default_cloud_pct: object = 18.0
        self.timeseries_samples: list[tuple[str, object, object]] = [
            ("2024-01-01", 0.21, 12.0),
            ("2024-01-11", 0.34, 8.0),
        ]
        self.thumb_url = "https://example.test/thumb.png"
        self.mode = "default"
        self.dataset_samples: list[tuple[str, object]] = []
        self.dataset_band_name = "temperature_2m"
        self.sentinel1_mean_values: dict[str, float] = {"VV": -10.0, "VH": -20.0}
        self.sentinel1_timeseries_samples: list[tuple[str, float, float]] = []
        self.applied_filters: list[object] = []
        self.last_expression: str | None = None
        self.last_dataset_id: str | None = None
        self.last_dataset_scale: object | None = None
        self.feature_collection_info_override: dict[str, object] | None = None
        self.last_geometry: object | None = None
        self.last_dates: tuple[str, str] | None = None
        self.last_thumb_params: dict[str, object] | None = None
        self.in_map_callback = False
        self.Filter = FakeFilter()
        self.Reducer = FakeReducer()
        self.Geometry = FakeGeometryFactory()

    def ImageCollection(self, dataset_id: str) -> FakeImageCollection:
        if self.mode not in {"dataset", "sentinel1", "sentinel1_timeseries"}:
            assert dataset_id == "COPERNICUS/S2_SR_HARMONIZED"
        self.last_dataset_id = dataset_id
        return FakeImageCollection(self)

    def Feature(self, _: object, properties: dict[str, object]) -> dict[str, object]:
        return {"type": "Feature", "properties": properties}


@pytest.fixture
def gee_client() -> tuple[EarthEngineClient, FakeRuntime, FakeEE]:
    runtime = FakeRuntime()
    ee = FakeEE()
    return EarthEngineClient(runtime=runtime, ee_module=ee), runtime, ee


def test_ndvi_mean_uses_runtime_and_returns_value(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, runtime, _ = gee_client

    value, images_used = client.ndvi_mean(
        geometry_geojson={"type": "Polygon", "coordinates": []},
        date_start="2024-01-01",
        date_end="2024-01-31",
        cloud_pct_max=20,
    )

    assert runtime.ensure_initialized_calls == 1
    assert value == 0.42
    assert images_used == 2


def test_extract_point_returns_reduced_ndvi(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, runtime, _ = gee_client

    value = client.extract_point(
        geometry_geojson={"type": "Point", "coordinates": [1.0, 2.0]},
        date_start="2024-01-01",
        date_end="2024-01-31",
        cloud_pct_max=10,
    )

    assert runtime.ensure_initialized_calls == 1
    assert value == 0.42


def test_extract_polygon_returns_reduced_ndvi(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, runtime, _ = gee_client

    value = client.extract_polygon(
        geometry_geojson={"type": "Polygon", "coordinates": []},
        date_start="2024-01-01",
        date_end="2024-01-31",
        cloud_pct_max=15,
    )

    assert runtime.ensure_initialized_calls == 1
    assert value == 0.42


def test_legacy_extract_path_uses_sentinel2_dataset(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, _, ee = gee_client

    value = client.extract_point(
        geometry_geojson={"type": "Point", "coordinates": [1.0, 2.0]},
        date_start="2024-01-01",
        date_end="2024-01-31",
        cloud_pct_max=10,
    )

    assert value == 0.42
    assert ee.last_dataset_id == "COPERNICUS/S2_SR_HARMONIZED"


@pytest.mark.parametrize("metric", ["ndvi_mean", "ndwi_mean", "evi_mean", "savi_mean"])
def test_extract_point_supports_extended_metrics(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE], metric: str
) -> None:
    client, _, _ = gee_client

    value = client.extract_point(
        geometry_geojson={"type": "Point", "coordinates": [1.0, 2.0]},
        date_start="2024-01-01",
        date_end="2024-01-31",
        cloud_pct_max=10,
        metric=metric,
    )

    assert value == 0.42


def test_extract_point_maps_missing_ndvi_to_no_imagery(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, runtime, ee = gee_client
    ee.next_reduce_value = None

    with pytest.raises(GEEUnavailableError) as raised:
        client.extract_point(
            geometry_geojson={"type": "Point", "coordinates": [1.0, 2.0]},
            date_start="2024-01-01",
            date_end="2024-01-31",
            cloud_pct_max=10,
        )

    assert runtime.ensure_initialized_calls == 1
    assert raised.value.error_code == "NO_IMAGERY"
    assert raised.value.retryable is False


def test_timeseries_reduces_per_image_and_parses_feature_collection(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, runtime, ee = gee_client
    ee.mode = "timeseries"

    items = client.timeseries(
        geometry_geojson={"type": "Polygon", "coordinates": []},
        date_start="2024-01-01",
        date_end="2024-01-31",
        cloud_pct_max=20,
    )

    assert runtime.ensure_initialized_calls == 1
    assert items == [
        {"date": "2024-01-01", "value": 0.21, "cloud_pct": 12.0},
        {"date": "2024-01-11", "value": 0.34, "cloud_pct": 8.0},
    ]


def test_timeseries_filters_malformed_and_empty_items(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, _, ee = gee_client
    ee.mode = "timeseries"
    ee.timeseries_samples = [
        ("2024-01-01", 0.2, 11.0),
        ("2024-01-02", None, 25.0),
        ("", 0.1, 9.0),
        ("2024-01-03", "not-a-number", 17.0),
    ]

    items = client.timeseries(
        geometry_geojson={"type": "Polygon", "coordinates": []},
        date_start="2024-01-01",
        date_end="2024-01-31",
        cloud_pct_max=20,
    )

    assert items == [{"date": "2024-01-01", "value": 0.2, "cloud_pct": 11.0}]


def test_image_returns_thumbnail_url(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, runtime, ee = gee_client

    url = client.image(
        geometry_geojson={"type": "Polygon", "coordinates": []},
        date_start="2024-01-01",
        date_end="2024-01-31",
        cloud_pct_max=20,
    )

    assert runtime.ensure_initialized_calls == 1
    assert url == "https://example.test/thumb.png"
    assert ee.last_thumb_params is not None
    assert ee.last_thumb_params["min"] == -1
    assert ee.last_thumb_params["max"] == 1


def test_execute_does_not_map_programmer_errors() -> None:
    class FailingRuntime:
        def ensure_initialized(self) -> None:
            return None

    class BrokenClient(EarthEngineClient):
        def _operation_ndvi_mean(self, **_: object) -> tuple[float | None, int]:
            raise ValueError("bad local parsing")

    client = BrokenClient(runtime=FailingRuntime(), ee_module=FakeEE())

    with pytest.raises(ValueError):
        client.ndvi_mean(
            geometry_geojson={"type": "Polygon", "coordinates": []},
            date_start="2024-01-01",
            date_end="2024-01-02",
            cloud_pct_max=20,
        )


def test_error_message_sanitization_redacts_sensitive_details() -> None:
    class FailingRuntime:
        def ensure_initialized(self) -> None:
            return None

    class BrokenClient(EarthEngineClient):
        def _operation_ndvi_mean(self, **_: object) -> tuple[float | None, int]:
            raise RuntimeError(
                "project=abc token=secret refresh_token=rt private key leaked"
            )

    client = BrokenClient(runtime=FailingRuntime(), ee_module=FakeEE())

    with pytest.raises(GEEUnavailableError) as raised:
        client.ndvi_mean(
            geometry_geojson={"type": "Polygon", "coordinates": []},
            date_start="2024-01-01",
            date_end="2024-01-02",
            cloud_pct_max=20,
        )

    assert raised.value.error_code == "GEE_INTERNAL_ERROR"
    assert raised.value.retryable is False
    assert "token" not in raised.value.message.lower()
    assert "private key" not in raised.value.message.lower()


@pytest.mark.parametrize(
    ("exc", "expected_type", "code", "retryable"),
    [
        (
            PermissionError("permission denied"),
            GEEAuthError,
            "GEE_AUTH_FAILED",
            None,
        ),
        (
            TimeoutError("request timed out"),
            GEEUnavailableError,
            "GEE_TIMEOUT",
            True,
        ),
        (
            ConnectionError("network unavailable"),
            GEEUnavailableError,
            "GEE_UNAVAILABLE",
            True,
        ),
        (
            RuntimeError("sdk exploded"),
            GEEUnavailableError,
            "GEE_INTERNAL_ERROR",
            False,
        ),
    ],
)
def test_canonical_error_mapping_for_all_operations(
    exc: Exception,
    expected_type: type[Exception],
    code: str,
    retryable: bool | None,
) -> None:
    class FailingRuntime:
        def ensure_initialized(self) -> None:
            return None

    class BrokenClient(EarthEngineClient):
        def _operation_ndvi_mean(self, **_: object) -> tuple[float | None, int]:
            raise exc

        def _operation_extract_point(self, **_: object) -> float:
            raise exc

        def _operation_extract_polygon(self, **_: object) -> float:
            raise exc

        def _operation_timeseries(self, **_: object) -> list[dict[str, object]]:
            raise exc

        def _operation_image(self, **_: object) -> str:
            raise exc

        def _operation_extract_point_dataset(self, **_: object) -> dict[str, object]:
            raise exc

        def _operation_extract_polygon_dataset(self, **_: object) -> dict[str, object]:
            raise exc

    client = BrokenClient(runtime=FailingRuntime(), ee_module=FakeEE())
    common_kwargs = {
        "geometry_geojson": {"type": "Polygon", "coordinates": []},
        "date_start": "2024-01-01",
        "date_end": "2024-01-02",
        "cloud_pct_max": 20,
    }
    dataset_kwargs = {
        "dataset_id": "ECMWF/ERA5_LAND/HOURLY",
        "band_name": "temperature_2m",
        "variable": "temp",
        "geometry_geojson": {"type": "Point", "coordinates": [1.0, 2.0]},
        "date_start": "2024-01-01",
        "date_end": "2024-01-02",
    }

    for method_name in (
        "ndvi_mean",
        "extract_point",
        "extract_polygon",
        "timeseries",
        "image",
        "extract_point_dataset",
        "extract_polygon_dataset",
    ):
        method = getattr(client, method_name)
        with pytest.raises(expected_type) as raised:
            if method_name in ("extract_point_dataset", "extract_polygon_dataset"):
                method(**dataset_kwargs)
            else:
                method(**common_kwargs)

        assert getattr(raised.value, "error_code") == code
        if retryable is not None:
            assert isinstance(raised.value, GEEUnavailableError)
            assert raised.value.retryable is retryable


def test_extract_point_dataset_builds_sorted_series_and_mean(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, runtime, ee = gee_client
    ee.mode = "dataset"
    ee.dataset_band_name = "temperature_2m"
    ee.dataset_samples = [
        ("2024-01-02T06:00:00Z", 20.0),
        ("2024-01-01T18:00:00Z", 10.0),
        ("2024-01-03T00:00:00Z", 30.0),
    ]

    result = client.extract_point_dataset(
        dataset_id="ECMWF/ERA5_LAND/HOURLY",
        band_name="temperature_2m",
        variable="temp",
        geometry_geojson={"type": "Point", "coordinates": [1.0, 2.0]},
        date_start="2024-01-01",
        date_end="2024-01-03",
    )

    assert runtime.ensure_initialized_calls == 1
    assert ee.last_dataset_id == "ECMWF/ERA5_LAND/HOURLY"
    assert result["dataset"] == "ECMWF/ERA5_LAND/HOURLY"
    assert result["variable"] == "temp"
    assert result["value"] == 20.0
    assert ee.last_dataset_scale == 10000
    assert result["series"] == [
        {"date": "2024-01-01T18:00:00Z", "value": 10.0, "cloud_pct": None},
        {"date": "2024-01-02T06:00:00Z", "value": 20.0, "cloud_pct": None},
        {"date": "2024-01-03T00:00:00Z", "value": 30.0, "cloud_pct": None},
    ]


def test_extract_polygon_dataset_applies_utc_date_boundaries(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, _, ee = gee_client
    ee.mode = "dataset"
    ee.dataset_band_name = "surface_pressure"
    ee.dataset_samples = [("2024-01-01T00:00:00Z", 1000.0)]

    result = client.extract_polygon_dataset(
        dataset_id="ECMWF/NRT_FORECAST/IFS/OPER",
        band_name="surface_pressure",
        variable="sp",
        geometry_geojson={"type": "Polygon", "coordinates": []},
        date_start="2024-01-01",
        date_end="2024-01-31",
        scale=5000,
    )

    assert result["series"]
    assert ee.last_dates == ("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    assert ee.last_dataset_scale == 5000


def test_extract_point_dataset_drops_invalid_numeric_values(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, _, ee = gee_client
    ee.mode = "dataset"
    ee.dataset_band_name = "temperature_2m"
    ee.dataset_samples = [
        ("2024-01-01T00:00:00Z", None),
        ("2024-01-01T01:00:00Z", "abc"),
        ("2024-01-01T02:00:00Z", math.nan),
        ("2024-01-01T03:00:00Z", math.inf),
        ("2024-01-01T04:00:00Z", -math.inf),
        ("2024-01-01T05:00:00Z", 12.5),
    ]

    result = client.extract_point_dataset(
        dataset_id="ECMWF/ERA5_LAND/HOURLY",
        band_name="temperature_2m",
        variable="temp",
        geometry_geojson={"type": "Point", "coordinates": [1.0, 2.0]},
        date_start="2024-01-01",
        date_end="2024-01-01",
    )

    assert result["value"] == 12.5
    assert result["series"] == [
        {"date": "2024-01-01T05:00:00Z", "value": 12.5, "cloud_pct": None}
    ]


def test_extract_polygon_dataset_raises_no_imagery_when_all_invalid(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, _, ee = gee_client
    ee.mode = "dataset"
    ee.dataset_band_name = "surface_pressure"
    ee.dataset_samples = [
        ("2024-01-01T00:00:00Z", None),
        ("2024-01-01T01:00:00Z", math.nan),
        ("2024-01-01T02:00:00Z", math.inf),
    ]

    with pytest.raises(GEEUnavailableError) as raised:
        client.extract_polygon_dataset(
            dataset_id="ECMWF/NRT_FORECAST/IFS/OPER",
            band_name="surface_pressure",
            variable="sp",
            geometry_geojson={"type": "Polygon", "coordinates": []},
            date_start="2024-01-01",
            date_end="2024-01-01",
        )

    assert raised.value.error_code == "NO_IMAGERY"
    assert raised.value.retryable is False


def test_extract_point_dataset_handles_malformed_features_payload_as_no_imagery(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, _, ee = gee_client
    ee.mode = "dataset"
    ee.feature_collection_info_override = {
        "type": "FeatureCollection",
        "features": "bad",
    }

    with pytest.raises(GEEUnavailableError) as raised:
        client.extract_point_dataset(
            dataset_id="ECMWF/ERA5_LAND/HOURLY",
            band_name="temperature_2m",
            variable="temp",
            geometry_geojson={"type": "Point", "coordinates": [1.0, 2.0]},
            date_start="2024-01-01",
            date_end="2024-01-01",
        )

    assert raised.value.error_code == "NO_IMAGERY"
    assert raised.value.retryable is False


def _assert_sentinel1_fixed_filters(ee: FakeEE) -> None:
    assert ("eq", "instrumentMode", "IW") in ee.applied_filters
    assert (
        "listContains",
        "transmitterReceiverPolarisation",
        "VV",
    ) in ee.applied_filters
    assert (
        "listContains",
        "transmitterReceiverPolarisation",
        "VH",
    ) in ee.applied_filters


@pytest.mark.parametrize(
    ("method_name", "mode", "geometry_geojson", "metric", "expected"),
    [
        (
            "extract_point_sentinel1",
            "sentinel1",
            {"type": "Point", "coordinates": [1.0, 2.0]},
            "vv_mean",
            -9.0,
        ),
        (
            "extract_point_sentinel1",
            "sentinel1",
            {"type": "Point", "coordinates": [1.0, 2.0]},
            "vh_mean",
            -17.5,
        ),
        (
            "extract_point_sentinel1",
            "sentinel1",
            {"type": "Point", "coordinates": [1.0, 2.0]},
            "vv_vh_ratio",
            pytest.approx(10**0.85),
        ),
        (
            "extract_polygon_sentinel1",
            "sentinel1",
            {"type": "Polygon", "coordinates": []},
            "vv_mean",
            -9.0,
        ),
        (
            "extract_polygon_sentinel1",
            "sentinel1",
            {"type": "Polygon", "coordinates": []},
            "vh_mean",
            -17.5,
        ),
        (
            "extract_polygon_sentinel1",
            "sentinel1",
            {"type": "Polygon", "coordinates": []},
            "vv_vh_ratio",
            pytest.approx(10**0.85),
        ),
        (
            "timeseries_sentinel1",
            "sentinel1_timeseries",
            {"type": "Polygon", "coordinates": []},
            "vv_mean",
            [
                {"date": "2024-01-01", "value": -10.0, "cloud_pct": None},
                {"date": "2024-01-02", "value": -7.0, "cloud_pct": None},
            ],
        ),
        (
            "timeseries_sentinel1",
            "sentinel1_timeseries",
            {"type": "Polygon", "coordinates": []},
            "vh_mean",
            [
                {"date": "2024-01-01", "value": -20.0, "cloud_pct": None},
                {"date": "2024-01-02", "value": -17.0, "cloud_pct": None},
            ],
        ),
        (
            "timeseries_sentinel1",
            "sentinel1_timeseries",
            {"type": "Polygon", "coordinates": []},
            "vv_vh_ratio",
            [
                {"date": "2024-01-01", "value": pytest.approx(10.0), "cloud_pct": None},
                {"date": "2024-01-02", "value": pytest.approx(10.0), "cloud_pct": None},
            ],
        ),
    ],
)
def test_sentinel1_metric_mapping_for_all_methods(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
    method_name: str,
    mode: str,
    geometry_geojson: dict[str, object],
    metric: str,
    expected: object,
) -> None:
    client, runtime, ee = gee_client
    ee.mode = mode
    ee.sentinel1_mean_values = {"VV": -9.0, "VH": -17.5}
    ee.sentinel1_timeseries_samples = [
        ("2024-01-01", -10.0, -20.0),
        ("2024-01-02", -7.0, -17.0),
    ]

    method = getattr(client, method_name)
    result = method(
        geometry_geojson=geometry_geojson,
        date_start="2024-01-01",
        date_end="2024-01-31",
        metric=metric,
    )

    assert runtime.ensure_initialized_calls == 1
    assert result == expected


@pytest.mark.parametrize(
    ("method_name", "mode", "geometry_geojson"),
    [
        (
            "extract_point_sentinel1",
            "sentinel1",
            {"type": "Point", "coordinates": [1.0, 2.0]},
        ),
        (
            "extract_polygon_sentinel1",
            "sentinel1",
            {"type": "Polygon", "coordinates": []},
        ),
        (
            "timeseries_sentinel1",
            "sentinel1_timeseries",
            {"type": "Polygon", "coordinates": []},
        ),
    ],
)
def test_sentinel1_collection_applies_fixed_iw_and_dual_pol_filters_for_all_methods(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
    method_name: str,
    mode: str,
    geometry_geojson: dict[str, object],
) -> None:
    client, _, ee = gee_client
    ee.mode = mode
    ee.sentinel1_timeseries_samples = [
        ("2024-01-01", -10.0, -20.0),
        ("2024-01-02", -7.0, -17.0),
    ]

    method = getattr(client, method_name)
    method(
        geometry_geojson=geometry_geojson,
        date_start="2024-01-01",
        date_end="2024-01-31",
        metric="vv_mean",
    )

    _assert_sentinel1_fixed_filters(ee)


def test_sentinel1_extract_uses_s1_grd_dataset_id(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, _, ee = gee_client
    ee.mode = "sentinel1"

    client.extract_point_sentinel1(
        geometry_geojson={"type": "Point", "coordinates": [1.0, 2.0]},
        date_start="2024-01-01",
        date_end="2024-01-31",
        metric="vv_mean",
    )

    assert ee.last_dataset_id == "COPERNICUS/S1_GRD"


def test_sentinel1_timeseries_uses_s1_grd_dataset_id(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, _, ee = gee_client
    ee.mode = "sentinel1_timeseries"
    ee.sentinel1_timeseries_samples = [
        ("2024-01-01", -10.0, -20.0),
        ("2024-01-02", -7.0, -17.0),
    ]

    client.timeseries_sentinel1(
        geometry_geojson={"type": "Polygon", "coordinates": []},
        date_start="2024-01-01",
        date_end="2024-01-31",
        metric="vv_mean",
    )

    assert ee.last_dataset_id == "COPERNICUS/S1_GRD"


@pytest.mark.parametrize(
    ("method_name", "mode", "geometry_geojson"),
    [
        (
            "extract_point_sentinel1",
            "sentinel1",
            {"type": "Point", "coordinates": [1.0, 2.0]},
        ),
        (
            "extract_polygon_sentinel1",
            "sentinel1",
            {"type": "Polygon", "coordinates": []},
        ),
        (
            "timeseries_sentinel1",
            "sentinel1_timeseries",
            {"type": "Polygon", "coordinates": []},
        ),
    ],
)
def test_sentinel1_collection_uses_end_exclusive_next_day_filter_window(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
    method_name: str,
    mode: str,
    geometry_geojson: dict[str, object],
) -> None:
    client, _, ee = gee_client
    ee.mode = mode
    ee.sentinel1_timeseries_samples = [
        ("2024-01-01", -10.0, -20.0),
        ("2024-01-02", -7.0, -17.0),
    ]

    method = getattr(client, method_name)
    method(
        geometry_geojson=geometry_geojson,
        date_start="2024-01-01",
        date_end="2024-01-31",
        metric="vv_mean",
    )

    assert ee.last_dates == ("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")


@pytest.mark.parametrize(
    ("method_name", "metric", "sentinel1_means"),
    [
        ("extract_point_sentinel1", "vv_mean", {"VV": math.nan, "VH": -17.0}),
        ("extract_polygon_sentinel1", "vh_mean", {"VV": -10.0, "VH": math.inf}),
        (
            "extract_point_sentinel1",
            "vv_vh_ratio",
            {"VV": -10.0, "VH": -math.inf},
        ),
    ],
)
def test_sentinel1_extract_non_finite_values_map_to_no_imagery(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
    method_name: str,
    metric: str,
    sentinel1_means: dict[str, float],
) -> None:
    client, _, ee = gee_client
    ee.mode = "sentinel1"
    ee.sentinel1_mean_values = sentinel1_means

    method = getattr(client, method_name)
    with pytest.raises(GEEUnavailableError) as raised:
        method(
            geometry_geojson={"type": "Point", "coordinates": [1.0, 2.0]},
            date_start="2024-01-01",
            date_end="2024-01-31",
            metric=metric,
        )

    assert raised.value.error_code == "NO_IMAGERY"
    assert raised.value.retryable is False


def test_sentinel1_timeseries_all_non_finite_values_map_to_no_imagery(
    gee_client: tuple[EarthEngineClient, FakeRuntime, FakeEE],
) -> None:
    client, _, ee = gee_client
    ee.mode = "sentinel1_timeseries"
    ee.sentinel1_timeseries_samples = [
        ("2024-01-01", math.nan, -20.0),
        ("2024-01-02", math.inf, -17.0),
    ]

    with pytest.raises(GEEUnavailableError) as raised:
        client.timeseries_sentinel1(
            geometry_geojson={"type": "Polygon", "coordinates": []},
            date_start="2024-01-01",
            date_end="2024-01-31",
            metric="vv_mean",
        )

    assert raised.value.error_code == "NO_IMAGERY"
    assert raised.value.retryable is False
