"""Builder patterns for creating entries and collections."""

import re
from typing import Any, Union

from .fields import EntryType
from .models import Collection, Entry
from .names import NameParser

# Since Entry model doesn't have 'collections' field, we'll track it separately
# Same for Collection model not having 'parent', 'children', 'metadata', 'smart_filters'
# We'll create enhanced versions for the builder pattern


class EntryWithExtras:
    """Wrapper for Entry with additional fields for builder pattern."""

    def __init__(
        self, entry: Any, collections: set[str]
    ):  # Accept any entry-like object
        self._entry = entry
        self.collections = list(collections)
        # Delegate all attributes to the wrapped entry

    def __getattr__(self, name):
        return getattr(self._entry, name)


class CollectionWithExtras:
    """Wrapper for Collection with additional fields for builder pattern."""

    def __init__(
        self,
        collection: Collection,
        parent: Union[Collection, "CollectionWithExtras"] | None = None,
        metadata: dict[str, Any] | None = None,
        smart_filters: list[dict[str, Any]] | None = None,
    ):
        self._collection = collection
        self.parent = parent
        self.children: list[CollectionWithExtras] = []
        self.metadata = metadata or {}
        self.smart_filters = smart_filters or []
        self.entry_keys = list(collection.entry_keys) if collection.entry_keys else []

        # Add to parent's children if parent exists
        if parent:
            if isinstance(parent, CollectionWithExtras):
                parent.children.append(self)
            # For raw Collection, we can't add children

    def __getattr__(self, name):
        return getattr(self._collection, name)

    def get_path(self) -> list[str]:
        """Get hierarchical path as list of names."""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            if isinstance(current, CollectionWithExtras):
                current = current.parent
            else:
                # Raw Collection doesn't have parent
                break
        return path


