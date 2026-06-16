from agro_gee_api.routes._authz import get_authz_context


def test_get_authz_context_is_header_driven_and_db_free() -> None:
    context = get_authz_context(x_user_id="1", x_requester_role=" Internal ")

    assert context.requester_user_id == 1
    assert context.allowed_user_ids == (1,)
    assert context.requester_role is None


def test_get_authz_context_ignores_empty_requester_role() -> None:
    context = get_authz_context(x_user_id="9", x_requester_role="   ")

    assert context.requester_role is None
