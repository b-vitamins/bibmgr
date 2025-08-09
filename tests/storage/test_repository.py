"""Tests for repository pattern implementation."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from bibmgr.core.models import Collection, Entry, EntryType


class TestEntryRepository:
    """Test the entry repository interface."""

    def test_find_existing_entry(self, mock_backend, sample_entry):
        """Finding an existing entry returns the entry."""
        mock_backend.data[sample_entry.key] = sample_entry.to_dict()

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        found = repo.find(sample_entry.key)
        assert found is not None
        assert found.key == sample_entry.key
        assert found.title == sample_entry.title
        assert found.author == sample_entry.author

    def test_find_nonexistent_entry_returns_none(self, mock_backend):
        """Finding a non-existent entry returns None."""
        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        assert repo.find("nonexistent") is None

    def test_find_all_returns_all_entries(self, mock_backend, sample_entries):
        """find_all returns all stored entries."""
        for entry in sample_entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        all_entries = repo.find_all()
        assert len(all_entries) == len(sample_entries)
        assert {e.key for e in all_entries} == {e.key for e in sample_entries}

    def test_save_new_entry(self, mock_backend, sample_entry):
        """Saving a new entry stores it in backend."""
        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        repo.save(sample_entry)

        assert sample_entry.key in mock_backend.data
        stored_data = mock_backend.data[sample_entry.key]
        assert stored_data["title"] == sample_entry.title

    def test_save_validates_entry(self, mock_backend):
        """Saving an invalid entry raises ValueError."""
        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        invalid_entry = Entry(
            key="invalid",
            type=EntryType.ARTICLE,
            title="Only Title",
        )

        with pytest.raises(ValueError, match="validation failed"):
            repo.save(invalid_entry)

    def test_save_updates_existing_entry(self, mock_backend, sample_entry):
        """Saving an existing entry updates it."""
        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        repo.save(sample_entry)

        import msgspec

        updated = msgspec.structs.replace(sample_entry, title="Updated Title")
        repo.save(updated)

        assert len(mock_backend.data) == 1
        assert mock_backend.data[sample_entry.key]["title"] == "Updated Title"

    def test_delete_existing_entry(self, mock_backend, sample_entry):
        """Deleting an existing entry removes it."""
        mock_backend.data[sample_entry.key] = sample_entry.to_dict()

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        assert repo.delete(sample_entry.key) is True
        assert sample_entry.key not in mock_backend.data

    def test_delete_nonexistent_entry(self, mock_backend):
        """Deleting non-existent entry returns False."""
        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        assert repo.delete("nonexistent") is False

    def test_exists_check(self, mock_backend, sample_entry):
        """exists() correctly reports entry existence."""
        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        assert repo.exists(sample_entry.key) is False

        mock_backend.data[sample_entry.key] = sample_entry.to_dict()
        assert repo.exists(sample_entry.key) is True

    def test_count_entries(self, mock_backend, sample_entries):
        """count() returns correct number of entries."""
        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        assert repo.count() == 0

        for i, entry in enumerate(sample_entries):
            mock_backend.data[entry.key] = entry.to_dict()
            assert repo.count() == i + 1


class TestQueryMethods:
    """Test repository query methods."""

    def test_find_by_type(self, mock_backend, sample_entries):
        """find_by_type returns entries of specific type."""
        for entry in sample_entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        articles = repo.find_by_type("article")
        assert all(e.type == EntryType.ARTICLE for e in articles)
        assert len(articles) == sum(
            1 for e in sample_entries if e.type == EntryType.ARTICLE
        )

        books = repo.find_by_type("book")
        assert all(e.type == EntryType.BOOK for e in books)
        assert len(books) == sum(1 for e in sample_entries if e.type == EntryType.BOOK)

    def test_find_by_year(self, mock_backend):
        """find_by_year returns entries from specific year."""
        entries = [
            Entry(key="a", type=EntryType.MISC, title="A", year=2020),
            Entry(key="b", type=EntryType.MISC, title="B", year=2021),
            Entry(key="c", type=EntryType.MISC, title="C", year=2020),
        ]

        for entry in entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        entries_2020 = repo.find_by_year(2020)
        assert len(entries_2020) == 2
        assert all(e.year == 2020 for e in entries_2020)

    def test_find_by_author_substring(self, mock_backend):
        """find_by_author finds entries with author substring match."""
        entries = [
            Entry(key="k1", type=EntryType.MISC, author="Donald Knuth", title="Book 1"),
            Entry(
                key="k2", type=EntryType.MISC, author="Donald E. Knuth", title="Book 2"
            ),
            Entry(
                key="l1", type=EntryType.MISC, author="Leslie Lamport", title="Book 3"
            ),
        ]

        for entry in entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        knuth_entries = repo.find_by_author("Knuth")
        assert len(knuth_entries) == 2
        assert all(e.author and "knuth" in e.author.lower() for e in knuth_entries)

        donald_entries = repo.find_by_author("Donald")
        assert len(donald_entries) == 2

    def test_find_recent_entries(self, mock_backend):
        """find_recent returns most recently added entries."""
        now = datetime.now()
        entries = []

        for i in range(5):
            entry_data = {
                "key": f"entry{i}",
                "type": "misc",
                "title": f"Entry {i}",
                "added": (now - timedelta(days=i)).isoformat(),
            }
            mock_backend.data[f"entry{i}"] = entry_data
            entries.append(entry_data)

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        recent = repo.find_recent(limit=3)
        assert len(recent) == 3
        assert recent[0].key == "entry0"
        assert recent[1].key == "entry1"
        assert recent[2].key == "entry2"


class TestQueryBuilder:
    """Test the query builder interface."""

    def test_simple_equality_query(self, mock_backend, sample_entries):
        """QueryBuilder can build simple equality queries."""
        for entry in sample_entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository, QueryBuilder

        repo = EntryRepository(mock_backend)

        query = QueryBuilder().where("year", "=", 1950)
        results = repo.find_by(query)

        assert len(results) == 1
        assert results[0].year == 1950
        assert results[0].key == "turing1950"

    def test_comparison_operators(self, mock_backend, sample_entries):
        """QueryBuilder supports comparison operators."""
        for entry in sample_entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository, QueryBuilder

        repo = EntryRepository(mock_backend)

        query = QueryBuilder().where("year", ">", 1980)
        results = repo.find_by(query)
        assert all(e.year and e.year > 1980 for e in results)

        query = QueryBuilder().where("year", "<=", 1968)
        results = repo.find_by(query)
        assert all(e.year and e.year <= 1968 for e in results)

    def test_string_contains_query(self, mock_backend, sample_entries):
        """QueryBuilder supports string contains operator."""
        for entry in sample_entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository, QueryBuilder

        repo = EntryRepository(mock_backend)

        query = QueryBuilder().where("title", "contains", "Statement")
        results = repo.find_by(query)

        assert len(results) == 1
        assert results[0].title and "Statement" in results[0].title

    def test_multiple_conditions(self, mock_backend, sample_entries):
        """QueryBuilder can combine multiple conditions."""
        for entry in sample_entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository, QueryBuilder

        repo = EntryRepository(mock_backend)

        query = (
            QueryBuilder()
            .where("type", "=", EntryType.ARTICLE.value)
            .where("year", "<", 1960)
        )
        results = repo.find_by(query)

        assert all(e.type == EntryType.ARTICLE for e in results)
        assert all(e.year and e.year < 1960 for e in results)
        assert len(results) == 2

    def test_ordering(self, mock_backend, sample_entries):
        """QueryBuilder supports result ordering."""
        for entry in sample_entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository, QueryBuilder

        repo = EntryRepository(mock_backend)

        query = QueryBuilder().order_by("year", ascending=True)
        results = repo.find_by(query)

        years = [e.year for e in results if e.year is not None]
        assert years == sorted(years)

        query = QueryBuilder().order_by("year", ascending=False)
        results = repo.find_by(query)

        years = [e.year for e in results if e.year is not None]
        assert years == sorted(years, reverse=True)

    def test_limit_and_offset(self, mock_backend, sample_entries):
        """QueryBuilder supports limit and offset."""
        for entry in sample_entries:
            mock_backend.data[entry.key] = entry.to_dict()

        from bibmgr.storage.repository import EntryRepository, QueryBuilder

        repo = EntryRepository(mock_backend)

        query = QueryBuilder().order_by("key").limit(2)
        results = repo.find_by(query)
        assert len(results) == 2

        query = QueryBuilder().order_by("key").offset(2).limit(2)
        results = repo.find_by(query)
        assert len(results) == 2

        all_query = QueryBuilder().order_by("key")
        all_results = repo.find_by(all_query)
        assert results[0].key == all_results[2].key


class TestCollectionRepository:
    """Test collection repository functionality."""

    def test_save_and_find_collection(self, mock_backend, sample_collection):
        """Collections can be saved and retrieved."""
        from bibmgr.storage.repository import CollectionRepository

        repo = CollectionRepository(mock_backend)

        repo.save(sample_collection)

        found = repo.find(str(sample_collection.id))
        assert found is not None
        assert found.name == sample_collection.name
        assert found.entry_keys == sample_collection.entry_keys

    def test_find_all_collections(self, mock_backend, nested_collections):
        """find_all returns all collections."""
        from bibmgr.storage.repository import CollectionRepository

        repo = CollectionRepository(mock_backend)

        for collection in nested_collections:
            repo.save(collection)

        all_collections = repo.find_all()
        assert len(all_collections) == len(nested_collections)

    def test_delete_collection(self, mock_backend, sample_collection):
        """Collections can be deleted."""
        from bibmgr.storage.repository import CollectionRepository

        repo = CollectionRepository(mock_backend)

        repo.save(sample_collection)
        assert repo.find(str(sample_collection.id)) is not None

        assert repo.delete(str(sample_collection.id)) is True
        assert repo.find(str(sample_collection.id)) is None

    def test_find_by_parent(self, mock_backend, nested_collections):
        """find_by_parent returns child collections."""
        from bibmgr.storage.repository import CollectionRepository

        repo = CollectionRepository(mock_backend)

        for collection in nested_collections:
            repo.save(collection)

        roots = repo.find_by_parent(None)
        assert len(roots) == 1
        assert roots[0].name == "Computer Science"

        children = repo.find_by_parent(str(roots[0].id))
        assert len(children) == 2
        assert {c.name for c in children} == {"Algorithms", "Machine Learning"}

    def test_find_smart_collections(self, mock_backend):
        """find_smart_collections returns only query-based collections."""
        from bibmgr.storage.repository import CollectionRepository

        repo = CollectionRepository(mock_backend)

        manual = Collection(name="Manual", entry_keys=("a", "b"))
        smart = Collection(name="Smart", query="year > 2020")

        repo.save(manual)
        repo.save(smart)

        smart_collections = repo.find_smart_collections()
        assert len(smart_collections) == 1
        assert smart_collections[0].name == "Smart"
        assert smart_collections[0].is_smart


class TestRepositoryManager:
    """Test the repository manager that coordinates operations."""

    def test_transaction_support(self, mock_backend):
        """Repository manager provides transaction support."""
        from bibmgr.storage.repository import RepositoryManager

        manager = RepositoryManager(mock_backend)

        assert mock_backend.transaction_depth == 0

        with manager.transaction():
            assert mock_backend.transaction_depth == 1
            with manager.transaction():
                assert mock_backend.transaction_depth == 2
            assert mock_backend.transaction_depth == 1

        assert mock_backend.transaction_depth == 0

    def test_import_entries_validates(self, mock_backend, sample_entries):
        """import_entries validates entries before importing."""
        from bibmgr.storage.repository import RepositoryManager

        manager = RepositoryManager(mock_backend)

        entries = sample_entries[:2] + [
            Entry(key="invalid", type=EntryType.ARTICLE, title="No author/journal/year")
        ]

        results = manager.import_entries(entries)

        assert results[sample_entries[0].key] is True
        assert results[sample_entries[1].key] is True

        assert results["invalid"] is False
        assert len(mock_backend.data) == 2

    def test_import_entries_skip_validation(self, mock_backend):
        """import_entries can skip validation if requested."""
        from bibmgr.storage.repository import RepositoryManager

        manager = RepositoryManager(mock_backend)

        invalid_entry = Entry(
            key="invalid", type=EntryType.ARTICLE, title="No required fields"
        )

        results = manager.import_entries([invalid_entry], skip_validation=True)

        assert results["invalid"] is True
        assert "invalid" in mock_backend.data

    def test_export_entries_all(self, mock_backend, sample_entries):
        """export_entries exports all entries when no keys specified."""
        from bibmgr.storage.repository import RepositoryManager

        manager = RepositoryManager(mock_backend)

        manager.import_entries(sample_entries)

        exported = manager.export_entries()
        assert len(exported) == len(sample_entries)
        assert {e.key for e in exported} == {e.key for e in sample_entries}

    def test_export_entries_subset(self, mock_backend, sample_entries):
        """export_entries can export specific entries."""
        from bibmgr.storage.repository import RepositoryManager

        manager = RepositoryManager(mock_backend)

        manager.import_entries(sample_entries)

        keys_to_export = [sample_entries[0].key, sample_entries[2].key]
        exported = manager.export_entries(keys_to_export)

        assert len(exported) == 2
        assert {e.key for e in exported} == set(keys_to_export)

    def test_get_statistics(self, mock_backend, sample_entries):
        """get_statistics returns repository statistics."""
        from bibmgr.storage.repository import RepositoryManager

        manager = RepositoryManager(mock_backend)

        manager.import_entries(sample_entries)

        collection = Collection(name="Test", entry_keys=("a", "b"))
        manager.collections.save(collection)

        stats = manager.get_statistics()

        assert stats["total_entries"] == len(sample_entries)
        assert "entries_by_type" in stats
        assert stats["entries_by_type"]["article"] == 3
        assert stats["entries_by_type"]["book"] == 2
        assert "entries_by_year" in stats
        assert stats["collections"]["total"] == 1
        assert stats["collections"]["smart"] == 0


class TestRepositoryErrors:
    """Test error handling in repository."""

    def test_backend_read_error(self, mock_backend):
        """Repository handles backend read errors gracefully."""
        mock_backend.read = Mock(side_effect=Exception("Read failed"))

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        assert repo.find("any_key") is None

    def test_backend_write_error(self, mock_backend, sample_entry):
        """Repository propagates backend write errors."""
        mock_backend.write = Mock(side_effect=Exception("Write failed"))

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        with pytest.raises(Exception, match="Write failed"):
            repo.save(sample_entry)

    def test_corrupted_data_handling(self, mock_backend):
        """Repository handles corrupted data gracefully."""
        mock_backend.data["corrupted"] = {"invalid": "data", "no": "required fields"}

        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(mock_backend)

        assert repo.find("corrupted") is None
        mock_backend.data["valid"] = Entry(
            key="valid", type=EntryType.MISC, title="Valid"
        ).to_dict()

        all_entries = repo.find_all()
        assert len(all_entries) == 1
        assert all_entries[0].key == "valid"
