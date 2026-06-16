from pathlib import Path


def test_ci_workflow_contract_baseline() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    )
    content = workflow_path.read_text(encoding="utf-8")

    assert "on:" in content
    assert "push:" in content
    assert "pull_request:" in content
    assert "uses: actions/setup-python" in content
    assert "Install dependencies" in content
    assert "pip install" in content
    assert "run: pytest" in content


def test_ci_workflow_contract_db_free_default() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    )
    content = workflow_path.read_text(encoding="utf-8")

    assert "- name: Run fast tests" in content
    assert 'run: pytest -v -m "not integration"' in content
    assert "- name: Start integration dependencies" in content
    assert "run: docker compose up -d" in content
    assert "- name: Run integration tests" in content
    assert "run: pytest -v -m integration" in content