class EntryBuilder:
    """Builder for creating bibliography entries."""

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._tags: set[str] = set()
        self._collections: set[str] = set()

    def key(self, key: str) -> "EntryBuilder":
        """Set entry key."""
        self._data["key"] = key
        return self

    def type(self, entry_type: EntryType) -> "EntryBuilder":
        """Set entry type."""
        self._data["type"] = entry_type
        return self

    def author(self, author: str) -> "EntryBuilder":
        """Set author field."""
        self._data["author"] = author
        return self

    def title(self, title: str) -> "EntryBuilder":
        """Set title field."""
        self._data["title"] = title
        return self

    def year(self, year: int | str) -> "EntryBuilder":
        """Set year field."""
        if isinstance(year, str):
            raise TypeError("year must be int")
        self._data["year"] = year
        return self

    def journal(self, journal: str) -> "EntryBuilder":
        """Set journal field."""
        self._data["journal"] = journal
        return self

    def volume(self, volume: str) -> "EntryBuilder":
        """Set volume field."""
        self._data["volume"] = volume
        return self

    def number(self, number: str) -> "EntryBuilder":
        """Set number field."""
        self._data["number"] = number
        return self

    def pages(self, pages: str) -> "EntryBuilder":
        """Set pages field."""
        self._data["pages"] = pages
        return self

    def month(self, month: str) -> "EntryBuilder":
        """Set month field."""
        self._data["month"] = month
        return self

    def doi(self, doi: str) -> "EntryBuilder":
        """Set DOI field."""
        self._data["doi"] = doi
        return self

    def url(self, url: str) -> "EntryBuilder":
        """Set URL field."""
        self._data["url"] = url
        return self

    def abstract(self, abstract: str) -> "EntryBuilder":
        """Set abstract field."""
        self._data["abstract"] = abstract
        return self

    def keywords(self, keywords: list[str] | str) -> "EntryBuilder":
        """Set keywords field."""
        if isinstance(keywords, str):
            raise TypeError("keywords must be list")
        self._data["keywords"] = keywords
        return self

    def chapter(self, chapter: str) -> "EntryBuilder":
        """Set chapter field."""
        self._data["chapter"] = chapter
        return self

    def crossref(self, crossref: str) -> "EntryBuilder":
        """Set crossref field."""
        self._data["crossref"] = crossref
        return self

    def custom_field(self, name: str, value: Any) -> "EntryBuilder":
        """Set a custom field."""
        # Entry model doesn't support arbitrary fields, but we can try
        self._data[name] = value
        return self

    def clear_field(self, field: str) -> "EntryBuilder":
        """Clear a field."""
        self._data.pop(field, None)
        return self

    def tag(self, tag: str) -> "EntryBuilder":
        """Add a tag."""
        self._tags.add(tag)
        return self

    def collection(self, collection: str) -> "EntryBuilder":
        """Add to a collection."""
        self._collections.add(collection)
        return self

    def auto_key(self) -> "EntryBuilder":
        """Auto-generate key from author/year/title."""
        author = self._data.get("author", "")
        year = self._data.get("year", "")
        title = self._data.get("title", "")

        # Extract first author's last name
        if author:
            # Parse first author
            authors = re.split(r"\s+and\s+", author)
            if authors:
                parsed = NameParser.parse(authors[0])
                if parsed.last:
                    author_part = "".join(parsed.last).lower()
                    # Remove non-alphanumeric
                    author_part = re.sub(r"[^a-z0-9]", "", author_part)
                else:
                    author_part = "unknown"
            else:
                author_part = "unknown"
        else:
            author_part = "unknown"

        # Year part
        year_part = str(year) if year else "nodate"

        # Title part - first word
        if title:
            # Remove articles and get first word
            title_words = re.findall(r"\b\w+\b", title.lower())
            # Skip common articles
            for word in title_words:
                if word not in ["the", "a", "an"]:
                    title_part = word
                    break
            else:
                title_part = "untitled"
        else:
            title_part = "untitled"

        # Combine parts
        key = f"{author_part}{year_part}{title_part}"
        self._data["key"] = key
        return self

    def build(self) -> Entry | EntryWithExtras | Any:  # Any for EntryWithCustom
        """Build the entry."""
        # Validate required fields
        if "key" not in self._data:
            raise ValueError("key is required")
        if "type" not in self._data:
            raise ValueError("type is required")

        # Don't validate key format here - let validators handle it
        # This allows building entries with issues that can be fixed later

        # Add tags if any
        if self._tags:
            self._data["tags"] = tuple(self._tags)

        # Create entry - try with custom fields first
        try:
            entry = Entry(**self._data)
        except TypeError:
            # If custom fields caused an error, create without them
            # and add them as attributes later
            known_fields = {
                "key",
                "type",
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
                "month",
                "note",
                "number",
                "organization",
                "pages",
                "publisher",
                "school",
                "series",
                "title",
                "type_",
                "volume",
                "year",
                "doi",
                "url",
                "isbn",
                "issn",
                "eprint",
                "archiveprefix",
                "primaryclass",
                "abstract",
                "keywords",
                "file",
                "annotation",
                "comment",
                "timestamp",
                "added",
                "modified",
                "tags",
            }

            base_data = {k: v for k, v in self._data.items() if k in known_fields}
            custom_data = {k: v for k, v in self._data.items() if k not in known_fields}

            entry = Entry(**base_data)

            # If we have custom fields, we need to create a wrapper
            if custom_data:
                # Create a simple wrapper that delegates to entry
                class EntryWithCustom:
                    def __init__(self, entry, **custom):
                        self._entry = entry
                        for k, v in custom.items():
                            setattr(self, k, v)

                    def __getattr__(self, name):
                        # First check custom attributes
                        if hasattr(self, name):
                            return getattr(self, name)
                        # Then delegate to wrapped entry
                        return getattr(self._entry, name)

                entry_with_custom = EntryWithCustom(entry, **custom_data)
                # If we have collections, wrap it further
                if self._collections:
                    return EntryWithExtras(entry_with_custom, self._collections)
                return entry_with_custom

        # If we have collections, wrap the entry
        if self._collections:
            return EntryWithExtras(entry, self._collections)

        return entry

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntryBuilder":
        """Create builder from dictionary."""
        builder = cls()
        builder._data = data.copy()
        # Extract tags and collections if present
        if "tags" in data:
            builder._tags = set(data["tags"])
            builder._data.pop("tags")
        if "collections" in data:
            builder._collections = set(data["collections"])
            builder._data.pop("collections")
        return builder

    @classmethod
    def from_entry(cls, entry: Entry) -> "EntryBuilder":
        """Create builder from existing entry."""
        data = entry.to_dict()
        # Preserve the EntryType enum
        data["type"] = entry.type
        return cls.from_dict(data)


