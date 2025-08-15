"""CSV output formatter.

Provides formatting of entries to CSV format.
"""

import csv
from io import StringIO

from bibmgr.core.models import Entry


def format_entries_csv(
    entries: list[Entry],
    fields: list[str] | None = None,
    delimiter: str = ",",
    quote_char: str = '"',
) -> str:
    """Format entries as CSV.

    Args:
        entries: Entries to format
        fields: Fields to include (default: key, type, title, author, year)
        delimiter: CSV delimiter
        quote_char: Quote character

    Returns:
        CSV formatted string
    """
    if not fields:
        fields = ["key", "type", "title", "author", "year", "journal", "doi"]

    # Use StringIO to build CSV in memory
    output = StringIO()
    writer = csv.writer(
        output,
        delimiter=delimiter,
        quotechar=quote_char,
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )

    # Write header
    writer.writerow(fields)

    # Write entries
    for entry in entries:
        row = []
        for field in fields:
            value = ""

            if field == "key":
                value = entry.key
            elif field == "type":
                value = entry.type.value
            elif field == "title":
                value = entry.title or ""
            elif field == "author":
                # Handle both authors list and author string
                if hasattr(entry, "authors") and entry.authors:
                    value = " and ".join(entry.authors)
                elif entry.author:
                    value = entry.author
            elif field == "year":
                value = str(entry.year) if entry.year else ""
            elif field == "journal":
                value = entry.journal or ""
            elif field == "doi":
                value = entry.doi or ""
            elif field == "pages":
                value = entry.pages or ""
            elif field == "volume":
                value = entry.volume or ""
            elif field == "publisher":
                value = entry.publisher or ""
            elif field == "keywords":
                if entry.keywords:
                    if isinstance(entry.keywords, list | tuple):
                        value = "; ".join(entry.keywords)
                    else:
                        value = entry.keywords
            else:
                # Generic field access
                if hasattr(entry, field):
                    field_value = getattr(entry, field)
                    if field_value is not None:
                        if isinstance(field_value, list | tuple):
                            value = "; ".join(str(v) for v in field_value)
                        else:
                            value = str(field_value)

            row.append(value)

        writer.writerow(row)

    return output.getvalue()
