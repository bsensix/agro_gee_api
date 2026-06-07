from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agro_gee_api.main import app


pytestmark = pytest.mark.integration


def _multi_polygon() -> dict[str, object]:
    return {
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [-47.0, -15.0],
                    [-46.9, -15.0],
                    [-46.9, -15.1],
                    [-47.0, -15.1],
                    [-47.0, -15.0],
                ]
            ]
        ],
    }


def _small_polygon() -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [-47.0, -15.0],
                [-46.999, -15.0],
                [-46.999, -15.001],
                [-47.0, -15.001],
                [-47.0, -15.0],
            ]
        ],
    }


def _large_polygon() -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [-47.0, -15.0],
                [-46.996, -15.0],
                [-46.996, -15.004],
                [-47.0, -15.004],
                [-47.0, -15.0],
            ]
        ],
    }


def _invalid_polygon() -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [-47.0, -15.0],
                [-46.999, -15.001],
                [-47.0, -15.001],
                [-46.999, -15.0],
                [-47.0, -15.0],
            ]
        ],
    }


def _point() -> dict[str, object]:
    return {"type": "Point", "coordinates": [-47.0, -15.0]}


def _geometry_with_crs_code(
    geometry: dict[str, object],
    *,
    code: str,
) -> dict[str, object]:
    geometry_with_crs = dict(geometry)
    geometry_with_crs["crs"] = {
        "type": "name",
        "properties": {"code": code},
    }
    return geometry_with_crs


