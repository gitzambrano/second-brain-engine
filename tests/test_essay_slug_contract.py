import json

from conftest import run_script


def test_essay_slug_checker_requires_the_h1_slug(mini_brain):
    proc = run_script("check_essay_slugs.py", "--json", data_root=mini_brain)

    assert proc.returncode == 1
    assert json.loads(proc.stdout)["issues"][0]["code"] == "ESSAY_FILENAME_TITLE_MISMATCH"
    essays = mini_brain / "wiki" / "essays"
    (essays / "kitchen-sink.md").rename(essays / "qualification-essay.md")
    proc = run_script("check_essay_slugs.py", "--json", data_root=mini_brain)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_essay_slug_checker_rejects_non_kebab_filename(mini_brain):
    essays = mini_brain / "wiki" / "essays"
    (essays / "kitchen-sink.md").rename(essays / "Título inválido.md")

    proc = run_script("check_essay_slugs.py", "--json", data_root=mini_brain)

    assert proc.returncode == 1
    report = json.loads(proc.stdout)
    assert report["status"] == "fail"
    assert report["errors"] == 1
    assert report["issues"][0]["code"] == "ESSAY_FILENAME_TITLE_MISMATCH"


def test_hidden_essay_is_not_required_in_the_public_index(mini_brain):
    essay = mini_brain / "wiki" / "essays" / "kitchen-sink.md"
    essay.write_text(
        essay.read_text(encoding="utf-8").replace(
            "status: draft\n", "status: draft\nvisibility: hidden\n"
        ),
        encoding="utf-8",
    )

    proc = run_script("build_index.py", data_root=mini_brain)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = run_script("check_wiki.py", "--strict", "--json", data_root=mini_brain)

    report = json.loads(proc.stdout)
    codes = {issue["code"] for issue in report["corpus"]}
    assert "INDEX_MISSING_ESSAY" not in codes
