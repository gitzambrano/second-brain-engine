import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workflow_script_paths_exist():
    missing = []
    for workflow in (ROOT / ".github/workflows").glob("*.y*ml"):
        source = workflow.read_text(encoding="utf-8")
        refs = set(re.findall(r"\bscripts/[A-Za-z0-9_./-]+\.py\b", source))
        for rel in sorted(refs):
            if not (ROOT / rel).is_file():
                missing.append(f"{workflow.name}: {rel}")
    assert not missing, "workflow references missing scripts:\n" + "\n".join(missing)


def test_expensive_ci_is_split_and_path_scoped():
    workflows = ROOT / ".github/workflows"
    sanity = (workflows / "sanity.yml").read_text(encoding="utf-8")
    assert "pdf-export:" not in sanity
    assert "html-export:" not in sanity
    assert "site-browser:" not in sanity

    for name in ("pdf-export.yml", "html-export.yml", "site-browser.yml"):
        source = (workflows / name).read_text(encoding="utf-8")
        assert "paths:" in source, f"{name} must not run for every engine commit"
        assert "workflow_dispatch:" in source, f"{name} must remain available on demand"