def _auth_headers(*, user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


def _create_user(client: TestClient, *, suffix: str) -> int:
    response = client.post(
        "/users",
        json={
            "name": f"User {suffix}",
            "email": f"user.{suffix}@example.com",
            "role": "owner",
        },
    )
    assert response.status_code == 201
    return response.json()["user_id"]


def _create_farm(client: TestClient, *, user_id: int, suffix: str) -> dict[str, Any]:
    response = client.post(
        "/farms",
        headers=_auth_headers(user_id=user_id),
        json={
            "user_id": user_id,
            "name": f"Farm {suffix}",
            "geometry": _small_polygon(),
        },
    )
    assert response.status_code == 201
    return response.json()


def _assert_farm_geometry_unchanged(
    client: TestClient,
    *,
    requester_user_id: int,
    farm_id: int,
    expected_geometry: dict[str, Any],
    expected_area: Any,
) -> None:
    persisted = client.get(
        f"/farms/{farm_id}", headers=_auth_headers(user_id=requester_user_id)
    )
    assert persisted.status_code == 200
    assert persisted.json()["geometry"] == expected_geometry
    assert persisted.json()["area_ha"] == expected_area


def _assert_field_geometry_unchanged(
    client: TestClient,
    *,
    requester_user_id: int,
    field_id: int,
    expected_geometry: dict[str, Any],
    expected_area: Any,
) -> None:
    persisted = client.get(
        f"/fields/{field_id}", headers=_auth_headers(user_id=requester_user_id)
    )
    assert persisted.status_code == 200
    assert persisted.json()["geometry"] == expected_geometry
    assert persisted.json()["area_ha"] == expected_area


def test_users_full_crud_flow(clean_core_tables: None) -> None:
    client = TestClient(app)

    create_response = client.post(
        "/users",
        json={"name": "Maria", "email": "maria@example.com", "role": "admin"},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    user_id = created["user_id"]
    assert created["name"] == "Maria"

    list_response = client.get("/users")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["user_id"] == user_id

    get_response = client.get(f"/users/{user_id}")
    assert get_response.status_code == 200
    assert get_response.json()["email"] == "maria@example.com"

    update_response = client.put(
        f"/users/{user_id}",
        json={
            "name": "Maria Silva",
            "email": "maria.silva@example.com",
            "role": "manager",
            "parent_user_id": None,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Maria Silva"

    delete_response = client.delete(f"/users/{user_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/users/{user_id}")
    assert missing_response.status_code == 404


def test_farms_full_crud_flow(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={"name": "Joao", "email": "joao@example.com", "role": "owner"},
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))

    create_response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda Norte",
            "geometry": _small_polygon(),
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    farm_id = created["farm_id"]
    assert created["geometry"]["type"] == "MultiPolygon"
    created_area = created["area_ha"]
    assert float(created_area) > 0

    list_response = client.get("/farms")
    assert list_response.status_code == 200
    assert list_response.json()[0]["farm_id"] == farm_id

    get_response = client.get(f"/farms/{farm_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Fazenda Norte"
    assert get_response.json()["area_ha"] == created_area

    update_response = client.put(
        f"/farms/{farm_id}",
        json={
            "user_id": user_id,
            "name": "Fazenda Norte Atualizada",
            "geometry": _large_polygon(),
            "area_ha": 0.0001,
        },
    )
    assert update_response.status_code == 200
    updated_area = update_response.json()["area_ha"]
    assert float(updated_area) > float(created_area)

    list_after_update_response = client.get("/farms")
    assert list_after_update_response.status_code == 200
    assert list_after_update_response.json()[0]["area_ha"] == updated_area

    delete_response = client.delete(f"/farms/{farm_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/farms/{farm_id}")
    assert missing_response.status_code == 404


def test_fields_full_crud_flow(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={"name": "Ana", "email": "ana@example.com", "role": "owner"},
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))
    farm_response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda Sul",
            "geometry": _multi_polygon(),
        },
    )
    farm_id = farm_response.json()["farm_id"]

    create_response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Talhao 01",
            "geometry": _small_polygon(),
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    field_id = created["field_id"]
    assert created["name"] == "Talhao 01"
    created_area = created["area_ha"]
    assert float(created_area) > 0

    list_response = client.get("/fields")
    assert list_response.status_code == 200
    assert list_response.json()[0]["field_id"] == field_id

    get_response = client.get(f"/fields/{field_id}")
    assert get_response.status_code == 200
    assert get_response.json()["farm_id"] == farm_id
    assert get_response.json()["area_ha"] == created_area

    update_response = client.put(
        f"/fields/{field_id}",
        json={
            "farm_id": farm_id,
            "name": "Talhao 01 B",
            "geometry": _large_polygon(),
            "area_ha": 99999.9999,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Talhao 01 B"
    updated_area = update_response.json()["area_ha"]
    assert float(updated_area) > float(created_area)

    list_after_update_response = client.get("/fields")
    assert list_after_update_response.status_code == 200
    assert list_after_update_response.json()[0]["area_ha"] == updated_area

    delete_response = client.delete(f"/fields/{field_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/fields/{field_id}")
    assert missing_response.status_code == 404


def test_users_unique_violation_returns_409(clean_core_tables: None) -> None:
    client = TestClient(app)

    first_response = client.post(
        "/users",
        json={"name": "User A", "email": "unique@example.com", "role": "owner"},
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/users",
        json={"name": "User B", "email": "unique@example.com", "role": "owner"},
    )
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Resource already exists"}


def test_farm_fk_violation_returns_400(clean_core_tables: None) -> None:
    client = TestClient(app)

    requester = client.post(
        "/users",
        json={"name": "Requester", "email": "requester@example.com", "role": "owner"},
    )
    requester_id = requester.json()["user_id"]

    response = client.post(
        "/farms",
        headers={"X-User-Id": str(requester_id)},
        json={
            "user_id": 9999,
            "name": "Fazenda Sem Dono",
            "geometry": _multi_polygon(),
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Referenced resource not found"}


def test_delete_user_with_existing_farm_returns_400(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={"name": "Farm Owner", "email": "owner@example.com", "role": "owner"},
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))

    farm_response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda Dependente",
            "geometry": _multi_polygon(),
        },
    )
    assert farm_response.status_code == 201

    delete_response = client.delete(f"/users/{user_id}")
    assert delete_response.status_code == 400
    assert delete_response.json() == {"detail": "Referenced resource not found"}


def test_delete_farm_with_existing_field_returns_400(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={
            "name": "Field Owner",
            "email": "field.owner@example.com",
            "role": "owner",
        },
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))

    farm_response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda com Talhao",
            "geometry": _multi_polygon(),
        },
    )
    farm_id = farm_response.json()["farm_id"]

    field_response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Talhao Dependente",
            "geometry": _multi_polygon(),
        },
    )
    assert field_response.status_code == 201

    delete_response = client.delete(f"/farms/{farm_id}")
    assert delete_response.status_code == 400
    assert delete_response.json() == {"detail": "Referenced resource not found"}


def test_users_check_violation_returns_400(clean_core_tables: None) -> None:
    client = TestClient(app)

    response = client.post(
        "/users",
        json={"name": "", "email": "check@example.com", "role": "owner"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request data"}


def test_farm_rejects_non_polygon_geometry_type(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={"name": "Geo User", "email": "geo@example.com", "role": "owner"},
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))

    bad_geometry_response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda Ponto",
            "geometry": _point(),
        },
    )
    assert bad_geometry_response.status_code == 400


