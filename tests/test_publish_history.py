"""Histórico raso do site: `main` sempre com dois commits, remoto reescrito."""
from __future__ import annotations

import subprocess
import sys

import pytest
from conftest import SCRIPTS

sys.path.insert(0, str(SCRIPTS))

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test",
}


def git(cwd, *args):
    import os

    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, **GIT_ENV}, check=True,
    )
    return proc.stdout.strip()


@pytest.fixture
def remote_and_clone(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
    work = tmp_path / "site"
    git(tmp_path, "clone", str(bare), str(work))
    git(work, "checkout", "-B", "main")
    (work / ".github").mkdir()
    for n in (1, 2, 3):
        (work / "page.txt").write_text(f"v{n}\n", encoding="utf-8")
        (work / "audio.bin").write_bytes(b"\0" * 2048 * n)
        (work / ".github" / "newsletter-manifest.json").write_text(f'{{"n": {n}}}\n', encoding="utf-8")
        git(work, "add", "-A")
        git(work, "commit", "-m", f"pub {n}")
    git(work, "push", "-u", "origin", "main")
    return bare, work


def test_rewrite_history_leaves_exactly_two_commits(remote_and_clone):
    import publish_site

    bare, work = remote_and_clone
    previous_manifest = git(work, "show", "HEAD:.github/newsletter-manifest.json")
    previous_tree = git(work, "rev-parse", "HEAD^{tree}")

    (work / "page.txt").write_text("v4\n", encoding="utf-8")
    (work / ".github" / "newsletter-manifest.json").write_text('{"n": 4}\n', encoding="utf-8")
    head = publish_site.rewrite_history(work, "Publicação nova")

    assert git(work, "rev-parse", "HEAD") == head
    assert git(work, "rev-list", "--count", "HEAD") == "2"
    assert git(bare, "rev-list", "--count", "main") == "2"
    assert git(bare, "rev-parse", "main") == head
    parent = git(work, "rev-parse", "HEAD^")
    assert git(work, "rev-list", "--parents", "-n", "1", parent) == parent  # órfão
    assert git(work, "rev-parse", "HEAD^^{tree}") == previous_tree
    # O que a newsletter lê: manifesto em HEAD^ é o da publicação anterior.
    assert git(work, "show", "HEAD^:.github/newsletter-manifest.json") == previous_manifest
    assert git(work, "show", "HEAD:.github/newsletter-manifest.json") == '{"n": 4}'
    assert git(work, "status", "--porcelain") == ""


def test_rewrite_history_prunes_old_objects_and_reflog(remote_and_clone):
    import publish_site

    bare, work = remote_and_clone
    (work / "audio.bin").write_bytes(b"\1" * 4096)
    publish_site.rewrite_history(work, "p4")
    (work / "audio.bin").write_bytes(b"\2" * 4096)
    publish_site.rewrite_history(work, "p5")
    assert git(work, "rev-list", "--count", "HEAD") == "2"
    assert git(work, "rev-list", "--all", "--count") == "2"
    # Nada do histórico antigo sobrou como objeto solto.
    unreachable = git(work, "fsck", "--unreachable", "--no-reflogs")
    assert "commit" not in unreachable


def test_second_rewrite_keeps_chain_at_two(remote_and_clone):
    import publish_site

    bare, work = remote_and_clone
    for n in (4, 5, 6):
        (work / "page.txt").write_text(f"v{n}\n", encoding="utf-8")
        publish_site.rewrite_history(work, f"p{n}")
        assert git(bare, "rev-list", "--count", "main") == "2"
    assert git(work, "show", "HEAD^:page.txt") == "v5"


def test_sync_site_checkout_resets_stale_clone_after_remote_rewrite(remote_and_clone, tmp_path):
    import publish_site

    bare, work = remote_and_clone
    other = tmp_path / "other"
    git(tmp_path, "clone", str(bare), str(other))
    assert publish_site.sync_site_checkout(other) is False  # árvores iguais

    (work / "page.txt").write_text("v9\n", encoding="utf-8")
    publish_site.rewrite_history(work, "p9")  # remoto reescrito

    # `other` ainda tem o histórico antigo: pull --rebase falharia; o sync não.
    assert publish_site.sync_site_checkout(other) is True
    assert git(other, "rev-parse", "HEAD") == git(bare, "rev-parse", "main")
    assert (other / "page.txt").read_text(encoding="utf-8").strip() == "v9"
    assert publish_site.sync_site_checkout(other) is False


def test_force_with_lease_rejects_when_remote_moved_unseen(remote_and_clone, tmp_path):
    import publish_site

    bare, work = remote_and_clone
    other = tmp_path / "other"
    git(tmp_path, "clone", str(bare), str(other))
    (other / "page.txt").write_text("alheio\n", encoding="utf-8")
    git(other, "commit", "-am", "alheio")
    git(other, "push", "origin", "main")

    (work / "page.txt").write_text("v7\n", encoding="utf-8")
    with pytest.raises(subprocess.CalledProcessError):
        publish_site.rewrite_history(work, "p7")  # remoto andou sem `work` saber
