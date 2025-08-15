"""Template-based formatter.

Provides custom template formatting for entries.
"""

from bibmgr.core.models import Entry


def format_with_template(entry: Entry, template: str) -> str:
    """Format an entry using a custom template.

    Template can include field placeholders like {key}, {title}, {year}, etc.

    Args:
        entry: Entry to format
        template: Template string with placeholders

    Returns:
        Formatted string
    """
    # Build field dictionary
    fields = _build_field_dict(entry)

    try:
        return template.format(**fields)
    except KeyError as e:
        # Handle missing fields gracefully
        missing_field = str(e).strip("'")
        fields[missing_field] = f"[Missing: {missing_field}]"
        return template.format(**fields)


def format_entries_with_template(
    entries: list[Entry], template: str, separator: str = "\n"
) -> str:
    """Format multiple entries using a template.

    Args:
        entries: Entries to format
        template: Template string
        separator: Separator between entries

    Returns:
        Formatted string
    """
    formatted = [format_with_template(entry, template) for entry in entries]
    return separator.join(formatted)


def _build_field_dict(entry: Entry) -> dict[str, str]:
    """Build a dictionary of all entry fields for template formatting."""
    fields = {
        "key": entry.key,
        "type": entry.type.value,
        "title": entry.title or "",
        "year": str(entry.year) if entry.year else "",
    }

    # Handle authors
    if hasattr(entry, "authors") and entry.authors:
        fields["authors"] = " and ".join(entry.authors)
        fields["author"] = " and ".join(entry.authors)
        fields["first_author"] = entry.authors[0] if entry.authors else ""
        fields["author_count"] = str(len(entry.authors))
    elif entry.author:
        fields["authors"] = entry.author
        fields["author"] = entry.author
        fields["first_author"] = entry.author.split(" and ")[0]
        fields["author_count"] = str(len(entry.author.split(" and ")))
    else:
        fields["authors"] = ""
        fields["author"] = ""
        fields["first_author"] = ""
        fields["author_count"] = "0"

    # Add all other fields
    for field in [
        "journal",
        "booktitle",
        "publisher",
        "volume",
        "number",
        "pages",
        "doi",
        "isbn",
        "issn",
        "url",
        "abstract",
        "month",
        "note",
        "edition",
        "series",
        "chapter",
        "address",
        "organization",
        "school",
        "institution",
        "howpublished",
    ]:
        if hasattr(entry, field):
            value = getattr(entry, field)
            if value is not None:
                if isinstance(value, list | tuple):
                    fields[field] = ", ".join(str(v) for v in value)
                else:
                    fields[field] = str(value)
            else:
                fields[field] = ""
        else:
            fields[field] = ""

    # Handle keywords specially
    if entry.keywords:
        if isinstance(entry.keywords, list | tuple):
            fields["keywords"] = ", ".join(entry.keywords)
            fields["keyword_count"] = str(len(entry.keywords))
        else:
            fields["keywords"] = entry.keywords
            fields["keyword_count"] = "1"
    else:
        fields["keywords"] = ""
        fields["keyword_count"] = "0"

    # Add some computed fields
    fields["has_doi"] = "yes" if entry.doi else "no"
    fields["has_url"] = "yes" if entry.url else "no"
    fields["has_abstract"] = "yes" if entry.abstract else "no"

    # Citation key variants
    if hasattr(entry, "authors") and entry.authors and entry.year:
        first_author_last = entry.authors[0].split(",")[0].strip()
        fields["author_year"] = f"{first_author_last}{entry.year}"
    elif entry.author and entry.year:
        first_author = entry.author.split(" and ")[0]
        first_author_last = first_author.split(",")[0].strip()
        fields["author_year"] = f"{first_author_last}{entry.year}"
    else:
        fields["author_year"] = entry.key

    return fields