def test_farm_rejects_invalid_polygon(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={"name": "Geo User 2", "email": "geo2@example.com", "role": "owner"},
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))

    bad_geometry_response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda Invalida",
            "geometry": _invalid_polygon(),
        },
    )
    assert bad_geometry_response.status_code == 400


def test_farm_create_rejects_non_4326_crs(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={"name": "Geo CRS User", "email": "geocrs@example.com", "role": "owner"},
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))

    geometry = _multi_polygon()
    geometry["crs"] = {
        "type": "name",
        "properties": {"name": "EPSG:3857"},
    }
    response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda CRS Invalido",
            "geometry": geometry,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid geometry CRS; only EPSG:4326 is supported"
    }


def test_field_rejects_non_polygon_geometry_type(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={"name": "Field User", "email": "fieldgeo@example.com", "role": "owner"},
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))
    farm_response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda Base",
            "geometry": _multi_polygon(),
        },
    )
    farm_id = farm_response.json()["farm_id"]

    bad_geometry_response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Talhao Ponto",
            "geometry": _point(),
        },
    )
    assert bad_geometry_response.status_code == 400


def test_field_rejects_invalid_polygon(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={
            "name": "Field User 2",
            "email": "fieldgeo2@example.com",
            "role": "owner",
        },
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))
    farm_response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda Base 2",
            "geometry": _multi_polygon(),
        },
    )
    farm_id = farm_response.json()["farm_id"]

    bad_geometry_response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Talhao Invalido",
            "geometry": _invalid_polygon(),
        },
    )
    assert bad_geometry_response.status_code == 400


def test_field_create_rejects_non_4326_crs(clean_core_tables: None) -> None:
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={
            "name": "Field CRS User",
            "email": "fieldcrs@example.com",
            "role": "owner",
        },
    )
    user_id = user_response.json()["user_id"]
    client.headers.update(_auth_headers(user_id=user_id))
    farm_response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Fazenda Field CRS",
            "geometry": _multi_polygon(),
        },
    )
    farm_id = farm_response.json()["farm_id"]

    geometry = _small_polygon()
    geometry["crs"] = {
        "type": "name",
        "properties": {"name": "urn:ogc:def:crs:EPSG::3857"},
    }
    response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Talhao CRS Invalido",
            "geometry": geometry,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid geometry CRS; only EPSG:4326 is supported"
    }


def test_farm_update_rejects_point_geometry_and_keeps_geometry_unchanged(
    clean_core_tables: None,
) -> None:
    client = TestClient(app)
    user_id = _create_user(client, suffix="farm-update-point")
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client,
        user_id=user_id,
        suffix="update-point-base",
    )
    farm_id = int(created_farm["farm_id"])
    original_geometry = created_farm["geometry"]
    original_area = created_farm["area_ha"]

    response = client.put(
        f"/farms/{farm_id}",
        json={
            "user_id": user_id,
            "name": "Farm Update Point",
            "geometry": _point(),
        },
    )

    assert response.status_code == 400
    _assert_farm_geometry_unchanged(
        client,
        requester_user_id=user_id,
        farm_id=farm_id,
        expected_geometry=original_geometry,
        expected_area=original_area,
    )


def test_farm_update_rejects_invalid_polygon_and_keeps_geometry_unchanged(
    clean_core_tables: None,
) -> None:
    client = TestClient(app)
    user_id = _create_user(client, suffix="farm-update-invalid")
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client,
        user_id=user_id,
        suffix="update-invalid-base",
    )
    farm_id = int(created_farm["farm_id"])
    original_geometry = created_farm["geometry"]
    original_area = created_farm["area_ha"]

    response = client.put(
        f"/farms/{farm_id}",
        json={
            "user_id": user_id,
            "name": "Farm Update Invalid",
            "geometry": _invalid_polygon(),
        },
    )

    assert response.status_code == 400
    _assert_farm_geometry_unchanged(
        client,
        requester_user_id=user_id,
        farm_id=farm_id,
        expected_geometry=original_geometry,
        expected_area=original_area,
    )


