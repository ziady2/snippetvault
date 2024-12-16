"""All exceptions snippetbox raises live here.

Keeping them in one module makes the public surface easier to catch
in user code: ``except snippetbox.SnippetboxError`` covers everything.
"""

from __future__ import annotations


class SnippetboxError(Exception):
    """Base class. Catch this if you want to handle anything we raise."""


class BookNotFoundError(SnippetboxError):
    """Raised when a JSON book file cannot be located."""

    def __init__(self, path: str) -> None:
        super().__init__(f"book not found: {path}")
        self.path = path


class DuplicateSlugError(SnippetboxError):
    """Two snippets ended up with the same slug."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"duplicate slug: {slug!r}")
        self.slug = slug


class InvalidSnippetError(SnippetboxError):
    """Validation failed for a snippet (missing field, bad value, etc.)."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class MigrationError(SnippetboxError):
    """Schema migration could not be performed."""

    def __init__(self, message: str, *, from_v: int, to_v: int) -> None:
        super().__init__(message)
        self.from_v = from_v
        self.to_v = to_v


class PluginError(SnippetboxError):
    """A user-supplied plugin misbehaved."""

    def __init__(self, name: str, message: str) -> None:
        super().__init__(f"plugin {name!r}: {message}")
        self.name = name


class SearchError(SnippetboxError):
    """Bad search query syntax."""


class IOFormatError(SnippetboxError):
    """An import/export codec couldn't make sense of an input."""

    def __init__(self, codec: str, message: str) -> None:
        super().__init__(f"{codec}: {message}")
        self.codec = codec


class ConfigError(SnippetboxError):
    """The user's config file is broken."""


class AuditError(SnippetboxError):
    """Something went wrong with the audit log."""


def wrap(exc: BaseException, *, codec: str | None = None) -> SnippetboxError:
    # Convert random exceptions into SnippetboxError so the CLI can
    # show a clean message instead of a traceback. Used at the
    # boundary between codecs and the rest of the app.
    if isinstance(exc, SnippetboxError):
        return exc
    if codec:
        return IOFormatError(codec, str(exc))
    return SnippetboxError(str(exc))