class CollectionBuilder:
    """Builder for creating collections."""

    def __init__(self):
        self._name: str | None = None
        self._description: str | None = None
        self._parent: Collection | CollectionWithExtras | None = None
        self._metadata: dict[str, Any] = {}
        self._entry_keys: set[str] = set()
        self._smart_filters: list[dict[str, Any]] = []

    def name(self, name: str) -> "CollectionBuilder":
        """Set collection name."""
        self._name = name
        return self

    def description(self, description: str) -> "CollectionBuilder":
        """Set collection description."""
        self._description = description
        return self

    def parent(self, parent: Collection | CollectionWithExtras) -> "CollectionBuilder":
        """Set parent collection."""
        self._parent = parent
        return self

    def metadata(self, key: str, value: Any) -> "CollectionBuilder":
        """Add metadata."""
        self._metadata[key] = value
        return self

    def icon(self, icon: str) -> "CollectionBuilder":
        """Set collection icon."""
        self._metadata["icon"] = icon
        return self

    def color(self, color: str) -> "CollectionBuilder":
        """Set collection color."""
        self._metadata["color"] = color
        return self

    def add_entry(self, entry: Entry) -> "CollectionBuilder":
        """Add a single entry."""
        self._entry_keys.add(entry.key)
        return self

    def add_entries(self, entries: list[Entry]) -> "CollectionBuilder":
        """Add multiple entries."""
        for entry in entries:
            self._entry_keys.add(entry.key)
        return self

    def remove_entry_keys(self, keys: list[str]) -> "CollectionBuilder":
        """Remove entries by key."""
        for key in keys:
            self._entry_keys.discard(key)
        return self

    def smart_filter(
        self, field: str, operator: str, value: Any
    ) -> "CollectionBuilder":
        """Add a smart filter."""
        # Validate operator
        valid_operators = ["=", "!=", ">", ">=", "<", "<=", "contains", "in", "not in"]
        if operator not in valid_operators:
            raise ValueError(f"Invalid operator: {operator}")

        # Validate operator for field type
        if operator == "contains" and isinstance(value, int | float):
            raise ValueError("Cannot use 'contains' operator with numeric value")

        self._smart_filters.append(
            {"field": field, "operator": operator, "value": value}
        )
        return self

    def clear_smart_filters(self) -> "CollectionBuilder":
        """Clear all smart filters."""
        self._smart_filters.clear()
        return self

    def build(self) -> CollectionWithExtras:
        """Build the collection."""
        # Validate
        if not self._name:
            raise ValueError("name is required")

        # Create collection data
        data = {
            "name": self._name,
            "description": self._description,
        }

        # Add parent relationship
        if self._parent:
            if isinstance(self._parent, CollectionWithExtras):
                data["parent_id"] = self._parent._collection.id
            else:
                data["parent_id"] = self._parent.id

        # Add entries if any
        if self._entry_keys:
            data["entry_keys"] = tuple(sorted(self._entry_keys))

        # Create base collection
        collection = Collection(**data)

        # Wrap with extras
        wrapped = CollectionWithExtras(
            collection,
            parent=self._parent,
            metadata=self._metadata.copy(),
            smart_filters=self._smart_filters.copy(),
        )

        # Check for self-parent (this check should happen after building)
        if self._parent:
            parent_collection = (
                self._parent._collection
                if isinstance(self._parent, CollectionWithExtras)
                else self._parent
            )
            if parent_collection == collection:
                raise ValueError("Cannot be own parent")

        return wrapped

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollectionBuilder":
        """Create builder from dictionary."""
        builder = cls()
        if "name" in data:
            builder.name(data["name"])
        if "description" in data:
            builder.description(data["description"])
        if "metadata" in data:
            for key, value in data["metadata"].items():
                builder.metadata(key, value)
        return builder

    @classmethod
    def from_collection(
        cls, collection: Collection | CollectionWithExtras
    ) -> "CollectionBuilder":
        """Create builder from existing collection."""
        builder = cls()
        builder.name(collection.name)
        if collection.description:
            builder.description(collection.description)

        # Copy metadata if it's a wrapped collection
        if isinstance(collection, CollectionWithExtras):
            for key, value in collection.metadata.items():
                builder.metadata(key, value)

        return builder

    @classmethod
    def build_tree(cls, tree_dict: dict[str, Any]) -> list[CollectionWithExtras]:
        """Build a tree of collections from nested dictionary."""
        collections = []

        def build_level(
            data: dict[str, Any], parent: CollectionWithExtras | None = None
        ):
            for name, config in data.items():
                if isinstance(config, dict):
                    # Extract metadata if present
                    metadata = config.get("metadata", {})
                    # Remove metadata from config to get children
                    children = {k: v for k, v in config.items() if k != "metadata"}

                    # Build this collection
                    builder = cls().name(name)
                    if parent:
                        builder.parent(parent)
                    for key, value in metadata.items():
                        builder.metadata(key, value)

                    collection = builder.build()
                    collections.append(collection)

                    # Build children
                    if children:
                        build_level(children, collection)

        build_level(tree_dict)
        return collections