def test_farm_update_rejects_non_4326_crs_and_keeps_geometry_unchanged(
    clean_core_tables: None,
) -> None:
    client = TestClient(app)
    user_id = _create_user(client, suffix="farm-update-crs")
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client,
        user_id=user_id,
        suffix="update-crs-base",
    )
    farm_id = int(created_farm["farm_id"])
    original_geometry = created_farm["geometry"]
    original_area = created_farm["area_ha"]

    geometry = _small_polygon()
    geometry["crs"] = {
        "type": "name",
        "properties": {"name": "EPSG:3857"},
    }
    response = client.put(
        f"/farms/{farm_id}",
        json={
            "user_id": user_id,
            "name": "Farm Update CRS",
            "geometry": geometry,
        },
    )

    assert response.status_code == 400
    _assert_farm_geometry_unchanged(
        client,
        requester_user_id=user_id,
        farm_id=farm_id,
        expected_geometry=original_geometry,
        expected_area=original_area,
    )


def test_field_update_rejects_point_geometry_and_keeps_geometry_unchanged(
    clean_core_tables: None,
) -> None:
    client = TestClient(app)
    user_id = _create_user(client, suffix="field-update-point")
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client,
        user_id=user_id,
        suffix="field-update-point-farm",
    )
    farm_id = int(created_farm["farm_id"])

    create_field_response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Field Base Point",
            "geometry": _small_polygon(),
        },
    )
    assert create_field_response.status_code == 201
    created_field = create_field_response.json()
    field_id = int(created_field["field_id"])
    original_geometry = created_field["geometry"]
    original_area = created_field["area_ha"]

    response = client.put(
        f"/fields/{field_id}",
        json={
            "farm_id": farm_id,
            "name": "Field Update Point",
            "geometry": _point(),
        },
    )

    assert response.status_code == 400
    _assert_field_geometry_unchanged(
        client,
        requester_user_id=user_id,
        field_id=field_id,
        expected_geometry=original_geometry,
        expected_area=original_area,
    )


def test_field_update_rejects_invalid_polygon_and_keeps_geometry_unchanged(
    clean_core_tables: None,
) -> None:
    client = TestClient(app)
    user_id = _create_user(client, suffix="field-update-invalid")
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client,
        user_id=user_id,
        suffix="field-update-invalid-farm",
    )
    farm_id = int(created_farm["farm_id"])

    create_field_response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Field Base Invalid",
            "geometry": _small_polygon(),
        },
    )
    assert create_field_response.status_code == 201
    created_field = create_field_response.json()
    field_id = int(created_field["field_id"])
    original_geometry = created_field["geometry"]
    original_area = created_field["area_ha"]

    response = client.put(
        f"/fields/{field_id}",
        json={
            "farm_id": farm_id,
            "name": "Field Update Invalid",
            "geometry": _invalid_polygon(),
        },
    )

    assert response.status_code == 400
    _assert_field_geometry_unchanged(
        client,
        requester_user_id=user_id,
        field_id=field_id,
        expected_geometry=original_geometry,
        expected_area=original_area,
    )


def test_field_update_rejects_non_4326_crs_and_keeps_geometry_unchanged(
    clean_core_tables: None,
) -> None:
    client = TestClient(app)
    user_id = _create_user(client, suffix="field-update-crs")
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client,
        user_id=user_id,
        suffix="field-update-crs-farm",
    )
    farm_id = int(created_farm["farm_id"])

    create_field_response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Field Base CRS",
            "geometry": _small_polygon(),
        },
    )
    assert create_field_response.status_code == 201
    created_field = create_field_response.json()
    field_id = int(created_field["field_id"])
    original_geometry = created_field["geometry"]
    original_area = created_field["area_ha"]

    geometry = _small_polygon()
    geometry["crs"] = {
        "type": "name",
        "properties": {"name": "urn:ogc:def:crs:EPSG::3857"},
    }
    response = client.put(
        f"/fields/{field_id}",
        json={
            "farm_id": farm_id,
            "name": "Field Update CRS",
            "geometry": geometry,
        },
    )

    assert response.status_code == 400
    _assert_field_geometry_unchanged(
        client,
        requester_user_id=user_id,
        field_id=field_id,
        expected_geometry=original_geometry,
        expected_area=original_area,
    )


@pytest.mark.parametrize(
    "code",
    [
        "4326",
        "EPSG:4326",
        "epsg:4326",
        "UrN:OgC:DeF:CrS:ePsG::4326",
        "HTTP://WWW.OPENGIS.NET/DEF/CRS/EPSG/0/4326",
    ],
)
def test_farm_create_accepts_crs_properties_code_4326_variants(
    clean_core_tables: None,
    code: str,
) -> None:
    client = TestClient(app)
    user_id = _create_user(
        client,
        suffix=f"farm-create-code-{code.lower().replace(':', '-').replace('/', '-')}",
    )
    client.headers.update(_auth_headers(user_id=user_id))

    response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Farm CRS Code Accepted",
            "geometry": _geometry_with_crs_code(_small_polygon(), code=code),
        },
    )

    assert response.status_code == 201


