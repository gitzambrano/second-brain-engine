from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_remote_ci_workflows_remain_in_engine_or_data():
    assert not list((ROOT / ".github/workflows").glob("*.y*ml"))
    assert not list((ROOT / "data/.github/workflows").glob("*.y*ml"))


def test_pages_deploy_relies_on_the_local_seal_not_a_remote_python_gate():
    source = (ROOT / "site/.github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "check_artifact.py" not in source
    assert "upload-pages-artifact" in source
