"""Tests for collection and organization system."""

import json
import tempfile
from pathlib import Path

import pytest

from bibmgr.collections.manager import (
    CollectionManager,
    FileCollectionRepository,
)
from bibmgr.collections.models import (
    Collection,
    CollectionPredicate,
    CollectionQuery,
    PredicateOperator,
    SmartCollection,
)
from bibmgr.collections.tags import TagHierarchy, TagManager


class TestCollection:
    """Test Collection model."""

    def test_create_collection(self):
        """Test creating a collection."""
        collection = Collection(
            name="Research Papers",
            description="Papers for my research",
        )

        assert collection.name == "Research Papers"
        assert collection.description == "Papers for my research"
        assert collection.parent_id is None
        assert len(collection.entry_keys) == 0
        assert collection.id is not None

    def test_add_entry(self):
        """Test adding entries to collection."""
        collection = Collection(name="Test")

        updated = collection.add_entry("paper1")
        assert "paper1" in updated.entry_keys
        assert len(updated.entry_keys) == 1

        updated = updated.add_entry("paper2")
        assert len(updated.entry_keys) == 2

    def test_remove_entry(self):
        """Test removing entries from collection."""
        collection = Collection(name="Test", entry_keys={"paper1", "paper2", "paper3"})

        updated = collection.remove_entry("paper2")
        assert "paper2" not in updated.entry_keys
        assert len(updated.entry_keys) == 2

    def test_rename_collection(self):
        """Test renaming a collection."""
        collection = Collection(name="Old Name")

        updated = collection.rename("New Name")
        assert updated.name == "New Name"
        assert updated.updated_at > collection.updated_at

    def test_move_collection(self):
        """Test moving collection to new parent."""
        collection = Collection(name="Child")

        updated = collection.move_to("parent-id")
        assert updated.parent_id == "parent-id"


class TestCollectionPredicate:
    """Test collection predicates."""

    def test_equals_predicate(self):
        """Test EQUALS operator."""
        pred = CollectionPredicate(
            field="type", operator=PredicateOperator.EQUALS, value="article"
        )

        class Entry:
            type = "article"

        assert pred.matches(Entry())

        Entry.type = "book"
        assert not pred.matches(Entry())

    def test_contains_predicate(self):
        """Test CONTAINS operator."""
        pred = CollectionPredicate(
            field="title", operator=PredicateOperator.CONTAINS, value="quantum"
        )

        class Entry:
            title = "Quantum Computing Advances"

        assert pred.matches(Entry())

        Entry.title = "Classical Computing"
        assert not pred.matches(Entry())

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        pred = CollectionPredicate(
            field="author",
            operator=PredicateOperator.CONTAINS,
            value="einstein",
            case_sensitive=False,
        )

        class Entry:
            author = "Albert EINSTEIN"

        assert pred.matches(Entry())

    def test_exists_predicate(self):
        """Test EXISTS operator."""
        pred = CollectionPredicate(
            field="doi", operator=PredicateOperator.EXISTS, value=None
        )

        class Entry:
            doi = "10.1234/example"

        assert pred.matches(Entry())

        class EntryNoDoi:
            doi = None

        assert not pred.matches(EntryNoDoi())


class TestCollectionQuery:
    """Test collection queries."""

    def test_and_combinator(self):
        """Test AND combination of predicates."""
        query = CollectionQuery(
            predicates=[
                CollectionPredicate(
                    field="type", operator=PredicateOperator.EQUALS, value="article"
                ),
                CollectionPredicate(
                    field="year", operator=PredicateOperator.GREATER_THAN, value=2020
                ),
            ],
            combinator="AND",
        )

        class Entry:
            type = "article"
            year = 2022

        assert query.matches(Entry())

        Entry.year = 2019
        assert not query.matches(Entry())

    def test_or_combinator(self):
        """Test OR combination of predicates."""
        query = CollectionQuery(
            predicates=[
                CollectionPredicate(
                    field="author",
                    operator=PredicateOperator.CONTAINS,
                    value="Einstein",
                ),
                CollectionPredicate(
                    field="author", operator=PredicateOperator.CONTAINS, value="Feynman"
                ),
            ],
            combinator="OR",
        )

        class Entry:
            author = "Richard Feynman"

        assert query.matches(Entry())

        Entry.author = "Albert Einstein"
        assert query.matches(Entry())

        Entry.author = "Marie Curie"
        assert not query.matches(Entry())


class TestSmartCollection:
    """Test smart collections."""

    def test_create_smart_collection(self):
        """Test creating a smart collection."""
        query = CollectionQuery(
            predicates=[
                CollectionPredicate(
                    field="year", operator=PredicateOperator.GREATER_THAN, value=2020
                )
            ]
        )

        collection = SmartCollection(
            name="Recent Papers", query=query, auto_update=True
        )

        assert collection.name == "Recent Papers"
        assert collection.query == query
        assert collection.auto_update is True

    def test_refresh_smart_collection(self):
        """Test refreshing smart collection."""
        query = CollectionQuery(
            predicates=[
                CollectionPredicate(
                    field="type", operator=PredicateOperator.EQUALS, value="article"
                )
            ]
        )

        collection = SmartCollection(name="Articles", query=query)

        class Entry:
            def __init__(self, key, type_):
                self.key = key
                self.type = type_

        entries = [
            Entry("paper1", "article"),
            Entry("paper2", "book"),
            Entry("paper3", "article"),
        ]

        updated = collection.refresh(entries)
        assert len(updated.entry_keys) == 2
        assert "paper1" in updated.entry_keys
        assert "paper3" in updated.entry_keys
        assert "paper2" not in updated.entry_keys


