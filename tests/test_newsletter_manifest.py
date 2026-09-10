"""Contrato de opt-in e reenvio da newsletter."""
from __future__ import annotations

from types import SimpleNamespace

from lib import build_newsletter_manifest as newsletter


def _essay():
    return SimpleNamespace(
        slug="essay-teste",
        title="Essay teste",
        summary="Resumo suficientemente longo para o manifesto de teste.",
        path="essay-teste.md",
        updated="2026-09-09",
    )


def test_newsletter_issue_is_the_only_opt_in(monkeypatch):
    monkeypatch.setattr(newsletter, "collect_public", lambda: [_essay()])
    monkeypatch.setattr(newsletter, "parse", lambda _path: ({"newsletter_issue": 1}, "corpo"))
    monkeypatch.setattr(newsletter, "public_body_for_index", lambda *_args: "corpo")
    monkeypatch.setattr(newsletter, "plain_text", lambda body: body)

    assert [entry["id"] for entry in newsletter.collect_newsletter_entries()] == ["essay-teste:1"]


def test_missing_newsletter_issue_never_sends(monkeypatch):
    monkeypatch.setattr(newsletter, "collect_public", lambda: [_essay()])
    monkeypatch.setattr(newsletter, "parse", lambda _path: ({"newsletter": True}, "corpo"))
    monkeypatch.setattr(newsletter, "public_body_for_index", lambda *_args: "corpo")
    monkeypatch.setattr(newsletter, "plain_text", lambda body: body)

    assert newsletter.collect_newsletter_entries() == []
