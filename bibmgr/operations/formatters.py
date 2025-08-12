"""Formatters for bibliography operations."""

from bibmgr.core.models import Entry, EntryType


class CitationFormatter:
    """Format citations in various styles."""

    def __init__(self, style: str = "apa", template: str | None = None):
        """Initialize formatter.

        Args:
            style: Citation style (apa, mla, chicago, bibtex, custom)
            template: Custom template for 'custom' style
        """
        self.style = style.lower()
        self.template = template

    def format(self, entry: Entry) -> str:
        """Format entry as citation.

        Args:
            entry: Bibliography entry

        Returns:
            Formatted citation string
        """
        if self.style == "apa":
            return self._format_apa(entry)
        elif self.style == "mla":
            return self._format_mla(entry)
        elif self.style == "chicago":
            return self._format_chicago(entry)
        elif self.style == "bibtex":
            return self._format_bibtex(entry)
        elif self.style == "custom":
            if not self.template:
                raise ValueError("No template provided for custom format")
            return self._format_custom(entry)
        else:
            raise ValueError(f"Unsupported citation style: {self.style}")

    def _format_apa(self, entry: Entry) -> str:
        """Format in APA style."""
        result = ""

        # Authors (already ends with period)
        if hasattr(entry, "author") and entry.author:
            result += self._format_authors_apa(entry.author)

        # Year
        if hasattr(entry, "year") and entry.year:
            if result:
                result += " "
            result += f"({entry.year})."

        # Title
        if hasattr(entry, "title") and entry.title:
            if result:
                result += " "
            if entry.type == EntryType.BOOK:
                result += f"*{entry.title}*."
            else:
                result += f"{entry.title}."

        # Source
        if entry.type == EntryType.ARTICLE:
            if hasattr(entry, "journal") and entry.journal:
                if result:
                    result += " "
                result += f"*{entry.journal}*."

            # Volume, issue, and pages
            vol_parts = []
            if hasattr(entry, "volume") and entry.volume:
                vol_str = entry.volume
                if hasattr(entry, "number") and entry.number:
                    vol_str += f"({entry.number})"
                vol_parts.append(vol_str)

            if hasattr(entry, "pages") and entry.pages:
                pages = entry.pages.replace("--", "-")
                vol_parts.append(pages)

            if vol_parts:
                if result:
                    result += " "
                result += ", ".join(vol_parts) + "."

        elif entry.type == EntryType.BOOK:
            if hasattr(entry, "publisher") and entry.publisher:
                if result:
                    result += " "
                result += entry.publisher + "."

        elif entry.type == EntryType.INPROCEEDINGS:
            if hasattr(entry, "booktitle") and entry.booktitle:
                if result:
                    result += " "
                result += f"In *{entry.booktitle}*."
            if hasattr(entry, "pages") and entry.pages:
                if result:
                    result += " "
                pages = entry.pages.replace("--", "-")
                result += f"(pp. {pages})."
            if hasattr(entry, "address") and entry.address:
                if result:
                    result += " "
                result += entry.address + "."

        elif entry.type == EntryType.PHDTHESIS or entry.type == EntryType.MASTERSTHESIS:
            type_str = (
                "Doctoral dissertation"
                if entry.type == EntryType.PHDTHESIS
                else "Master's thesis"
            )
            if result:
                result += " "
            if hasattr(entry, "school") and entry.school:
                result += f"[{type_str}, {entry.school}]."
            else:
                result += f"[{type_str}]."

        # DOI
        if hasattr(entry, "doi") and entry.doi:
            if result:
                result += " "
            result += f"https://doi.org/{entry.doi}"

        # URL as fallback
        elif hasattr(entry, "url") and entry.url:
            if result:
                result += " "
            result += entry.url

        # Ensure ends with period
        if not result.endswith("."):
            result += "."

        return result

    def _format_mla(self, entry: Entry) -> str:
        """Format in MLA style."""
        parts = []

        # Authors
        if hasattr(entry, "author") and entry.author:
            authors = self._format_authors_mla(entry.author)
            parts.append(authors)

        # Title
        if hasattr(entry, "title") and entry.title:
            if entry.type == EntryType.BOOK:
                parts.append(f"*{entry.title}*")
            else:
                parts.append(f'"{entry.title}"')

        # Source
        if entry.type == EntryType.ARTICLE:
            if hasattr(entry, "journal") and entry.journal:
                parts.append(f"*{entry.journal}*")

            # Volume and issue
            if hasattr(entry, "volume") and entry.volume:
                vol_str = f"vol. {entry.volume}"
                if hasattr(entry, "number") and entry.number:
                    vol_str += f", no. {entry.number}"
                parts.append(vol_str)

            # Year
            if hasattr(entry, "year") and entry.year:
                parts.append(str(entry.year))

            # Pages
            if hasattr(entry, "pages") and entry.pages:
                pages = entry.pages.replace("--", "-")
                parts.append(f"pp. {pages}")

        elif entry.type == EntryType.BOOK:
            if hasattr(entry, "publisher") and entry.publisher:
                pub_str = entry.publisher
                if hasattr(entry, "year") and entry.year:
                    pub_str += f", {entry.year}"
                parts.append(pub_str)

        elif entry.type == EntryType.INPROCEEDINGS:
            if hasattr(entry, "booktitle") and entry.booktitle:
                parts.append(f"*{entry.booktitle}*")
            if hasattr(entry, "publisher") and entry.publisher:
                parts.append(entry.publisher)
            if hasattr(entry, "year") and entry.year:
                parts.append(str(entry.year))
            if hasattr(entry, "pages") and entry.pages:
                pages = entry.pages.replace("--", "-")
                parts.append(f"pp. {pages}")

        result = ". ".join(parts)
        if not result.endswith("."):
            result += "."
        return result

    def _format_chicago(self, entry: Entry) -> str:
        """Format in Chicago style."""
        parts = []

        # Authors
        if hasattr(entry, "author") and entry.author:
            authors = self._format_authors_chicago(entry.author)
            parts.append(authors)

        # Title
        if hasattr(entry, "title") and entry.title:
            if entry.type == EntryType.BOOK:
                parts.append(f"*{entry.title}*")
            else:
                parts.append(f'"{entry.title}."')

        # Source details
        if entry.type == EntryType.ARTICLE:
            if hasattr(entry, "journal") and entry.journal:
                parts.append(f"*{entry.journal}*")

            if hasattr(entry, "volume") and entry.volume:
                vol_str = entry.volume
                if hasattr(entry, "number") and entry.number:
                    vol_str += f", no. {entry.number}"
                if hasattr(entry, "year") and entry.year:
                    vol_str += f" ({entry.year})"
                parts.append(vol_str)

            if hasattr(entry, "pages") and entry.pages:
                pages = entry.pages.replace("--", "-")
                parts.append(pages)  # No colon prefix

        elif entry.type == EntryType.BOOK:
            pub_parts = []
            if hasattr(entry, "address") and entry.address:
                pub_parts.append(entry.address)
            if hasattr(entry, "publisher") and entry.publisher:
                if pub_parts:  # If we have address
                    pub_parts[0] = pub_parts[0] + ":"  # Address: Publisher
                pub_parts.append(entry.publisher)
            if hasattr(entry, "year") and entry.year:
                pub_parts.append(str(entry.year))
            if pub_parts:
                parts.append(", ".join(pub_parts))

        result = ". ".join(parts)
        if not result.endswith("."):
            result += "."
        return result

    def _format_bibtex(self, entry: Entry) -> str:
        """Format as BibTeX."""
        lines = [f"@{entry.type.value}{{{entry.key},"]

        # Add all non-empty fields
        for field in entry.__struct_fields__:
            if field in ["key", "type"]:
                continue
            value = getattr(entry, field, None)
            if value:
                if isinstance(value, str):
                    lines.append(f"  {field} = {{{value}}},")
                else:
                    lines.append(f"  {field} = {{{value}}},")

        lines.append("}")
        return "\n".join(lines)

    def _format_custom(self, entry: Entry) -> str:
        """Format with custom template."""
        if not self.template:
            raise ValueError("No template provided for custom format")

        # Create context for template
        context = {
            "authors": getattr(entry, "author", ""),
            "year": getattr(entry, "year", ""),
            "title": getattr(entry, "title", ""),
            "journal": getattr(entry, "journal", ""),
            "volume": getattr(entry, "volume", ""),
            "pages": getattr(entry, "pages", ""),
            "doi": getattr(entry, "doi", ""),
            "publisher": getattr(entry, "publisher", ""),
        }

        return self.template.format(**context)

    def _format_authors_apa(self, authors: str) -> str:
        """Format authors in APA style."""
        author_list = authors.split(" and ")
        formatted = []

        for author in author_list:
            author = author.strip()
            if "," in author:
                # Last, First format
                last, first = author.split(",", 1)
                last = last.strip()
                first = first.strip()
                # Use initials
                if first:
                    parts = [n[0].upper() for n in first.split() if n]
                    initials = ". ".join(parts) + "." if parts else ""
                    formatted.append(f"{last}, {initials}")
                else:
                    formatted.append(last)
            else:
                # First Last format
                parts = author.split()
                if len(parts) > 1:
                    last = parts[-1]
                    first_parts = parts[:-1]
                    initials_list = [p[0].upper() for p in first_parts]
                    initials = ". ".join(initials_list) + "." if initials_list else ""
                    formatted.append(f"{last}, {initials}")
                else:
                    formatted.append(author)

        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]}, & {formatted[1]}"
        else:
            return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"

    def _format_authors_mla(self, authors: str) -> str:
        """Format authors in MLA style."""
        author_list = authors.split(" and ")
        formatted = []

        for i, author in enumerate(author_list):
            author = author.strip()
            # First author is in "Last, First" format
            # Subsequent authors are in "First Last" format
            if i == 0:
                # Keep as is if already in Last, First format
                if "," in author:
                    formatted.append(author)
                else:
                    # Convert First Last to Last, First
                    parts = author.split()
                    if len(parts) > 1:
                        formatted.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
                    else:
                        formatted.append(author)
            else:
                # For 2nd+ authors, convert to First Last format if needed
                if "," in author:
                    # Convert from Last, First to First Last
                    last, first = author.split(",", 1)
                    formatted.append(f"{first.strip()} {last.strip()}")
                else:
                    formatted.append(author)

        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]}, and {formatted[1]}"
        else:
            # MLA uses et al. for 3+ authors
            return formatted[0] + ", et al."

    def _format_authors_chicago(self, authors: str) -> str:
        """Format authors in Chicago style."""
        author_list = authors.split(" and ")
        formatted = []

        for i, author in enumerate(author_list):
            author = author.strip()
            # First author is in "Last, First" format
            # Subsequent authors are in "First Last" format (same as MLA)
            if i == 0:
                # Keep as is if already in Last, First format
                if "," in author:
                    formatted.append(author)
                else:
                    # Convert First Last to Last, First
                    parts = author.split()
                    if len(parts) > 1:
                        formatted.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
                    else:
                        formatted.append(author)
            else:
                # For 2nd+ authors, convert to First Last format if needed
                if "," in author:
                    # Convert from Last, First to First Last
                    last, first = author.split(",", 1)
                    formatted.append(f"{first.strip()} {last.strip()}")
                else:
                    formatted.append(author)

        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]}, and {formatted[1]}"
        else:
            # Chicago shows all authors (unlike MLA which uses et al.)
            return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"