class TestCollectionManager:
    """Test collection manager."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create collection manager."""
        repo = FileCollectionRepository(temp_dir)
        return CollectionManager(repo)

    def test_create_collection(self, manager):
        """Test creating a collection."""
        collection = manager.create_collection(
            name="My Collection", description="Test collection"
        )

        assert collection.name == "My Collection"
        assert collection.description == "Test collection"

        # Verify it was saved
        retrieved = manager.get_collection(collection.id)
        assert retrieved is not None
        assert retrieved.name == "My Collection"

    def test_create_hierarchical_collections(self, manager):
        """Test creating parent-child collections."""
        parent = manager.create_collection("Parent")
        child = manager.create_collection("Child", parent_id=parent.id)

        assert child.parent_id == parent.id

    def test_update_collection(self, manager):
        """Test updating a collection."""
        collection = manager.create_collection("Original")

        updated = manager.update_collection(
            collection.id, name="Updated", description="New description"
        )

        assert updated.name == "Updated"
        assert updated.description == "New description"

    def test_delete_collection(self, manager):
        """Test deleting a collection."""
        collection = manager.create_collection("To Delete")

        assert manager.delete_collection(collection.id)
        assert manager.get_collection(collection.id) is None

    def test_delete_collection_cascade(self, manager):
        """Test cascade deletion."""
        parent = manager.create_collection("Parent")
        child1 = manager.create_collection("Child1", parent_id=parent.id)
        child2 = manager.create_collection("Child2", parent_id=parent.id)

        manager.delete_collection(parent.id, cascade=True)

        assert manager.get_collection(parent.id) is None
        assert manager.get_collection(child1.id) is None
        assert manager.get_collection(child2.id) is None

    def test_add_remove_entries(self, manager):
        """Test adding and removing entries."""
        collection = manager.create_collection("Test")

        # Add entries
        updated = manager.add_to_collection(collection.id, "entry1")
        assert "entry1" in updated.entry_keys

        updated = manager.add_to_collection(collection.id, "entry2")
        assert len(updated.entry_keys) == 2

        # Remove entry
        updated = manager.remove_from_collection(collection.id, "entry1")
        assert "entry1" not in updated.entry_keys
        assert len(updated.entry_keys) == 1

    def test_move_collection(self, manager):
        """Test moving collections."""
        parent1 = manager.create_collection("Parent1")
        parent2 = manager.create_collection("Parent2")
        child = manager.create_collection("Child", parent_id=parent1.id)

        # Move to different parent
        moved = manager.move_collection(child.id, parent2.id)
        assert moved.parent_id == parent2.id

        # Move to root
        moved = manager.move_collection(child.id, None)
        assert moved.parent_id is None

    def test_prevent_cycle(self, manager):
        """Test cycle prevention in hierarchy."""
        parent = manager.create_collection("Parent")
        child = manager.create_collection("Child", parent_id=parent.id)

        # Try to make parent a child of its own child
        with pytest.raises(ValueError, match="cycle"):
            manager.move_collection(parent.id, child.id)

        # Try to make collection its own parent
        with pytest.raises(ValueError, match="own parent"):
            manager.move_collection(parent.id, parent.id)


