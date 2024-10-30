"""Allow ``python -m snippetbox`` as an alternative to the installed script."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
