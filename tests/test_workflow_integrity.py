from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_remote_ci_workflows_remain_in_engine_or_data():
    assert not list((ROOT / ".github/workflows").glob("*.y*ml"))
    assert not list((ROOT / "data/.github/workflows").glob("*.y*ml"))


def test_site_maintains_only_pages_and_newsletter_workflows():
    workflows_dir = ROOT / "site/.github/workflows"
    workflow_names = {p.name for p in workflows_dir.glob("*.y*ml")}
    assert workflow_names == {"pages.yml", "newsletter.yml"}

    pages_source = (workflows_dir / "pages.yml").read_text(encoding="utf-8")
    assert "check_artifact.py" in pages_source
    assert "upload-pages-artifact" in pages_source

    newsletter_source = (workflows_dir / "newsletter.yml").read_text(encoding="utf-8")
    assert "send_kit_newsletter.py" in newsletter_source

