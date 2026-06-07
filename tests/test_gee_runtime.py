import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from agro_gee_api.services.gee_client import GEEAuthError, GEEUnavailableError
from agro_gee_api.services.gee_runtime import GEERuntime


class FakeNumber:
    def __init__(self, ee: Any) -> None:
        self._ee = ee

    def getInfo(self) -> int:
        self._ee.probe_calls += 1
        if self._ee.probe_error is not None:
            raise self._ee.probe_error
        return 1


class FakeEE:
    class ServiceAccountCredentials:
        def __init__(self, email: str, key_data: str) -> None:
            self.email = email
            self.key_data = key_data

    def __init__(self) -> None:
        self.init_calls: list[tuple[object, str | None]] = []
        self.init_error: Exception | None = None
        self.probe_calls = 0
        self.probe_error: Exception | None = None
        self.init_lock = threading.Lock()

    def Initialize(
        self, credentials: object = None, project: str | None = None
    ) -> None:
        with self.init_lock:
            self.init_calls.append((credentials, project))
            if self.init_error is not None:
                raise self.init_error

    def Number(self, value: int) -> FakeNumber:
        assert value == 1
        return FakeNumber(self)


def test_service_account_mode_requires_service_account_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEE_AUTH_MODE", "service_account")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_EMAIL", raising=False)
    monkeypatch.delenv("GEE_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("GEE_OAUTH_CLIENT_ID", "oauth-id")
    monkeypatch.setenv("GEE_OAUTH_CLIENT_SECRET", "oauth-secret")
    monkeypatch.setenv("GEE_OAUTH_REFRESH_TOKEN", "oauth-refresh")

    runtime = GEERuntime(ee_module=FakeEE())

    with pytest.raises(GEEAuthError) as exc:
        runtime.ensure_initialized()

    assert exc.value.error_code == "GEE_AUTH_FAILED"


def test_oauth_mode_requires_oauth_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEE_AUTH_MODE", "oauth")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.delenv("GEE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GEE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GEE_OAUTH_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )

    runtime = GEERuntime(ee_module=FakeEE())

    with pytest.raises(GEEAuthError) as exc:
        runtime.ensure_initialized()

    assert exc.value.error_code == "GEE_AUTH_FAILED"


def test_project_id_is_required_in_all_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEE_AUTH_MODE", raising=False)
    monkeypatch.delenv("GEE_PROJECT_ID", raising=False)
    monkeypatch.setenv("GEE_OAUTH_CLIENT_ID", "oauth-id")
    monkeypatch.setenv("GEE_OAUTH_CLIENT_SECRET", "oauth-secret")
    monkeypatch.setenv("GEE_OAUTH_REFRESH_TOKEN", "oauth-refresh")

    runtime = GEERuntime(ee_module=FakeEE())

    with pytest.raises(GEEAuthError) as exc:
        runtime.ensure_initialized()

    assert exc.value.error_code == "GEE_AUTH_FAILED"


