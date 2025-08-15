"""Citation formatter for various citation styles.

Provides formatting of entries in APA, IEEE, MLA, Chicago, and custom styles.
"""

from bibmgr.core.models import Entry


def format_citation(
    entry: Entry, style: str = "apa", template: str | None = None
) -> str:
    """Format an entry as a citation in the specified style.

    Args:
        entry: Entry to format
        style: Citation style (apa, ieee, mla, chicago)
        template: Custom template (overrides style)

    Returns:
        Formatted citation string
    """
    if template:
        return _format_with_template(entry, template)

    style = style.lower()

    if style == "apa":
        return _format_apa(entry)
    elif style == "ieee":
        return _format_ieee(entry)
    elif style == "mla":
        return _format_mla(entry)
    elif style == "chicago":
        return _format_chicago(entry)
    else:
        # Default to APA
        return _format_apa(entry)


def format_citations(
    entries: list[Entry], style: str = "apa", numbered: bool = False
) -> list[str]:
    """Format multiple entries as citations.

    Args:
        entries: Entries to format
        style: Citation style
        numbered: Whether to number citations (for IEEE style)

    Returns:
        List of formatted citations
    """
    citations = []

    for i, entry in enumerate(entries):
        if style.lower() == "ieee" and numbered:
            # Add number prefix for IEEE
            citation = f"[{i + 1}] " + format_citation(entry, style)
        else:
            citation = format_citation(entry, style)

        citations.append(citation)

    return citations


def _format_with_template(entry: Entry, template: str) -> str:
    """Format using a custom template.

    Template can include fields like {author}, {year}, {title}, etc.
    """
    # Build field dictionary
    fields = {
        "key": entry.key,
        "type": entry.type.value,
        "title": entry.title or "",
        "year": str(entry.year) if entry.year else "",
        "journal": entry.journal or "",
        "booktitle": entry.booktitle or "",
        "publisher": entry.publisher or "",
        "volume": entry.volume or "",
        "number": entry.number or "",
        "pages": entry.pages or "",
        "doi": entry.doi or "",
        "url": entry.url or "",
    }

    # Handle authors
    if hasattr(entry, "authors") and entry.authors:
        fields["author"] = " and ".join(entry.authors)
        fields["authors"] = " and ".join(entry.authors)
    elif entry.author:
        fields["author"] = entry.author
        fields["authors"] = entry.author
    else:
        fields["author"] = ""
        fields["authors"] = ""

    return template.format(**fields)


def _format_apa(entry: Entry) -> str:
    """Format in APA style."""
    parts = []

    # Authors
    if hasattr(entry, "authors") and entry.authors:
        if len(entry.authors) == 1:
            parts.append(_format_author_apa(entry.authors[0]))
        elif len(entry.authors) == 2:
            parts.append(
                f"{_format_author_apa(entry.authors[0])}, & {_format_author_apa(entry.authors[1])}"
            )
        else:
            # Three or more authors
            formatted_authors = [_format_author_apa(a) for a in entry.authors[:6]]
            if len(entry.authors) > 6:
                parts.append(
                    ", ".join(formatted_authors)
                    + ", ... "
                    + _format_author_apa(entry.authors[-1])
                )
            else:
                parts.append(
                    ", ".join(formatted_authors[:-1]) + ", & " + formatted_authors[-1]
                )
    elif entry.author:
        parts.append(entry.author)

    # Year
    if entry.year:
        parts.append(f"({entry.year}).")

    # Title
    if entry.title:
        if entry.type.value in ["book", "inbook", "manual", "techreport"]:
            # Italicize book titles
            parts.append(f"*{entry.title}*.")
        else:
            parts.append(f"{entry.title}.")

    # Journal/Book
    if entry.journal:
        parts.append(f"*{entry.journal}*")
        if entry.volume:
            parts.append(f", *{entry.volume}*")
            if entry.number:
                parts.append(f"({entry.number})")
        if entry.pages:
            parts.append(f", {entry.pages}")
    elif entry.booktitle:
        parts.append(f"In *{entry.booktitle}*")
        if entry.pages:
            parts.append(f"(pp. {entry.pages})")

    # Publisher
    if entry.publisher:
        parts.append(f". {entry.publisher}")

    # DOI
    if entry.doi:
        parts.append(f". https://doi.org/{entry.doi}")

    return " ".join(parts)