class TestTagHierarchy:
    """Test tag hierarchy."""

    def test_add_tag(self):
        """Test adding tags."""
        hierarchy = TagHierarchy()

        tag = hierarchy.add_tag("ml/nlp/bert")
        assert tag.path == "ml/nlp/bert"

        # Parent tags should be created
        assert hierarchy.get_tag("ml") is not None
        assert hierarchy.get_tag("ml/nlp") is not None

    def test_get_children(self):
        """Test getting child tags."""
        hierarchy = TagHierarchy()

        hierarchy.add_tag("ml/nlp/bert")
        hierarchy.add_tag("ml/nlp/gpt")
        hierarchy.add_tag("ml/cv/resnet")

        nlp_children = hierarchy.get_children("ml/nlp")
        assert len(nlp_children) == 2
        assert "ml/nlp/bert" in nlp_children
        assert "ml/nlp/gpt" in nlp_children

        ml_children = hierarchy.get_children("ml")
        assert "ml/nlp" in ml_children
        assert "ml/cv" in ml_children

    def test_get_descendants(self):
        """Test getting all descendants."""
        hierarchy = TagHierarchy()

        hierarchy.add_tag("ml/nlp/bert/base")
        hierarchy.add_tag("ml/nlp/bert/large")
        hierarchy.add_tag("ml/nlp/gpt")

        descendants = hierarchy.get_descendants("ml")
        assert len(descendants) == 5  # nlp, bert, base, large, gpt

    def test_get_ancestors(self):
        """Test getting ancestors."""
        hierarchy = TagHierarchy()

        ancestors = hierarchy.get_ancestors("ml/nlp/bert/base")
        assert ancestors == ["ml", "ml/nlp", "ml/nlp/bert"]

    def test_rename_tag(self):
        """Test renaming tags."""
        hierarchy = TagHierarchy()

        hierarchy.add_tag("old/path/tag")
        hierarchy.add_tag("old/path/tag/child")

        assert hierarchy.rename_tag("old/path", "new/path")

        assert hierarchy.get_tag("new/path/tag") is not None
        assert hierarchy.get_tag("new/path/tag/child") is not None
        assert hierarchy.get_tag("old/path/tag") is None

    def test_merge_tags(self):
        """Test merging tags."""
        hierarchy = TagHierarchy()

        hierarchy.add_tag("tag1")
        hierarchy.add_tag("tag2")
        hierarchy.usage_count["tag1"] = 5
        hierarchy.usage_count["tag2"] = 3

        assert hierarchy.merge_tags("tag1", "tag2")

        assert hierarchy.get_tag("tag1") is None
        assert hierarchy.usage_count["tag2"] == 8

    def test_delete_tag(self):
        """Test deleting tags."""
        hierarchy = TagHierarchy()

        hierarchy.add_tag("parent/child1")
        hierarchy.add_tag("parent/child2")

        # Delete without cascade
        assert hierarchy.delete_tag("parent")
        assert hierarchy.get_tag("parent") is None
        assert hierarchy.get_tag("parent/child1") is not None

        # Delete with cascade
        hierarchy.add_tag("other/sub1/sub2")
        assert hierarchy.delete_tag("other", cascade=True)
        assert hierarchy.get_tag("other/sub1") is None
        assert hierarchy.get_tag("other/sub1/sub2") is None

    def test_co_occurrence(self):
        """Test tag co-occurrence tracking."""
        hierarchy = TagHierarchy()

        hierarchy.record_usage(["ml", "nlp", "bert"])
        hierarchy.record_usage(["ml", "nlp", "gpt"])
        hierarchy.record_usage(["ml", "cv"])

        assert hierarchy.usage_count["ml"] == 3
        assert hierarchy.usage_count["nlp"] == 2

        assert hierarchy.co_occurrence["ml"]["nlp"] == 2
        assert hierarchy.co_occurrence["ml"]["cv"] == 1
        assert hierarchy.co_occurrence["nlp"]["bert"] == 1

    def test_suggest_tags(self):
        """Test tag suggestions."""
        hierarchy = TagHierarchy()

        # Set up co-occurrence data
        hierarchy.record_usage(["python", "ml", "numpy"])
        hierarchy.record_usage(["python", "ml", "pandas"])
        hierarchy.record_usage(["python", "web", "django"])
        hierarchy.record_usage(["ml", "numpy", "scipy"])

        suggestions = hierarchy.suggest_tags(["python"], limit=3)
        assert "ml" in suggestions  # Most co-occurred with python

        suggestions = hierarchy.suggest_tags(["ml"], limit=2)
        assert "numpy" in suggestions  # Co-occurred with ml


class TestTagManager:
    """Test tag manager."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create tag manager."""
        return TagManager(temp_dir)

    def test_add_tag(self, manager):
        """Test adding tags."""
        tag = manager.add_tag(
            "research/ml", color="#FF0000", description="Machine Learning"
        )

        assert tag.path == "research/ml"
        assert tag.color == "#FF0000"
        assert tag.description == "Machine Learning"

        # Verify persistence
        manager2 = TagManager(manager.base_path)
        retrieved = manager2.hierarchy.get_tag("research/ml")
        assert retrieved is not None
        assert retrieved.color == "#FF0000"

    def test_update_tag(self, manager):
        """Test updating tags."""
        manager.add_tag("test", color="#000000")

        updated = manager.update_tag("test", color="#FFFFFF", description="Updated")

        assert updated.color == "#FFFFFF"
        assert updated.description == "Updated"

    def test_tag_entry(self, manager):
        """Test tagging entries."""
        manager.tag_entry("entry1", ["ml", "nlp", "bert"])

        stats = manager.hierarchy.get_stats("ml")
        assert stats.count == 1

        # Tag another entry
        manager.tag_entry("entry2", ["ml", "cv"])

        stats = manager.hierarchy.get_stats("ml")
        assert stats.count == 2

    def test_export_tags(self, manager):
        """Test exporting tags."""
        manager.add_tag("root/child1")
        manager.add_tag("root/child2")
        manager.tag_entry("e1", ["root/child1"])

        # JSON export
        json_export = manager.export_tags("json")
        data = json.loads(json_export)
        assert len(data["tags"]) == 3  # root, child1, child2

        # Text export
        text_export = manager.export_tags("text")
        assert "root" in text_export
        assert "  child1" in text_export  # Indented
