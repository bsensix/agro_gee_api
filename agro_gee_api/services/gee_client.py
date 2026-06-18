from dataclasses import dataclass
from datetime import date, timedelta
import math
import os
from typing import TYPE_CHECKING, Any, Callable, Protocol, TypeVar, TypedDict

try:
    import ee
except Exception:  # pragma: no cover - only used when dependency is unavailable
    ee = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from agro_gee_api.services.gee_runtime import GEERuntime


@dataclass(frozen=True)
class GEEAuthError(Exception):
    error_code: str
    message: str


@dataclass(frozen=True)
class ServiceAccountConfig:
    service_account_email: str
    private_key: str


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str
    client_secret: str
    refresh_token: str


@dataclass(frozen=True)
class GEEUnavailableError(Exception):
    error_code: str
    message: str
    retryable: bool


class DatasetSeriesItem(TypedDict):
    date: str
    value: float
    cloud_pct: None


class DatasetExtractResult(TypedDict):
    dataset: str
    variable: str
    value: float
    series: list[DatasetSeriesItem]


class GEEClient(Protocol):
    def ndvi_mean(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
    ) -> tuple[float | None, int]: ...

    def extract_point(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> float: ...

    def extract_polygon(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> float: ...

    def extract_point_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str,
    ) -> float: ...

    def extract_polygon_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str,
    ) -> float: ...

    def timeseries(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> list[dict[str, object]]: ...

    def timeseries_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str,
    ) -> list[dict[str, object]]: ...

    def image(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> str: ...

    def extract_point_dataset(
        self,
        *,
        dataset_id: str,
        band_name: str,
        variable: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None = None,
    ) -> DatasetExtractResult: ...

    def extract_polygon_dataset(
        self,
        *,
        dataset_id: str,
        band_name: str,
        variable: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None = None,
    ) -> DatasetExtractResult: ...


T = TypeVar("T")


class GEERuntimeProtocol(Protocol):
    def ensure_initialized(self) -> None: ...


class EarthEngineClient:
    _DATASET = "COPERNICUS/S2_SR_HARMONIZED"
    _SENTINEL1_DATASET = "COPERNICUS/S1_GRD"
    _DATASET_EXTRACT_DEFAULT_SCALE = 10_000

    def __init__(
        self, *, runtime: GEERuntimeProtocol | None = None, ee_module: Any = None
    ) -> None:
        self._ee = ee_module or ee
        if runtime is None:
            from agro_gee_api.services.gee_runtime import GEERuntime

            runtime = GEERuntime(ee_module=self._ee)
        self._runtime = runtime

    def ndvi_mean(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
    ) -> tuple[float | None, int]:
        return self._execute(
            self._operation_ndvi_mean,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
        )

    def extract_point(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str = "ndvi_mean",
    ) -> float:
        return self._execute(
            self._operation_extract_point,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
            metric=metric,
        )

    def extract_polygon(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str = "ndvi_mean",
    ) -> float:
        return self._execute(
            self._operation_extract_polygon,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
            metric=metric,
        )

    def timeseries(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str = "ndvi_mean",
    ) -> list[dict[str, object]]:
        return self._execute(
            self._operation_timeseries,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
            metric=metric,
        )

    def extract_point_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str = "vv_mean",
    ) -> float:
        return self._execute(
            self._operation_extract_point_sentinel1,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            metric=metric,
        )

    def extract_polygon_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str = "vv_mean",
    ) -> float:
        return self._execute(
            self._operation_extract_polygon_sentinel1,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            metric=metric,
        )

    def timeseries_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str = "vv_mean",
    ) -> list[dict[str, object]]:
        return self._execute(
            self._operation_timeseries_sentinel1,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            metric=metric,
        )

    def image(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str = "ndvi_mean",
    ) -> str:
        return self._execute(
            self._operation_image,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
            metric=metric,
        )

    def extract_point_dataset(
        self,
        *,
        dataset_id: str,
        band_name: str,
        variable: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None = None,
    ) -> DatasetExtractResult:
        return self._execute(
            self._operation_extract_point_dataset,
            dataset_id=dataset_id,
            band_name=band_name,
            variable=variable,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            scale=scale,
        )

    def extract_polygon_dataset(
        self,
        *,
        dataset_id: str,
        band_name: str,
        variable: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None = None,
    ) -> DatasetExtractResult:
        return self._execute(
            self._operation_extract_polygon_dataset,
            dataset_id=dataset_id,
            band_name=band_name,
            variable=variable,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            scale=scale,
        )

    def _execute(self, operation: Callable[..., T], **kwargs: object) -> T:
        try:
            self._runtime.ensure_initialized()
            return operation(**kwargs)
        except GEEAuthError as exc:
            raise GEEAuthError("GEE_AUTH_FAILED", exc.message) from exc
        except GEEUnavailableError as exc:
            raise self._canonicalize_unavailable_error(exc) from exc
        except Exception as exc:
            if isinstance(
                exc,
                (
                    TypeError,
                    ValueError,
                    KeyError,
                    AttributeError,
                    AssertionError,
                    IndexError,
                ),
            ):
                raise
            raise self._map_sdk_error(exc) from exc

    def _operation_ndvi_mean(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
    ) -> tuple[float | None, int]:
        geometry = self._ee.Geometry(geometry_geojson)
        collection = self._ndvi_collection(
            geometry=geometry,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
            metric="ndvi_mean",
        )
        images_used = int(collection.size().getInfo() or 0)
        if images_used <= 0:
            return None, 0

        stats = (
            collection.mean()
            .reduceRegion(
                reducer=self._ee.Reducer.mean(),
                geometry=geometry,
                scale=10,
                maxPixels=1_000_000_000,
            )
            .getInfo()
        )
        value = self._extract_index_value(stats)
        return value, images_used

    def _operation_extract_point(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> float:
        return self._extract_reduced_value(
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
            metric=metric,
        )

    def _operation_extract_polygon(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> float:
        return self._extract_reduced_value(
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
            metric=metric,
        )

    def _operation_extract_point_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str,
    ) -> float:
        return self._extract_reduced_value_sentinel1(
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            metric=metric,
        )

    def _operation_extract_polygon_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str,
    ) -> float:
        return self._extract_reduced_value_sentinel1(
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            metric=metric,
        )

    def _operation_timeseries(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> list[dict[str, object]]:
        geometry = self._ee.Geometry(geometry_geojson)
        collection = self._filtered_collection(
            geometry=geometry,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
        )
        timeseries_collection = collection.map(
            lambda image: self._to_timeseries_feature(
                image=image,
                geometry=geometry,
                metric=metric,
            )
        )
        info = timeseries_collection.getInfo()
        features = info.get("features", []) if isinstance(info, dict) else []
        if not isinstance(features, list):
            return []

        result: list[dict[str, object]] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties", {})
            if not isinstance(properties, dict):
                continue
            date_value = properties.get("date") or properties.get("system:time_start")
            metric_value = properties.get("value")
            if (
                not isinstance(date_value, str)
                or not date_value
                or metric_value is None
            ):
                continue
            try:
                value = float(metric_value)
            except (TypeError, ValueError):
                continue
            cloud_pct: float | None = None
            raw_cloud_pct = properties.get("cloud_pct")
            if raw_cloud_pct is not None:
                try:
                    cloud_pct = float(raw_cloud_pct)
                except (TypeError, ValueError):
                    cloud_pct = None
            result.append(
                {"date": str(date_value), "value": value, "cloud_pct": cloud_pct}
            )
        return result

    def _operation_timeseries_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str,
    ) -> list[dict[str, object]]:
        geometry = self._ee.Geometry(geometry_geojson)
        collection = self._filtered_collection_sentinel1(
            geometry=geometry,
            date_start=date_start,
            date_end=date_end,
        )
        timeseries_collection = collection.map(
            lambda image: self._to_timeseries_feature_sentinel1(
                image=image,
                geometry=geometry,
                metric=metric,
            )
        )
        info = timeseries_collection.getInfo()
        features = info.get("features", []) if isinstance(info, dict) else []
        if not isinstance(features, list):
            features = []

        result: list[dict[str, object]] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties", {})
            if not isinstance(properties, dict):
                continue
            date_value = properties.get("date") or properties.get("system:time_start")
            metric_value = properties.get("value")
            if not isinstance(date_value, str) or not date_value:
                continue

            value: float | None = None
            if metric == "vv_vh_ratio":
                vv_db = properties.get("vv_db")
                vh_db = properties.get("vh_db")
                if vv_db is None:
                    continue
                if vh_db is None:
                    continue
                try:
                    vv_db_float = float(vv_db)
                    vh_db_float = float(vh_db)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(vv_db_float) or not math.isfinite(vh_db_float):
                    continue
                value = 10 ** ((vv_db_float - vh_db_float) / 10.0)
            else:
                if metric_value is None:
                    continue
                try:
                    value = float(metric_value)
                except (TypeError, ValueError):
                    continue
            if value is None or not math.isfinite(value):
                continue

            result.append({"date": str(date_value), "value": value, "cloud_pct": None})

        if not result:
            raise GEEUnavailableError(
                "NO_IMAGERY",
                "No valid imagery for requested period",
                retryable=False,
            )
        return result

    def _to_timeseries_feature(
        self, *, image: object, geometry: object, metric: str
    ) -> object:
        index_image = self._index_image(image=image, metric=metric).rename("INDEX")
        stats = (
            index_image.reduceRegion(
                reducer=self._ee.Reducer.mean(),
                geometry=geometry,
                scale=10,
                maxPixels=1_000_000_000,
            )
            if hasattr(index_image, "reduceRegion")
            else {}
        )
        metric_value: object = None
        if hasattr(stats, "get"):
            metric_value = stats.get("INDEX")
        elif isinstance(stats, dict):
            metric_value = stats.get("INDEX")

        date_value: object = None
        if hasattr(image, "date"):
            date_obj = image.date()
            if hasattr(date_obj, "format"):
                date_value = date_obj.format("YYYY-MM-dd")

        cloud_pct_value = self._cloud_percentage_for_geometry(
            image=image, geometry=geometry
        )

        properties = {
            "date": date_value,
            "value": metric_value,
            "cloud_pct": cloud_pct_value,
        }
        if hasattr(self._ee, "Feature"):
            return self._ee.Feature(None, properties)
        return {"type": "Feature", "properties": properties}

    def _operation_image(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> str:
        geometry = self._ee.Geometry(geometry_geojson)
        collection = self._ndvi_collection(
            geometry=geometry,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
            metric=metric,
        )
        return (
            collection.mean()
            .clip(geometry)
            .getThumbURL(
                {
                    "min": -1,
                    "max": 1,
                    "palette": ["#d73027", "#fdae61", "#ffffbf", "#a6d96a", "#1a9850"],
                    "region": geometry_geojson,
                    "dimensions": 1024,
                    "format": "png",
                }
            )
        )

    def _operation_extract_point_dataset(
        self,
        *,
        dataset_id: str,
        band_name: str,
        variable: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None,
    ) -> DatasetExtractResult:
        return self._operation_extract_dataset(
            dataset_id=dataset_id,
            band_name=band_name,
            variable=variable,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            scale=scale,
        )

    def _operation_extract_polygon_dataset(
        self,
        *,
        dataset_id: str,
        band_name: str,
        variable: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None,
    ) -> DatasetExtractResult:
        return self._operation_extract_dataset(
            dataset_id=dataset_id,
            band_name=band_name,
            variable=variable,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            scale=scale,
        )

    def _operation_extract_dataset(
        self,
        *,
        dataset_id: str,
        band_name: str,
        variable: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None,
    ) -> DatasetExtractResult:
        geometry = self._ee.Geometry(geometry_geojson)
        effective_scale = (
            scale if scale is not None else self._DATASET_EXTRACT_DEFAULT_SCALE
        )
        start_at, end_before = self._to_utc_filter_window(
            date_start=date_start,
            date_end=date_end,
        )
        collection = (
            self._ee.ImageCollection(dataset_id)
            .filterBounds(geometry)
            .filterDate(start_at, end_before)
        )
        mapped_collection = collection.map(
            lambda image: self._to_dataset_series_feature(
                image=image,
                geometry=geometry,
                band_name=band_name,
                scale=effective_scale,
            )
        )
        features_info = (
            mapped_collection.getInfo() if hasattr(mapped_collection, "getInfo") else {}
        )
        features_raw = (
            features_info.get("features", []) if isinstance(features_info, dict) else []
        )
        features = features_raw if isinstance(features_raw, list) else []

        series: list[DatasetSeriesItem] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties", {})
            if not isinstance(properties, dict):
                continue
            date_value = properties.get("date")
            raw_value = properties.get("value")
            if not isinstance(date_value, str) or not date_value:
                continue
            if raw_value is None:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value):
                continue
            series.append({"date": date_value, "value": value, "cloud_pct": None})

        series.sort(key=lambda item: str(item.get("date", "")))
        if not series:
            raise GEEUnavailableError(
                "NO_IMAGERY",
                "No valid imagery found for requested period",
                retryable=False,
            )

        value = sum(float(item["value"]) for item in series) / len(series)
        return {
            "dataset": dataset_id,
            "variable": variable,
            "value": value,
            "series": series,
        }

    def _to_dataset_series_feature(
        self, *, image: object, geometry: object, band_name: str, scale: int
    ) -> object:
        stats = (
            image.reduceRegion(
                reducer=self._ee.Reducer.mean(),
                geometry=geometry,
                scale=scale,
                maxPixels=1_000_000_000,
            )
            if hasattr(image, "reduceRegion")
            else {}
        )
        band_value: object = None
        if hasattr(stats, "get"):
            band_value = stats.get(band_name)
        elif isinstance(stats, dict):
            band_value = stats.get(band_name)

        date_value: object = None
        if hasattr(image, "date"):
            date_obj = image.date()
            if hasattr(date_obj, "format"):
                date_value = date_obj.format("YYYY-MM-dd'T'HH:mm:ss'Z'")

        properties = {
            "date": date_value,
            "value": band_value,
            "cloud_pct": None,
        }
        if hasattr(self._ee, "Feature"):
            return self._ee.Feature(None, properties)
        return {"type": "Feature", "properties": properties}

    def _extract_reduced_value(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> float:
        geometry = self._ee.Geometry(geometry_geojson)
        collection = self._ndvi_collection(
            geometry=geometry,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
            metric=metric,
        )
        stats = (
            collection.mean()
            .reduceRegion(
                reducer=self._ee.Reducer.mean(),
                geometry=geometry,
                scale=10,
                maxPixels=1_000_000_000,
            )
            .getInfo()
        )
        value = self._extract_index_value(stats)
        if value is None:
            raise GEEUnavailableError(
                "NO_IMAGERY",
                "No valid imagery for requested period",
                retryable=False,
            )
        return value

    def _extract_reduced_value_sentinel1(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        metric: str,
    ) -> float:
        geometry = self._ee.Geometry(geometry_geojson)
        collection = self._filtered_collection_sentinel1(
            geometry=geometry,
            date_start=date_start,
            date_end=date_end,
        )
        mean_image = collection.mean()
        value = self._reduce_sentinel1_metric(
            image=mean_image,
            geometry=geometry,
            metric=metric,
        )
        if value is None:
            raise GEEUnavailableError(
                "NO_IMAGERY",
                "No valid imagery for requested period",
                retryable=False,
            )
        return value

    def _filtered_collection(
        self,
        *,
        geometry: object,
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
    ) -> object:
        return (
            self._ee.ImageCollection(self._DATASET)
            .filterBounds(geometry)
            .filterDate(date_start, date_end)
            .filter(self._ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", cloud_pct_max))
        )

    def _filtered_collection_sentinel1(
        self,
        *,
        geometry: object,
        date_start: str,
        date_end: str,
    ) -> object:
        start_at, end_before = self._to_utc_filter_window(
            date_start=date_start,
            date_end=date_end,
        )
        return (
            self._ee.ImageCollection(self._SENTINEL1_DATASET)
            .filterBounds(geometry)
            .filterDate(start_at, end_before)
            .filter(self._ee.Filter.eq("instrumentMode", "IW"))
            .filter(
                self._ee.Filter.listContains(
                    "transmitterReceiverPolarisation",
                    "VV",
                )
            )
            .filter(
                self._ee.Filter.listContains(
                    "transmitterReceiverPolarisation",
                    "VH",
                )
            )
        )

    def _ndvi_collection(
        self,
        *,
        geometry: object,
        date_start: str,
        date_end: str,
        cloud_pct_max: int,
        metric: str,
    ) -> object:
        base = self._filtered_collection(
            geometry=geometry,
            date_start=date_start,
            date_end=date_end,
            cloud_pct_max=cloud_pct_max,
        )
        return base.map(
            lambda image: (
                self._index_image(image=image, metric=metric)
                .rename("INDEX")
                .copyProperties(
                    image,
                    ["system:time_start", "CLOUDY_PIXEL_PERCENTAGE"],
                )
            )
        )

    def _reduce_sentinel1_metric(
        self,
        *,
        image: object,
        geometry: object,
        metric: str,
    ) -> float | None:
        if metric == "vv_mean":
            return self._reduce_sentinel1_band(
                image=image,
                geometry=geometry,
                band_name="VV",
            )
        if metric == "vh_mean":
            return self._reduce_sentinel1_band(
                image=image,
                geometry=geometry,
                band_name="VH",
            )
        if metric == "vv_vh_ratio":
            vv = self._reduce_sentinel1_band(
                image=image,
                geometry=geometry,
                band_name="VV",
            )
            vh = self._reduce_sentinel1_band(
                image=image,
                geometry=geometry,
                band_name="VH",
            )
            if vv is None or vh is None:
                return None
            ratio = 10 ** ((vv - vh) / 10.0)
            if not math.isfinite(ratio):
                return None
            return ratio
        raise ValueError("Unsupported metric")

    def _reduce_sentinel1_band(
        self,
        *,
        image: object,
        geometry: object,
        band_name: str,
    ) -> float | None:
        stats = (
            image.select(band_name)
            .reduceRegion(
                reducer=self._ee.Reducer.mean(),
                geometry=geometry,
                scale=10,
                maxPixels=1_000_000_000,
            )
            .getInfo()
        )
        if not isinstance(stats, dict):
            return None
        raw = stats.get(band_name)
        if raw is None:
            raw = stats.get("INDEX")
        if raw is None:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        return value

    def _extract_index_value(self, stats: object) -> float | None:
        if not isinstance(stats, dict):
            return None
        raw = stats.get("INDEX")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _index_image(self, *, image: object, metric: str) -> object:
        if metric == "ndvi_mean":
            return image.normalizedDifference(["B8", "B4"])
        if metric == "ndwi_mean":
            return image.normalizedDifference(["B3", "B8"])
        if metric == "evi_mean":
            return image.expression(
                "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
                {
                    "NIR": image.select("B8"),
                    "RED": image.select("B4"),
                    "BLUE": image.select("B2"),
                },
            )
        if metric == "savi_mean":
            return image.expression(
                "((NIR - RED) / (NIR + RED + L)) * (1 + L)",
                {
                    "NIR": image.select("B8"),
                    "RED": image.select("B4"),
                    "L": 0.5,
                },
            )
        raise ValueError("Unsupported metric")

    def _sentinel1_index_image(self, *, image: object, metric: str) -> object:
        if metric == "vv_mean":
            return image.select("VV")
        if metric == "vh_mean":
            return image.select("VH")
        if metric == "vv_vh_ratio":
            return image.expression(
                "pow(10, VV / 10) / pow(10, VH / 10)",
                {
                    "VV": image.select("VV"),
                    "VH": image.select("VH"),
                },
            )
        raise ValueError("Unsupported metric")

    def _to_timeseries_feature_sentinel1(
        self, *, image: object, geometry: object, metric: str
    ) -> object:
        metric_value: object = None
        vv_value: object = None
        vh_value: object = None

        if metric == "vv_mean":
            stats = (
                image.select("VV").reduceRegion(
                    reducer=self._ee.Reducer.mean(),
                    geometry=geometry,
                    scale=10,
                    maxPixels=1_000_000_000,
                )
                if hasattr(image, "select") and hasattr(image, "reduceRegion")
                else {}
            )
            if hasattr(stats, "get"):
                metric_value = stats.get("VV")
            elif isinstance(stats, dict):
                metric_value = stats.get("VV")
        elif metric == "vh_mean":
            stats = (
                image.select("VH").reduceRegion(
                    reducer=self._ee.Reducer.mean(),
                    geometry=geometry,
                    scale=10,
                    maxPixels=1_000_000_000,
                )
                if hasattr(image, "select") and hasattr(image, "reduceRegion")
                else {}
            )
            if hasattr(stats, "get"):
                metric_value = stats.get("VH")
            elif isinstance(stats, dict):
                metric_value = stats.get("VH")
        elif metric == "vv_vh_ratio":
            vv_stats = (
                image.select("VV").reduceRegion(
                    reducer=self._ee.Reducer.mean(),
                    geometry=geometry,
                    scale=10,
                    maxPixels=1_000_000_000,
                )
                if hasattr(image, "select") and hasattr(image, "reduceRegion")
                else {}
            )
            vh_stats = (
                image.select("VH").reduceRegion(
                    reducer=self._ee.Reducer.mean(),
                    geometry=geometry,
                    scale=10,
                    maxPixels=1_000_000_000,
                )
                if hasattr(image, "select") and hasattr(image, "reduceRegion")
                else {}
            )
            if hasattr(vv_stats, "get"):
                vv_value = vv_stats.get("VV")
            elif isinstance(vv_stats, dict):
                vv_value = vv_stats.get("VV")
            if hasattr(vh_stats, "get"):
                vh_value = vh_stats.get("VH")
            elif isinstance(vh_stats, dict):
                vh_value = vh_stats.get("VH")
        else:
            raise ValueError("Unsupported metric")

        date_value: object = None
        if hasattr(image, "date"):
            date_obj = image.date()
            if hasattr(date_obj, "format"):
                date_value = date_obj.format("YYYY-MM-dd")

        properties = {
            "date": date_value,
            "value": metric_value,
            "cloud_pct": None,
            "vv_db": vv_value,
            "vh_db": vh_value,
        }
        if hasattr(self._ee, "Feature"):
            return self._ee.Feature(None, properties)
        return {"type": "Feature", "properties": properties}

    def _cloud_percentage_for_geometry(
        self, *, image: object, geometry: object
    ) -> object:
        if hasattr(image, "select") and hasattr(self._ee, "Reducer"):
            try:
                qa60 = image.select("QA60")
                cloud = qa60.bitwiseAnd(1 << 10).neq(0)
                cirrus = qa60.bitwiseAnd(1 << 11).neq(0)
                cloud_mask = cloud.Or(cirrus)
                stats = cloud_mask.reduceRegion(
                    reducer=self._ee.Reducer.mean(),
                    geometry=geometry,
                    scale=20,
                    maxPixels=1_000_000_000,
                )
                if hasattr(stats, "get"):
                    value = stats.get("QA60")
                    if value is not None:
                        if hasattr(self._ee, "Number"):
                            return self._ee.Number(value).multiply(100)
                        return float(value) * 100
                elif isinstance(stats, dict):
                    value = stats.get("QA60")
                    if value is not None:
                        return float(value) * 100
            except Exception:
                pass

        if hasattr(image, "get"):
            return image.get("CLOUDY_PIXEL_PERCENTAGE")
        return None

    def _canonicalize_unavailable_error(
        self, exc: GEEUnavailableError
    ) -> GEEUnavailableError:
        if exc.error_code == "NO_IMAGERY":
            return GEEUnavailableError("NO_IMAGERY", exc.message, retryable=False)
        if exc.error_code == "GEE_TIMEOUT":
            return GEEUnavailableError("GEE_TIMEOUT", exc.message, retryable=True)
        if exc.error_code == "GEE_UNAVAILABLE":
            return GEEUnavailableError("GEE_UNAVAILABLE", exc.message, retryable=True)
        if exc.error_code == "NO_IMAGERY":
            return GEEUnavailableError("NO_IMAGERY", exc.message, retryable=False)
        if exc.error_code == "GEE_INTERNAL_ERROR":
            return GEEUnavailableError(
                "GEE_INTERNAL_ERROR", exc.message, retryable=False
            )
        return GEEUnavailableError("GEE_INTERNAL_ERROR", exc.message, retryable=False)

    def _to_utc_filter_window(
        self, *, date_start: str, date_end: str
    ) -> tuple[str, str]:
        start = date.fromisoformat(date_start)
        end = date.fromisoformat(date_end) + timedelta(days=1)
        return (
            f"{start.isoformat()}T00:00:00Z",
            f"{end.isoformat()}T00:00:00Z",
        )

    def _map_sdk_error(self, exc: Exception) -> GEEAuthError | GEEUnavailableError:
        message = self._sanitize_error_message(str(exc))
        lowered = f"{type(exc).__name__} {exc}".lower()

        auth_tokens = (
            "permission",
            "forbidden",
            "unauthorized",
            "auth",
            "credential",
            "401",
            "403",
        )
        timeout_tokens = ("timeout", "timed out", "deadline exceeded")
        unavailable_tokens = (
            "unavailable",
            "network",
            "connection",
            "temporarily",
            "503",
            "429",
            "rate limit",
        )

        if any(token in lowered for token in auth_tokens):
            return GEEAuthError("GEE_AUTH_FAILED", message)
        if any(token in lowered for token in timeout_tokens):
            return GEEUnavailableError("GEE_TIMEOUT", message, retryable=True)
        if any(token in lowered for token in unavailable_tokens):
            return GEEUnavailableError("GEE_UNAVAILABLE", message, retryable=True)
        return GEEUnavailableError("GEE_INTERNAL_ERROR", message, retryable=False)

    def _sanitize_error_message(self, message: str) -> str:
        text = message.strip()
        if not text:
            return "Earth Engine operation failed"
        lowered = text.lower()
        sensitive_tokens = (
            "token",
            "secret",
            "private key",
            "private_key",
            "authorization",
            "bearer",
            "refresh_token",
            "credential",
        )
        if any(token in lowered for token in sensitive_tokens):
            return "Earth Engine error details redacted"
        internal_tokens = ("traceback", 'file "', "line ")
        if any(token in lowered for token in internal_tokens):
            return "Earth Engine operation failed"
        if len(text) > 240:
            return text[:240]
        return text


def build_service_account_config() -> ServiceAccountConfig:
    email = os.getenv("GEE_SERVICE_ACCOUNT_EMAIL")
    key = os.getenv("GEE_PRIVATE_KEY")
    if not email or not key:
        raise GEEAuthError(
            error_code="GEE_AUTH_FAILED",
            message="Missing service account credentials",
        )
    return ServiceAccountConfig(service_account_email=email, private_key=key)


def build_oauth_config() -> OAuthConfig:
    client_id = os.getenv("GEE_OAUTH_CLIENT_ID")
    client_secret = os.getenv("GEE_OAUTH_CLIENT_SECRET")
    refresh_token = os.getenv("GEE_OAUTH_REFRESH_TOKEN")
    if not client_id or not client_secret or not refresh_token:
        raise GEEAuthError(
            error_code="GEE_AUTH_FAILED",
            message="Missing OAuth credentials",
        )
    return OAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )
