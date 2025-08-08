"""Citation and bibliography generation system.

This module provides comprehensive citation formatting, bibliography generation,
and citation key management with support for multiple citation styles including
APA, MLA, Chicago, IEEE, and custom CSL styles.
"""

from bibmgr.citations.keys import (
    CitationKeyGenerator,
    KeyPattern,
    KeyCollisionStrategy,
    KeyValidator,
    AsyncKeyGenerator,
)
from bibmgr.citations.parser import (
    Citation,
    CitationCommand,
    CitationParser,
    CitationProcessor,
    LaTeXParser,
    BibLaTeXParser,
    MarkdownParser,
    CitationExtractor,
    AsyncCitationProcessor,
)
from bibmgr.citations.styles import (
    CitationFormatter,
    CitationStyle,
    StyleOptions,
    APAStyle,
    MLAStyle,
    ChicagoStyle,
    IEEEStyle,
    CSLStyle,
    StyleRegistry,
    FormattingCache,
    AuthorFormatter,
    DateFormatter,
    TitleFormatter,
)

__all__ = [
    # Keys
    "CitationKeyGenerator",
    "KeyPattern",
    "KeyCollisionStrategy",
    "KeyValidator",
    "AsyncKeyGenerator",
    # Parser
    "Citation",
    "CitationCommand",
    "CitationParser",
    "CitationProcessor",
    "LaTeXParser",
    "BibLaTeXParser",
    "MarkdownParser",
    "CitationExtractor",
    "AsyncCitationProcessor",
    # Styles
    "CitationFormatter",
    "CitationStyle",
    "StyleOptions",
    "APAStyle",
    "MLAStyle",
    "ChicagoStyle",
    "IEEEStyle",
    "CSLStyle",
    "StyleRegistry",
    "FormattingCache",
    "AuthorFormatter",
    "DateFormatter",
    "TitleFormatter",
]