@pytest.mark.parametrize("code", ["3857", "EPSG:3857", "urn:ogc:def:crs:EPSG::3857"])
def test_farm_create_rejects_crs_properties_code_non_4326(
    clean_core_tables: None,
    code: str,
) -> None:
    client = TestClient(app)
    user_id = _create_user(
        client,
        suffix=f"farm-create-code-reject-{code.lower().replace(':', '-').replace('/', '-')}",
    )
    client.headers.update(_auth_headers(user_id=user_id))

    response = client.post(
        "/farms",
        json={
            "user_id": user_id,
            "name": "Farm CRS Code Rejected",
            "geometry": _geometry_with_crs_code(_small_polygon(), code=code),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid geometry CRS; only EPSG:4326 is supported"
    }


@pytest.mark.parametrize(
    "code",
    [
        "4326",
        "EPSG:4326",
        "urn:ogc:def:crs:EPSG::4326",
        "http://www.opengis.net/def/crs/epsg/0/4326",
    ],
)
def test_farm_update_accepts_crs_properties_code_4326_variants(
    clean_core_tables: None,
    code: str,
) -> None:
    client = TestClient(app)
    user_id = _create_user(
        client,
        suffix=f"farm-update-code-{code.lower().replace(':', '-').replace('/', '-')}",
    )
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(client, user_id=user_id, suffix="farm-update-code-base")
    farm_id = int(created_farm["farm_id"])
    created_area = created_farm["area_ha"]

    response = client.put(
        f"/farms/{farm_id}",
        json={
            "user_id": user_id,
            "name": "Farm Update CRS Code Accepted",
            "geometry": _geometry_with_crs_code(_large_polygon(), code=code),
        },
    )

    assert response.status_code == 200
    assert float(response.json()["area_ha"]) > float(created_area)


@pytest.mark.parametrize("code", ["3857", "EPSG:3857", "urn:ogc:def:crs:epsg::3857"])
def test_farm_update_rejects_crs_properties_code_non_4326_and_keeps_geometry_unchanged(
    clean_core_tables: None,
    code: str,
) -> None:
    client = TestClient(app)
    user_id = _create_user(
        client,
        suffix=f"farm-update-code-reject-{code.lower().replace(':', '-').replace('/', '-')}",
    )
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client, user_id=user_id, suffix="farm-update-code-reject-base"
    )
    farm_id = int(created_farm["farm_id"])
    original_geometry = created_farm["geometry"]
    original_area = created_farm["area_ha"]

    response = client.put(
        f"/farms/{farm_id}",
        json={
            "user_id": user_id,
            "name": "Farm Update CRS Code Rejected",
            "geometry": _geometry_with_crs_code(_large_polygon(), code=code),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid geometry CRS; only EPSG:4326 is supported"
    }
    _assert_farm_geometry_unchanged(
        client,
        requester_user_id=user_id,
        farm_id=farm_id,
        expected_geometry=original_geometry,
        expected_area=original_area,
    )


@pytest.mark.parametrize(
    "code",
    [
        "4326",
        "EPSG:4326",
        "epsg:4326",
        "urn:ogc:def:crs:EPSG::4326",
        "http://www.opengis.net/def/crs/epsg/0/4326",
    ],
)
def test_field_create_accepts_crs_properties_code_4326_variants(
    clean_core_tables: None,
    code: str,
) -> None:
    client = TestClient(app)

    user_id = _create_user(
        client,
        suffix=f"field-create-code-{code.lower().replace(':', '-').replace('/', '-')}",
    )
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client, user_id=user_id, suffix="field-create-code-farm"
    )
    farm_id = int(created_farm["farm_id"])

    response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Field CRS Code Accepted",
            "geometry": _geometry_with_crs_code(_small_polygon(), code=code),
        },
    )

    assert response.status_code == 201


@pytest.mark.parametrize("code", ["3857", "EPSG:3857", "urn:ogc:def:crs:epsg::3857"])
def test_field_create_rejects_crs_properties_code_non_4326(
    clean_core_tables: None,
    code: str,
) -> None:
    client = TestClient(app)

    user_id = _create_user(
        client,
        suffix=f"field-create-code-reject-{code.lower().replace(':', '-').replace('/', '-')}",
    )
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client, user_id=user_id, suffix="field-create-code-reject-farm"
    )
    farm_id = int(created_farm["farm_id"])

    response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Field CRS Code Rejected",
            "geometry": _geometry_with_crs_code(_small_polygon(), code=code),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid geometry CRS; only EPSG:4326 is supported"
    }


