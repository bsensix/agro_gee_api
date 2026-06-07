from typing import Mapping, Sequence

from agro_gee_api.routes._authz import get_authz_context


class _FakeCursor:
    def __init__(
        self,
        allowed_rows: Sequence[Mapping[str, object]],
        role_row: Mapping[str, object],
    ) -> None:
        self._allowed_rows = allowed_rows
        self._role_row = role_row
        self._execute_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self._execute_count += 1

    def fetchall(self) -> Sequence[Mapping[str, object]]:
        return self._allowed_rows

    def fetchone(self) -> Mapping[str, object]:
        return self._role_row


class _FakeConnection:
    def __init__(
        self,
        allowed_rows: Sequence[Mapping[str, object]],
        role_row: Mapping[str, object],
    ) -> None:
        self._allowed_rows = allowed_rows
        self._role_row = role_row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._allowed_rows, self._role_row)


def test_get_authz_context_reads_dict_rows_and_role_from_db(monkeypatch) -> None:
    allowed_rows = [{"user_id": 1}, {"user_id": 8}]
    role_row = {"role": "admin"}

    monkeypatch.setattr(
        "agro_gee_api.routes._authz.get_connection",
        lambda: _FakeConnection(allowed_rows, role_row),
    )

    context = get_authz_context(x_user_id="1")

    assert context.allowed_user_ids == (1, 8)
    assert context.requester_role == "admin"
