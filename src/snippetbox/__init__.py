"""snippetbox - an offline knowledge base for reusable code snippets.

The package surface is intentionally thin: most users only ever touch
the CLI. If you import this as a library, you probably want
``snippetbox.storage.Book`` to load/save and ``snippetbox.search.search``
to query.
"""

from .errors import (
    SnippetboxError,
    BookNotFoundError,
    DuplicateSlugError,
    InvalidSnippetError,
    MigrationError,
    PluginError,
)
from .snippet import Snippet
from .tag import Tag
from .author import Author
from .collection import Collection
from .language import Language
from .service import MutationResult, SnippetService

__version__ = "2.0.0"
__all__ = [
    "__version__",
    "SnippetboxError",
    "BookNotFoundError",
    "DuplicateSlugError",
    "InvalidSnippetError",
    "MigrationError",
    "PluginError",
    "Snippet",
    "Tag",
    "Author",
    "Collection",
    "Language",
    "MutationResult",
    "SnippetService",
]