@pytest.mark.parametrize(
    "code",
    [
        "4326",
        "EPSG:4326",
        "urn:ogc:def:crs:epsg::4326",
        "http://www.opengis.net/def/crs/epsg/0/4326",
    ],
)
def test_field_update_accepts_crs_properties_code_4326_variants(
    clean_core_tables: None,
    code: str,
) -> None:
    client = TestClient(app)
    user_id = _create_user(
        client,
        suffix=f"field-update-code-{code.lower().replace(':', '-').replace('/', '-')}",
    )
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client, user_id=user_id, suffix="field-update-code-farm"
    )
    farm_id = int(created_farm["farm_id"])

    create_field_response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Field Update Base Code",
            "geometry": _small_polygon(),
        },
    )
    assert create_field_response.status_code == 201
    created_field = create_field_response.json()
    field_id = int(created_field["field_id"])
    created_area = created_field["area_ha"]

    response = client.put(
        f"/fields/{field_id}",
        json={
            "farm_id": farm_id,
            "name": "Field Update CRS Code Accepted",
            "geometry": _geometry_with_crs_code(_large_polygon(), code=code),
        },
    )

    assert response.status_code == 200
    assert float(response.json()["area_ha"]) > float(created_area)


@pytest.mark.parametrize("code", ["3857", "EPSG:3857", "urn:ogc:def:crs:EPSG::3857"])
def test_field_update_rejects_crs_properties_code_non_4326_and_keeps_geometry_unchanged(
    clean_core_tables: None,
    code: str,
) -> None:
    client = TestClient(app)
    user_id = _create_user(
        client,
        suffix=f"field-update-code-reject-{code.lower().replace(':', '-').replace('/', '-')}",
    )
    client.headers.update(_auth_headers(user_id=user_id))
    created_farm = _create_farm(
        client, user_id=user_id, suffix="field-update-code-reject-farm"
    )
    farm_id = int(created_farm["farm_id"])

    create_field_response = client.post(
        "/fields",
        json={
            "farm_id": farm_id,
            "name": "Field Update Base Code Reject",
            "geometry": _small_polygon(),
        },
    )
    assert create_field_response.status_code == 201
    created_field = create_field_response.json()
    field_id = int(created_field["field_id"])
    original_geometry = created_field["geometry"]
    original_area = created_field["area_ha"]

    response = client.put(
        f"/fields/{field_id}",
        json={
            "farm_id": farm_id,
            "name": "Field Update CRS Code Rejected",
            "geometry": _geometry_with_crs_code(_large_polygon(), code=code),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid geometry CRS; only EPSG:4326 is supported"
    }
    _assert_field_geometry_unchanged(
        client,
        requester_user_id=user_id,
        field_id=field_id,
        expected_geometry=original_geometry,
        expected_area=original_area,
    )


def test_farms_list_requires_x_user_id_header(clean_core_tables: None) -> None:
    client = TestClient(app)

    response = client.get("/farms")

    assert response.status_code == 400
    assert response.json() == {"detail": "Missing X-User-Id header"}


def test_farm_get_returns_403_when_resource_is_outside_user_scope(
    clean_core_tables: None,
) -> None:
    client = TestClient(app)

    owner_response = client.post(
        "/users",
        json={"name": "Owner", "email": "owner.scope@example.com", "role": "owner"},
    )
    owner_id = owner_response.json()["user_id"]

    outsider_response = client.post(
        "/users",
        json={
            "name": "Outsider",
            "email": "outsider.scope@example.com",
            "role": "owner",
        },
    )
    outsider_id = outsider_response.json()["user_id"]

    farm_response = client.post(
        "/farms",
        headers={"X-User-Id": str(owner_id)},
        json={
            "user_id": owner_id,
            "name": "Owner Farm",
            "geometry": _small_polygon(),
        },
    )
    assert farm_response.status_code == 201
    farm_id = farm_response.json()["farm_id"]

    forbidden_response = client.get(
        f"/farms/{farm_id}", headers={"X-User-Id": str(outsider_id)}
    )
    assert forbidden_response.status_code == 403
    assert forbidden_response.json() == {"detail": "Forbidden"}


def _create_field(client: TestClient, *, farm_id: int, name: str, user_id: int) -> int:
    response = client.post(
        "/fields",
        headers={"X-User-Id": str(user_id)},
        json={"farm_id": farm_id, "name": name, "geometry": _small_polygon()},
    )
    assert response.status_code == 201
    return int(response.json()["field_id"])


def test_gee_stats_returns_403_for_out_of_scope_field(
    clean_core_tables: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ServiceOk:
        def compute(self, **_: object) -> object:
            class Result:
                dataset = "COPERNICUS/S2_SR_HARMONIZED"
                metric = "ndvi_mean"
                value = 0.5
                images_used = 3

            return Result()

    monkeypatch.setattr("agro_gee_api.routes.gee.get_sentinel2_service", lambda: ServiceOk())
    client = TestClient(app)

    owner_id = _create_user(client, suffix="gee-owner-403")
    outsider_id = _create_user(client, suffix="gee-outsider-403")
    farm = _create_farm(client, user_id=owner_id, suffix="gee-farm-403")
    field_id = _create_field(
        client,
        farm_id=int(farm["farm_id"]),
        name="Talhao Scope",
        user_id=owner_id,
    )

    response = client.post(
        "/gee/sentinel2/stats",
        headers={"X-User-Id": str(outsider_id)},
        json={
            "field_id": field_id,
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 404


def test_gee_stats_returns_404_for_missing_field(
    clean_core_tables: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ServiceOk:
        def compute(self, **_: object) -> object:
            class Result:
                dataset = "COPERNICUS/S2_SR_HARMONIZED"
                metric = "ndvi_mean"
                value = 0.5
                images_used = 3

            return Result()

    monkeypatch.setattr("agro_gee_api.routes.gee.get_sentinel2_service", lambda: ServiceOk())
    client = TestClient(app)
    requester_id = _create_user(client, suffix="gee-missing-404")

    response = client.post(
        "/gee/sentinel2/stats",
        headers={"X-User-Id": str(requester_id)},
        json={
            "field_id": 999999,
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 404


def test_gee_stats_returns_200_for_authorized_field(
    clean_core_tables: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ServiceOk:
        def compute(self, **_: object) -> object:
            class Result:
                dataset = "COPERNICUS/S2_SR_HARMONIZED"
                metric = "ndvi_mean"
                value = 0.64
                images_used = 5

            return Result()

    monkeypatch.setattr("agro_gee_api.routes.gee.get_sentinel2_service", lambda: ServiceOk())
    client = TestClient(app)

    owner_id = _create_user(client, suffix="gee-owner-200")
    farm = _create_farm(client, user_id=owner_id, suffix="gee-farm-200")
    field_id = _create_field(
        client,
        farm_id=int(farm["farm_id"]),
        name="Talhao OK",
        user_id=owner_id,
    )

    response = client.post(
        "/gee/sentinel2/stats",
        headers={"X-User-Id": str(owner_id)},
        json={
            "field_id": field_id,
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 404


def test_gee_datasets_returns_seeded_active_catalog(clean_core_tables: None) -> None:
    client = TestClient(app)

    response = client.get("/gee/datasets")

    assert response.status_code == 200
    assert response.json() == [
        {
            "dataset_id": "COPERNICUS/S2_SR_HARMONIZED",
            "provider": "gee",
            "title": "Sentinel-2 SR Harmonized",
            "bands": ["B2", "B3", "B4", "B8", "QA60"],
        }
    ]


def test_gee_extract_point_returns_200_with_mocked_service(
    clean_core_tables: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExtractService:
        def extract_point(self, **_: object) -> float:
            return 0.47

    monkeypatch.setattr("agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService())
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset": "COPERNICUS/S2_SR_HARMONIZED",
        "metric": "ndvi_mean",
        "value": 0.47,
        "series": [],
    }


def test_gee_extract_polygon_returns_200_with_mocked_service(
    clean_core_tables: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExtractService:
        def extract_polygon(self, **_: object) -> float:
            return 0.55

    monkeypatch.setattr("agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService())
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 200
    assert response.json()["value"] == 0.55


def test_gee_timeseries_returns_200_with_mocked_service(
    clean_core_tables: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExtractService:
        def timeseries(self, **_: object) -> list[dict[str, object]]:
            return [{"date": "2026-06-01", "value": 0.41}]

    monkeypatch.setattr("agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService())
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/timeseries",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 404


def test_gee_image_returns_200_with_mocked_service(
    clean_core_tables: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExtractService:
        def image(self, **_: object) -> str:
            return "https://example.com/gee/render.png"

    monkeypatch.setattr("agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService())
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/image",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 404


def test_gee_auth_test_smoke_with_monkeypatched_runtime(
    clean_core_tables: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    user_id = _create_user(client, suffix="gee-auth-smoke")

    monkeypatch.setenv("GEE_AUTH_TEST_ENABLED", "true")
    monkeypatch.setattr("agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True)
    monkeypatch.setattr("agro_gee_api.routes.gee.run_gee_auth_recheck", lambda: None)

    response = client.post("/gee/auth/test", headers={"X-User-Id": str(user_id)})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_gee_endpoint_error_contracts_use_runtime_client_factory(
    clean_core_tables: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RuntimeErrorClient:
        def ndvi_mean(self, **_: object) -> tuple[float | None, int]:
            raise Exception("ndvi_mean should not be called in this contract case")

        def extract_point(self, **_: object) -> float:
            raise Exception("extract_point should not be called in this contract case")

        def extract_polygon(self, **_: object) -> float:
            raise Exception(
                "extract_polygon should not be called in this contract case"
            )

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            raise Exception("timeseries should not be called in this contract case")

        def image(self, **_: object) -> str:
            raise Exception("image should not be called in this contract case")

    client = TestClient(app)
    owner_id = _create_user(client, suffix="gee-runtime-contracts")
    farm = _create_farm(client, user_id=owner_id, suffix="gee-runtime-contracts-farm")
    field_id = _create_field(
        client,
        farm_id=int(farm["farm_id"]),
        name="Talhao Runtime Contracts",
        user_id=owner_id,
    )

    class StatsInternalClient(RuntimeErrorClient):
        def ndvi_mean(self, **_: object) -> tuple[float | None, int]:
            from agro_gee_api.services.gee_client import GEEUnavailableError

            raise GEEUnavailableError(
                "GEE_INTERNAL", "runtime internal", retryable=False
            )

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_gee_client",
        lambda: StatsInternalClient(),
        raising=False,
    )
    stats_response = client.post(
        "/gee/sentinel2/stats",
        headers={"X-User-Id": str(owner_id)},
        json={
            "field_id": field_id,
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )
    assert stats_response.status_code == 404

    class PointAuthClient(RuntimeErrorClient):
        def extract_point(self, **_: object) -> float:
            from agro_gee_api.services.gee_client import GEEAuthError

            raise GEEAuthError("GEE_AUTH_FAILED", "runtime auth failed")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_gee_client",
        lambda: PointAuthClient(),
        raising=False,
    )
    point_response = client.post(
        "/gee/sentinel2/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )
    assert point_response.status_code == 500
    assert point_response.json()["error_code"] == "GEE_AUTH_FAILED"

    class PolygonUnavailableClient(RuntimeErrorClient):
        def extract_polygon(self, **_: object) -> float:
            from agro_gee_api.services.gee_client import GEEUnavailableError

            raise GEEUnavailableError(
                "GEE_UNAVAILABLE", "runtime unavailable", retryable=True
            )

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_gee_client",
        lambda: PolygonUnavailableClient(),
        raising=False,
    )
    polygon_response = client.post(
        "/gee/sentinel2/extract/polygon",
        json={
            "geometry": _small_polygon(),
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )
    assert polygon_response.status_code == 503
    assert polygon_response.json()["error_code"] == "GEE_UNAVAILABLE"

    class TimeseriesTimeoutClient(RuntimeErrorClient):
        def timeseries(self, **_: object) -> list[dict[str, object]]:
            from agro_gee_api.services.gee_client import GEEUnavailableError

            raise GEEUnavailableError("GEE_TIMEOUT", "runtime timeout", retryable=True)

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_gee_client",
        lambda: TimeseriesTimeoutClient(),
        raising=False,
    )
    timeseries_response = client.post(
        "/gee/sentinel2/timeseries",
        json={
            "geometry": _small_polygon(),
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )
    assert timeseries_response.status_code == 404

    class ImageAuthClient(RuntimeErrorClient):
        def image(self, **_: object) -> str:
            from agro_gee_api.services.gee_client import GEEAuthError

            raise GEEAuthError("GEE_AUTH_FAILED", "runtime auth failed image")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_gee_client",
        lambda: ImageAuthClient(),
        raising=False,
    )
    image_response = client.post(
        "/gee/sentinel2/image",
        json={
            "geometry": _small_polygon(),
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )
    assert image_response.status_code == 500
    assert image_response.json()["error_code"] == "GEE_AUTH_FAILED"