def test_auto_mode_falls_back_to_oauth_when_service_account_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ee = FakeEE()
    oauth_credentials = object()
    monkeypatch.delenv("GEE_AUTH_MODE", raising=False)
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_EMAIL", raising=False)
    monkeypatch.delenv("GEE_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("GEE_OAUTH_CLIENT_ID", "oauth-id")
    monkeypatch.setenv("GEE_OAUTH_CLIENT_SECRET", "oauth-secret")
    monkeypatch.setenv("GEE_OAUTH_REFRESH_TOKEN", "oauth-refresh")

    runtime = GEERuntime(ee_module=fake_ee)
    monkeypatch.setattr(runtime, "_build_oauth_credentials", lambda: oauth_credentials)

    runtime.ensure_initialized()

    assert len(fake_ee.init_calls) == 1
    assert fake_ee.init_calls[0] == (oauth_credentials, "project-1")


def test_oauth_import_error_is_wrapped_in_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ee = FakeEE()
    monkeypatch.setenv("GEE_AUTH_MODE", "oauth")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.setenv("GEE_OAUTH_CLIENT_ID", "oauth-id")
    monkeypatch.setenv("GEE_OAUTH_CLIENT_SECRET", "oauth-secret")
    monkeypatch.setenv("GEE_OAUTH_REFRESH_TOKEN", "oauth-refresh")

    runtime = GEERuntime(ee_module=fake_ee)

    def raise_import_error() -> object:
        raise ImportError("google.oauth2 missing")

    monkeypatch.setattr(runtime, "_build_oauth_credentials", raise_import_error)

    with pytest.raises(GEEUnavailableError) as exc:
        runtime.ensure_initialized()

    assert exc.value.error_code == "GEE_INTERNAL"
    assert exc.value.retryable is False


def test_auto_mode_oauth_import_error_is_wrapped_in_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ee = FakeEE()
    monkeypatch.delenv("GEE_AUTH_MODE", raising=False)
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_EMAIL", raising=False)
    monkeypatch.delenv("GEE_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("GEE_OAUTH_CLIENT_ID", "oauth-id")
    monkeypatch.setenv("GEE_OAUTH_CLIENT_SECRET", "oauth-secret")
    monkeypatch.setenv("GEE_OAUTH_REFRESH_TOKEN", "oauth-refresh")

    runtime = GEERuntime(ee_module=fake_ee)

    def raise_import_error() -> object:
        raise ImportError("google.oauth2 missing")

    monkeypatch.setattr(runtime, "_build_oauth_credentials", raise_import_error)

    with pytest.raises(GEEUnavailableError) as exc:
        runtime.ensure_initialized()

    assert exc.value.error_code == "GEE_INTERNAL"
    assert exc.value.retryable is False


def test_private_key_normalizes_escaped_newlines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ee = FakeEE()
    monkeypatch.setenv("GEE_AUTH_MODE", "service_account")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )

    runtime = GEERuntime(ee_module=fake_ee)
    runtime.ensure_initialized()

    credentials, _ = fake_ee.init_calls[0]
    assert isinstance(credentials, FakeEE.ServiceAccountCredentials)
    assert (
        credentials.key_data
        == "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    )


def test_service_account_fallback_uses_credentials_from_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RaisesFileEE:
        class ServiceAccountCredentials:
            def __init__(self, email: str, key_data: str) -> None:
                raise FileNotFoundError(key_data)

        def __init__(self) -> None:
            self.init_calls: list[tuple[object, str | None]] = []
            self.probe_calls = 0
            self.probe_error: Exception | None = None

        def Initialize(
            self, credentials: object = None, project: str | None = None
        ) -> None:
            self.init_calls.append((credentials, project))

        def Number(self, value: int) -> FakeNumber:
            assert value == 1
            return FakeNumber(self)

    fake_ee = RaisesFileEE()
    monkeypatch.setenv("GEE_AUTH_MODE", "service_account")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )

    sentinel_credentials = object()

    class FakeServiceAccountFactory:
        captured_info: dict[str, str] | None = None
        captured_scopes: list[str] | None = None

        @staticmethod
        def from_service_account_info(
            info: dict[str, str], scopes: list[str] | None = None
        ) -> object:
            FakeServiceAccountFactory.captured_info = info
            FakeServiceAccountFactory.captured_scopes = scopes
            return sentinel_credentials

    monkeypatch.setattr(
        "google.oauth2.service_account.Credentials",
        FakeServiceAccountFactory,
    )

    runtime = GEERuntime(ee_module=fake_ee)
    runtime.ensure_initialized()

    credentials, project = fake_ee.init_calls[0]
    assert credentials is sentinel_credentials
    assert project == "project-1"
    assert FakeServiceAccountFactory.captured_info is not None
    assert (
        FakeServiceAccountFactory.captured_info["private_key"]
        == "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    )
    assert FakeServiceAccountFactory.captured_scopes == [
        "https://www.googleapis.com/auth/earthengine"
    ]


def test_force_recheck_runs_health_probe_again(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ee = FakeEE()
    monkeypatch.setenv("GEE_AUTH_MODE", "service_account")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )

    runtime = GEERuntime(ee_module=fake_ee)

    runtime.ensure_initialized()
    runtime.ensure_initialized(force_recheck=True)

    assert len(fake_ee.init_calls) == 1
    assert fake_ee.probe_calls == 2


def test_concurrent_calls_initialize_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ee = FakeEE()
    monkeypatch.setenv("GEE_AUTH_MODE", "service_account")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )

    runtime = GEERuntime(ee_module=fake_ee)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(runtime.ensure_initialized) for _ in range(25)]
        for future in futures:
            future.result()

    assert len(fake_ee.init_calls) == 1


def test_transient_probe_error_does_not_poison_initialized_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ee = FakeEE()
    monkeypatch.setenv("GEE_AUTH_MODE", "service_account")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )

    runtime = GEERuntime(ee_module=fake_ee)
    runtime.ensure_initialized()
    assert fake_ee.probe_calls == 1

    fake_ee.probe_error = TimeoutError("token=abc timeout")
    with pytest.raises(GEEUnavailableError) as exc:
        runtime.ensure_initialized(force_recheck=True)
    assert exc.value.retryable is True
    assert fake_ee.probe_calls == 2

    fake_ee.probe_error = None
    runtime.ensure_initialized(force_recheck=True)
    assert fake_ee.probe_calls == 3
    assert len(fake_ee.init_calls) == 1


def test_unknown_sdk_errors_map_to_internal_error_and_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ee = FakeEE()
    monkeypatch.setenv("GEE_AUTH_MODE", "service_account")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )

    runtime = GEERuntime(ee_module=fake_ee)
    runtime.ensure_initialized()

    fake_ee.probe_error = RuntimeError(
        "boom token=abc123 refresh_token=zzz private key leaked"
    )
    with pytest.raises(GEEUnavailableError) as exc:
        runtime.ensure_initialized(force_recheck=True)

    assert exc.value.error_code == "GEE_INTERNAL"
    assert exc.value.retryable is False
    message = exc.value.message.lower()
    assert "token" not in message
    assert "private key" not in message
    assert "abc123" not in message


def test_initialize_auth_error_maps_to_auth_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ee = FakeEE()
    fake_ee.init_error = RuntimeError("Permission denied for ee.Initialize")
    monkeypatch.setenv("GEE_AUTH_MODE", "service_account")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )

    runtime = GEERuntime(ee_module=fake_ee)

    with pytest.raises(GEEAuthError) as exc:
        runtime.ensure_initialized()

    assert exc.value.error_code == "GEE_AUTH_FAILED"


def test_probe_auth_error_maps_to_auth_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ee = FakeEE()
    monkeypatch.setenv("GEE_AUTH_MODE", "service_account")
    monkeypatch.setenv("GEE_PROJECT_ID", "project-1")
    monkeypatch.setenv(
        "GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com"
    )
    monkeypatch.setenv(
        "GEE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )

    runtime = GEERuntime(ee_module=fake_ee)
    runtime.ensure_initialized()

    fake_ee.probe_error = RuntimeError("Unauthorized during probe")
    with pytest.raises(GEEAuthError) as exc:
        runtime.ensure_initialized(force_recheck=True)

    assert exc.value.error_code == "GEE_AUTH_FAILED"
