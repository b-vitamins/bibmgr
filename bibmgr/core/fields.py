"""BibTeX field definitions and entry type specifications."""

from enum import Enum, unique

# Standard BibTeX fields from TameTheBeast manual
STANDARD_FIELDS = {
    "address",
    "author",
    "booktitle",
    "chapter",
    "crossref",
    "edition",
    "editor",
    "howpublished",
    "institution",
    "journal",
    "key",
    "month",
    "note",
    "number",
    "organization",
    "pages",
    "publisher",
    "school",
    "series",
    "title",
    "type",
    "volume",
    "year",
}

# Modern extensions
MODERN_FIELDS = {
    "doi",
    "url",
    "isbn",
    "issn",
    "keywords",
    "abstract",
    "eprint",
    "archiveprefix",
    "primaryclass",
    "eid",
    "numpages",
    "file",
    "urldate",
    "pubstate",
    "pagetotal",
    "annotation",
    "shorthand",
}

# Additional compatibility fields
COMPAT_FIELDS = {
    "annote",
    "collaboration",
    "comment",
    "sortkey",
    "timestamp",
    "review",
    "groups",
    "owner",
    "qualityassured",
    "ranking",
    "readstatus",
    "printed",
}

ALL_FIELDS = STANDARD_FIELDS | MODERN_FIELDS | COMPAT_FIELDS


@unique
class EntryType(Enum):
    """BibTeX entry types with their required/optional fields."""

    ARTICLE = "article"
    BOOK = "book"
    BOOKLET = "booklet"
    INBOOK = "inbook"
    INCOLLECTION = "incollection"
    INPROCEEDINGS = "inproceedings"
    CONFERENCE = "conference"  # Alias for inproceedings
    MANUAL = "manual"
    MASTERSTHESIS = "mastersthesis"
    MISC = "misc"
    PHDTHESIS = "phdthesis"
    PROCEEDINGS = "proceedings"
    TECHREPORT = "techreport"
    UNPUBLISHED = "unpublished"

    # Modern types
    ONLINE = "online"
    ELECTRONIC = "electronic"
    PATENT = "patent"
    SOFTWARE = "software"
    DATASET = "dataset"
    THESIS = "thesis"  # Generic thesis type


class FieldRequirements:
    """Define required/optional fields for each entry type."""

    REQUIREMENTS = {
        EntryType.ARTICLE: {
            "required": {"author", "title", "journal", "year"},
            "optional": {"volume", "number", "pages", "month", "note", "doi", "url"},
        },
        EntryType.BOOK: {
            "required": {"author|editor", "title", "publisher", "year"},
            "optional": {
                "volume|number",
                "series",
                "address",
                "edition",
                "month",
                "note",
                "isbn",
                "doi",
                "url",
            },
        },
        EntryType.BOOKLET: {
            "required": {"title"},
            "optional": {"author", "howpublished", "address", "month", "year", "note"},
        },
        EntryType.INBOOK: {
            "required": {
                "author|editor",
                "title",
                "chapter|pages",
                "publisher",
                "year",
            },
            "optional": {
                "volume|number",
                "series",
                "type",
                "address",
                "edition",
                "month",
                "note",
            },
        },
        EntryType.INCOLLECTION: {
            "required": {"author", "title", "booktitle", "publisher", "year"},
            "optional": {
                "editor",
                "volume|number",
                "series",
                "type",
                "chapter",
                "pages",
                "address",
                "edition",
                "month",
                "note",
            },
        },
        EntryType.INPROCEEDINGS: {
            "required": {"author", "title", "booktitle", "year"},
            "optional": {
                "editor",
                "volume|number",
                "series",
                "pages",
                "address",
                "month",
                "organization",
                "publisher",
                "note",
            },
        },
        EntryType.MANUAL: {
            "required": {"title"},
            "optional": {
                "author",
                "organization",
                "address",
                "edition",
                "month",
                "year",
                "note",
            },
        },
        EntryType.MASTERSTHESIS: {
            "required": {"author", "title", "school", "year"},
            "optional": {"type", "address", "month", "note"},
        },
        EntryType.MISC: {
            "required": set(),  # No required fields
            "optional": {"author", "title", "howpublished", "month", "year", "note"},
        },
        EntryType.PHDTHESIS: {
            "required": {"author", "title", "school", "year"},
            "optional": {"type", "address", "month", "note"},
        },
        EntryType.PROCEEDINGS: {
            "required": {"title", "year"},
            "optional": {
                "editor",
                "volume|number",
                "series",
                "address",
                "month",
                "organization",
                "publisher",
                "note",
            },
        },
        EntryType.TECHREPORT: {
            "required": {"author", "title", "institution", "year"},
            "optional": {"type", "number", "address", "month", "note"},
        },
        EntryType.UNPUBLISHED: {
            "required": {"author", "title", "note"},
            "optional": {"month", "year"},
        },
        # Modern types
        EntryType.ONLINE: {
            "required": {"author|editor", "title", "url", "year"},
            "optional": {"urldate", "note", "organization", "month"},
        },
        EntryType.DATASET: {
            "required": {"author", "title", "publisher|howpublished", "year"},
            "optional": {"doi", "url", "version", "note", "month"},
        },
    }

    @classmethod
    def get_requirements(cls, entry_type: EntryType) -> dict[str, set[str]]:
        """Get field requirements for an entry type."""
        # Handle conference as alias for inproceedings
        if entry_type == EntryType.CONFERENCE:
            entry_type = EntryType.INPROCEEDINGS
        return cls.REQUIREMENTS.get(
            entry_type, {"required": set(), "optional": ALL_FIELDS}
        )
