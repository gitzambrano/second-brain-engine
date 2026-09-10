"""Contrato do comando único de publicação pública."""
from __future__ import annotations

import sys
from pathlib import Path

from conftest import SCRIPTS

sys.path.insert(0, str(SCRIPTS))


def test_publish_site_default_runs_one_seal_then_commits_and_pushes(monkeypatch):
    import publish_site

    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(publish_site, "repositories_ready", lambda: None)
    monkeypatch.setattr(
        publish_site,
        "run",
        lambda *command, **_kwargs: calls.append(tuple(command)),
    )
    monkeypatch.setattr(publish_site, "site_has_changes", lambda: True)
    monkeypatch.setattr(publish_site, "publication_message", lambda: "Publicação do site: 2026-09-09")

    assert publish_site.main([]) == 0

    assert calls == [
        (sys.executable, str(SCRIPTS / "check_visibility_field.py")),
        (sys.executable, str(SCRIPTS / "build_site.py")),
        (sys.executable, str(SCRIPTS / "seal_publication.py")),
        ("git", "add", "."),
        ("git", "commit", "-m", "Publicação do site: 2026-09-09"),
        ("git", "push", "origin", "main"),
    ]


def test_publish_site_does_not_commit_when_build_changes_nothing(monkeypatch, capsys):
    import publish_site

    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(publish_site, "repositories_ready", lambda: None)
    monkeypatch.setattr(
        publish_site,
        "run",
        lambda *command, **_kwargs: calls.append(tuple(command)),
    )
    monkeypatch.setattr(publish_site, "site_has_changes", lambda: False)

    assert publish_site.main([]) == 0

    assert calls == [
        (sys.executable, str(SCRIPTS / "check_visibility_field.py")),
        (sys.executable, str(SCRIPTS / "build_site.py")),
        (sys.executable, str(SCRIPTS / "seal_publication.py")),
    ]
    assert "nada a publicar" in capsys.readouterr().out
