import os
import threading
from typing import Any, Protocol

from agro_gee_api.services.gee_client import GEEAuthError, GEEUnavailableError

try:
    import ee
except Exception:  # pragma: no cover - only used when dependency is unavailable
    ee = None  # type: ignore[assignment]


class GEERuntime:
    def __init__(self, ee_module: "EEModuleProtocol | None" = None) -> None:
        self._ee = ee_module or ee
        self._lock = threading.Lock()
        self._initialized = False

    def ensure_initialized(self, force_recheck: bool = False) -> None:
        if self._initialized and not force_recheck:
            return

        with self._lock:
            if not self._initialized:
                self._initialize_locked()
                return

            if force_recheck:
                self._run_health_probe()

    def _initialize_locked(self) -> None:
        ee_module = self._require_ee()

        project_id = os.getenv("GEE_PROJECT_ID")
        if not project_id:
            raise GEEAuthError("GEE_AUTH_FAILED", "Missing GEE project configuration")

        mode = (os.getenv("GEE_AUTH_MODE") or "auto").strip().lower()
        try:
            credentials = self._resolve_credentials(mode)
        except ImportError as exc:
            raise self._map_sdk_error(exc) from exc

        try:
            ee_module.Initialize(credentials=credentials, project=project_id)
        except Exception as exc:
            raise self._map_sdk_error(exc) from exc

        self._run_health_probe()
        self._initialized = True

    def _resolve_credentials(self, mode: str) -> object:
        if mode == "service_account":
            return self._build_service_account_credentials()
        if mode == "oauth":
            return self._build_oauth_credentials()
        if mode in ("", "auto"):
            if self._has_service_account_config():
                return self._build_service_account_credentials()
            return self._build_oauth_credentials()

        raise GEEAuthError("GEE_AUTH_FAILED", "Unsupported auth mode")

    def _has_service_account_config(self) -> bool:
        return bool(
            os.getenv("GEE_SERVICE_ACCOUNT_EMAIL") and os.getenv("GEE_PRIVATE_KEY")
        )

    def _build_service_account_credentials(self) -> object:
        ee_module = self._require_ee()
        email = os.getenv("GEE_SERVICE_ACCOUNT_EMAIL")
        key = os.getenv("GEE_PRIVATE_KEY")
        if not email or not key:
            raise GEEAuthError("GEE_AUTH_FAILED", "Missing service account credentials")

        normalized_key = key.replace("\\n", "\n")
        try:
            return ee_module.ServiceAccountCredentials(email, normalized_key)
        except FileNotFoundError:
            from google.oauth2 import service_account

            return service_account.Credentials.from_service_account_info(
                {
                    "type": "service_account",
                    "client_email": email,
                    "private_key": normalized_key,
                    "token_uri": "https://oauth2.googleapis.com/token",
                },
                scopes=["https://www.googleapis.com/auth/earthengine"],
            )

    def _build_oauth_credentials(self) -> object:
        client_id = os.getenv("GEE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GEE_OAUTH_CLIENT_SECRET")
        refresh_token = os.getenv("GEE_OAUTH_REFRESH_TOKEN")
        if not client_id or not client_secret or not refresh_token:
            raise GEEAuthError("GEE_AUTH_FAILED", "Missing OAuth credentials")

        from google.oauth2.credentials import Credentials

        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )

    def _run_health_probe(self) -> None:
        ee_module = self._require_ee()
        try:
            ee_module.Number(1).getInfo()
        except Exception as exc:
            raise self._map_sdk_error(exc) from exc

    def _require_ee(self) -> "EEModuleProtocol":
        if self._ee is None:
            raise GEEUnavailableError(
                "GEE_INTERNAL", "Earth Engine SDK unavailable", retryable=False
            )
        return self._ee

    def _map_sdk_error(self, exc: Exception) -> GEEAuthError | GEEUnavailableError:
        message = self._sanitize_error_message(str(exc))
        if self._is_auth_error(exc):
            return GEEAuthError("GEE_AUTH_FAILED", message)
        if self._is_transient_error(exc):
            return GEEUnavailableError("GEE_UNAVAILABLE", message, retryable=True)
        return GEEUnavailableError("GEE_INTERNAL", message, retryable=False)

    def _is_auth_error(self, exc: Exception) -> bool:
        text = f"{type(exc).__name__} {exc}".lower()
        auth_tokens = (
            "permission",
            "forbidden",
            "unauthorized",
            "authentication",
            "credential",
            "401",
            "403",
        )
        return any(token in text for token in auth_tokens)

    def _is_transient_error(self, exc: Exception) -> bool:
        text = f"{type(exc).__name__} {exc}".lower()
        transient_tokens = (
            "timeout",
            "timed out",
            "unavailable",
            "deadline",
            "temporarily",
            "rate limit",
            "429",
            "503",
        )
        return any(token in text for token in transient_tokens)

    def _sanitize_error_message(self, message: str) -> str:
        lowered = message.lower()
        sensitive_tokens = (
            "token",
            "secret",
            "private key",
            "private_key",
            "authorization",
            "bearer",
        )
        if any(token in lowered for token in sensitive_tokens):
            return "Earth Engine error details redacted"
        cleaned = message.strip()
        if not cleaned:
            return "Earth Engine operation failed"
        return cleaned


class _EENumberProtocol(Protocol):
    def getInfo(self) -> object: ...


class EEModuleProtocol(Protocol):
    ServiceAccountCredentials: Any
    Number: Any

    def Initialize(
        self, credentials: object = None, project: str | None = None
    ) -> None: ...
