"""Reexporta lib.build_newsletter_manifest no caminho plano antigo."""
from lib.build_newsletter_manifest import *  # noqa: F401,F403

if __name__ == "__main__":
    from lib.build_newsletter_manifest import main
    raise SystemExit(main())
