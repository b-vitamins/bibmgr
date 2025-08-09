"""RIS (Research Information Systems) format importer.

RIS is a standardized tag format developed by Research Information Systems,
used for exchanging citation data between different reference managers.
"""

import re
from pathlib import Path
from typing import Any

from bibmgr.core.models import Entry, EntryType
from bibmgr.core.validators import ValidatorRegistry


class RisImporter:
    """Import entries from RIS format."""

    TYPE_MAPPING = {
        "JOUR": EntryType.ARTICLE,
        "BOOK": EntryType.BOOK,
        "CHAP": EntryType.INBOOK,
        "CONF": EntryType.INPROCEEDINGS,
        "RPRT": EntryType.TECHREPORT,
        "THES": EntryType.PHDTHESIS,
        "UNPB": EntryType.UNPUBLISHED,
        "MGZN": EntryType.ARTICLE,
        "NEWS": EntryType.ARTICLE,
        "ELEC": EntryType.MISC,
        "COMP": EntryType.MISC,
        "GEN": EntryType.MISC,
    }

    TAG_MAPPING = {
        "TI": "title",
        "T1": "title",
        "AU": "author",
        "A1": "author",
        "PY": "year",
        "Y1": "year",
        "JO": "journal",
        "JF": "journal",
        "JA": "journal",
        "VL": "volume",
        "IS": "number",
        "SP": "pages",
        "EP": "pages",
        "DO": "doi",
        "UR": "url",
        "AB": "abstract",
        "N2": "abstract",
        "KW": "keywords",
        "PB": "publisher",
        "CY": "address",
        "LA": "language",
        "SN": "issn",
        "BN": "isbn",
        "N1": "note",
        "M1": "note",
        "M3": "note",
    }

    def __init__(self, validate: bool = True):
        self.validate = validate
        self.validator_registry = ValidatorRegistry()

    def import_file(self, path: Path) -> tuple[list[Entry], list[str]]:
        """Import from RIS file."""
        try:
            content = path.read_text(encoding="utf-8-sig")
            return self.import_text(content)
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="latin-1")
                return self.import_text(content)
            except Exception as e:
                return [], [f"Failed to read file: {e}"]
        except Exception as e:
            return [], [f"Failed to read file: {e}"]

    def import_text(self, text: str) -> tuple[list[Entry], list[str]]:
        """Import from RIS text."""
        entries = []
        errors = []

        records = self._split_records(text)

        for i, record_text in enumerate(records):
            try:
                entry = self._parse_record(record_text)
                if entry:
                    if self.validate:
                        validation_errors = self.validator_registry.validate(entry)
                        error_messages = [
                            e.message
                            for e in validation_errors
                            if e.severity == "error"
                        ]

                        if error_messages:
                            errors.append(
                                f"Record {i + 1}: " + "; ".join(error_messages)
                            )
                            continue

                    entries.append(entry)

            except Exception as e:
                errors.append(f"Record {i + 1}: {e}")

        return entries, errors

    def _split_records(self, text: str) -> list[str]:
        """Split RIS text into individual records."""
        records = []
        current_record = []
        in_record = False

        for line in text.splitlines():
            line = line.strip()

            if line.startswith("TY  -"):
                in_record = True
                current_record = [line]
            elif line.startswith("ER  -") and in_record:
                current_record.append(line)
                records.append("\n".join(current_record))
                current_record = []
                in_record = False
            elif in_record:
                current_record.append(line)

        if current_record and in_record:
            records.append("\n".join(current_record))

        return records

    def _process_tag(
        self,
        tag: str,
        value: str,
        data: dict,
        entry_type,
        authors: list,
        keywords: list,
        notes: list,
    ) -> None:
        """Process a single RIS tag and its value."""
        if not value:
            return

        if tag == "TY":
            data["TY"] = value
        elif tag in ["AU", "A1", "A2", "A3"]:
            authors.append(value)
        elif tag == "KW":
            keywords.append(value)
        elif tag in ["N1", "M1", "M3"]:
            notes.append(value)
        elif tag == "SP":
            data["SP"] = value
        elif tag == "EP":
            data["EP"] = value
        elif tag in self.TAG_MAPPING:
            field = self.TAG_MAPPING[tag]
            if field not in ["author", "keywords", "note"]:
                data[field] = value

    def _parse_record(self, record_text: str) -> Entry | None:
        """Parse a single RIS record into an Entry."""
        data = {}
        entry_type = None
        authors = []
        keywords = []
        notes = []

        lines = record_text.splitlines()
        current_tag = None
        current_value = []

        for line in lines:
            match = re.match(r"^([A-Z][A-Z0-9])\s+-\s*(.*)$", line)
            if match:
                if current_tag:
                    self._process_tag(
                        current_tag,
                        " ".join(current_value).strip(),
                        data,
                        entry_type,
                        authors,
                        keywords,
                        notes,
                    )

                current_tag, value = match.groups()
                current_value = [value.strip()] if value.strip() else []
            else:
                stripped = line.strip()
                if current_tag and stripped:
                    current_value.append(stripped)

        if current_tag:
            self._process_tag(
                current_tag,
                " ".join(current_value).strip(),
                data,
                entry_type,
                authors,
                keywords,
                notes,
            )

        if "TY" in data:
            entry_type = self.TYPE_MAPPING.get(data["TY"], EntryType.MISC)
            del data["TY"]

        if "SP" in data and "EP" in data:
            data["pages"] = f"{data['SP']}--{data['EP']}"
            del data["SP"]
            del data["EP"]
        elif "SP" in data:
            data["pages"] = data["SP"]
            del data["SP"]
        elif "EP" in data:
            data["pages"] = data["EP"]
            del data["EP"]

        if authors:
            data["author"] = " and ".join(authors)
        if keywords:
            data["keywords"] = ", ".join(keywords)
        if notes:
            data["note"] = "; ".join(notes)

        if "EP" in data:
            del data["EP"]

        if "key" not in data:
            data["key"] = self._generate_key(data, authors)

        data["type"] = entry_type

        if "year" in data:
            try:
                year_match = re.search(r"(\d{4})", data["year"])
                if year_match:
                    data["year"] = int(year_match.group(1))
                else:
                    del data["year"]
            except ValueError:
                del data["year"]

        # Create Entry object
        return Entry.from_dict(data)

    def _generate_key(self, data: dict[str, Any], authors: list[str]) -> str:
        """Generate a BibTeX key from RIS data."""
        key_parts = []

        if authors:
            first_author = authors[0]
            if "," in first_author:
                last_name = first_author.split(",")[0].strip()
            else:
                parts = first_author.split()
                last_name = parts[-1] if parts else "Unknown"

            last_name = re.sub(r"[^a-zA-Z]", "", last_name)
            key_parts.append(last_name.lower())
        else:
            key_parts.append("unknown")

        if "year" in data:
            key_parts.append(str(data["year"]))

        if "title" in data:
            title_words = re.findall(r"\w+", data["title"])
            if title_words:
                key_parts.append(title_words[0].lower())

        return "_".join(key_parts)

    def export_entries(self, entries: list[Entry], path: Path) -> None:
        """Export entries to RIS format."""
        lines = []

        type_to_ris = {v: k for k, v in self.TYPE_MAPPING.items()}

        for entry in entries:
            ris_type = type_to_ris.get(entry.type, "GEN")
            lines.append(f"TY  - {ris_type}")

            if entry.author:
                for author in entry.author.split(" and "):
                    lines.append(f"AU  - {author.strip()}")

            if entry.title:
                lines.append(f"TI  - {entry.title}")

            if entry.year:
                lines.append(f"PY  - {entry.year}")

            if entry.journal:
                lines.append(f"JO  - {entry.journal}")

            if entry.volume:
                lines.append(f"VL  - {entry.volume}")

            if entry.number:
                lines.append(f"IS  - {entry.number}")

            if entry.pages:
                if "--" in entry.pages:
                    start, end = entry.pages.split("--", 1)
                    lines.append(f"SP  - {start.strip()}")
                    lines.append(f"EP  - {end.strip()}")
                else:
                    lines.append(f"SP  - {entry.pages}")

            if entry.doi:
                lines.append(f"DO  - {entry.doi}")

            if entry.url:
                lines.append(f"UR  - {entry.url}")

            if entry.abstract:
                abstract_lines = self._wrap_text(entry.abstract, 70)
                for i, line in enumerate(abstract_lines):
                    if i == 0:
                        lines.append(f"AB  - {line}")
                    else:
                        lines.append(f"      {line}")

            if entry.keywords:
                for keyword in entry.keywords:
                    lines.append(f"KW  - {keyword}")

            if entry.publisher:
                lines.append(f"PB  - {entry.publisher}")

            if entry.address:
                lines.append(f"CY  - {entry.address}")

            if entry.issn:
                lines.append(f"SN  - {entry.issn}")

            if entry.isbn:
                lines.append(f"BN  - {entry.isbn}")

            if entry.note:
                lines.append(f"N1  - {entry.note}")

            lines.append("ER  - ")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")

    def _wrap_text(self, text: str, width: int) -> list[str]:
        """Wrap text to specified width."""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 > width:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = len(word)
            else:
                current_line.append(word)
                current_length += len(word) + 1

        if current_line:
            lines.append(" ".join(current_line))

        return lines
