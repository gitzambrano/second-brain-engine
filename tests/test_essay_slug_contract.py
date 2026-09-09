import json

from conftest import run_script


def test_essay_slug_checker_accepts_canonical_kebab_case(mini_brain):
    proc = run_script("check_essay_slugs.py", "--json", data_root=mini_brain)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["status"] == "pass"


def test_essay_slug_checker_rejects_non_kebab_filename(mini_brain):
    essays = mini_brain / "wiki" / "essays"
    (essays / "kitchen-sink.md").rename(essays / "Título inválido.md")

    proc = run_script("check_essay_slugs.py", "--json", data_root=mini_brain)

    assert proc.returncode == 1
    report = json.loads(proc.stdout)
    assert report["status"] == "fail"
    assert report["errors"] == 1
    assert report["issues"][0]["code"] == "ESSAY_SLUG_NOT_KEBAB"
