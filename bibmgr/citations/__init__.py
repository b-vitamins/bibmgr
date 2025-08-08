"""Citation and bibliography generation system.

This module provides comprehensive citation formatting, bibliography generation,
and citation key management with support for multiple citation styles including
APA, MLA, Chicago, IEEE, and custom CSL styles.
"""

from bibmgr.citations.keys import (
    AsyncKeyGenerator,
    CitationKeyGenerator,
    KeyCollisionStrategy,
    KeyPattern,
    KeyValidator,
)
from bibmgr.citations.parser import (
    AsyncCitationProcessor,
    BibLaTeXParser,
    Citation,
    CitationCommand,
    CitationExtractor,
    CitationParser,
    CitationProcessor,
    LaTeXParser,
    MarkdownParser,
)
from bibmgr.citations.styles import (
    APAStyle,
    AuthorFormatter,
    ChicagoStyle,
    CitationFormatter,
    CitationStyle,
    CSLStyle,
    DateFormatter,
    FormattingCache,
    IEEEStyle,
    MLAStyle,
    StyleOptions,
    StyleRegistry,
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