def _format_ieee(entry: Entry) -> str:
    """Format in IEEE style."""
    parts = []

    # Authors
    if hasattr(entry, "authors") and entry.authors:
        # IEEE uses initials first
        ieee_authors = []
        for author in entry.authors:
            # Simple conversion - in reality would need proper name parsing
            parts_name = author.split(", ")
            if len(parts_name) == 2:
                last, first = parts_name
                initials = "".join(f"{n[0]}." for n in first.split() if n)
                ieee_authors.append(f"{initials} {last}")
            else:
                ieee_authors.append(author)

        if len(ieee_authors) <= 3:
            parts.append(", ".join(ieee_authors))
        else:
            parts.append(", ".join(ieee_authors[:3]) + " et al.")
    elif entry.author:
        parts.append(entry.author)

    # Title in quotes
    if entry.title:
        parts.append(f', "{entry.title},"')

    # Journal/Conference
    if entry.journal:
        parts.append(f" *{entry.journal}*")
    elif entry.booktitle:
        parts.append(f" in *{entry.booktitle}*")

    # Volume, number, pages
    if entry.volume:
        parts.append(f", vol. {entry.volume}")
    if entry.number:
        parts.append(f", no. {entry.number}")
    if entry.pages:
        parts.append(f", pp. {entry.pages}")

    # Year
    if entry.year:
        parts.append(f", {entry.year}")

    return "".join(parts) + "."


def _format_mla(entry: Entry) -> str:
    """Format in MLA style."""
    parts = []

    # Authors
    if hasattr(entry, "authors") and entry.authors:
        if len(entry.authors) == 1:
            parts.append(entry.authors[0])
        elif len(entry.authors) == 2:
            # First author stays as "Last, First", second is "First Last"
            second_author = _format_author_mla_second(entry.authors[1])
            parts.append(f"{entry.authors[0]}, and {second_author}")
        else:
            parts.append(f"{entry.authors[0]}, et al.")
    elif entry.author:
        parts.append(entry.author)

    # Title in quotes
    if entry.title:
        parts.append(f'. "{entry.title}."')

    # Journal/Book in italics
    if entry.journal:
        parts.append(f" *{entry.journal}*")
    elif entry.booktitle:
        parts.append(f" *{entry.booktitle}*")

    # Volume and number
    if entry.volume:
        parts.append(f", vol. {entry.volume}")
        if entry.number:
            parts.append(f", no. {entry.number}")

    # Year
    if entry.year:
        parts.append(f", {entry.year}")

    # Pages
    if entry.pages:
        parts.append(f", pp. {entry.pages}")

    return "".join(parts) + "."


def _format_chicago(entry: Entry) -> str:
    """Format in Chicago style."""
    parts = []

    # Authors
    if hasattr(entry, "authors") and entry.authors:
        if len(entry.authors) == 1:
            parts.append(entry.authors[0])
        elif len(entry.authors) == 2:
            # First author stays as "Last, First", second is "First Last"
            second_author = _format_author_mla_second(entry.authors[1])
            parts.append(f"{entry.authors[0]}, and {second_author}")
        else:
            # Chicago shows all authors - format all but first as "First Last"
            formatted_authors = [entry.authors[0]]
            for author in entry.authors[1:-1]:
                formatted_authors.append(_format_author_mla_second(author))
            formatted_authors.append(_format_author_mla_second(entry.authors[-1]))
            parts.append(
                ", ".join(formatted_authors[:-1]) + f", and {formatted_authors[-1]}"
            )
    elif entry.author:
        parts.append(entry.author)

    # Title in quotes
    if entry.title:
        parts.append(f'. "{entry.title}."')

    # Journal/Book in italics
    if entry.journal:
        parts.append(f" *{entry.journal}*")
        if entry.volume:
            parts.append(f" {entry.volume}")
            if entry.number:
                parts.append(f", no. {entry.number}")
    elif entry.booktitle:
        parts.append(f" In *{entry.booktitle}*")

    # Year
    if entry.year:
        parts.append(f" ({entry.year})")

    # Pages
    if entry.pages:
        parts.append(f": {entry.pages}")

    return "".join(parts) + "."


def _format_author_apa(author: str) -> str:
    """Format author name in APA style (Last, F. M.)."""
    # Simple implementation - in reality would need proper name parsing
    parts = author.split(", ")
    if len(parts) == 2:
        last, first = parts
        initials = "".join(f"{n[0]}." for n in first.split() if n)
        return f"{last}, {initials}"
    return author


def _format_author_mla_second(author: str) -> str:
    """Format second author name in MLA style (First Last)."""
    # Convert "Last, First" to "First Last"
    parts = author.split(", ")
    if len(parts) == 2:
        last, first = parts
        return f"{first} {last}"
    return author
