"""Comprehensive tests for search history and saved searches.

These tests are implementation-agnostic and focus on the expected behavior
of search history tracking, saved searches, and analytics.
"""

import pytest
import tempfile
import json
from datetime import datetime
from pathlib import Path

# Tests are now ready to run


class TestSearchHistoryEntry:
    """Test search history entry model."""

    def test_entry_creation(self):
        """Should create history entry with all fields."""
        from bibmgr.search.history import SearchHistoryEntry

        now = datetime.now()
        entry = SearchHistoryEntry(
            query="machine learning",
            timestamp=now,
            result_count=42,
            search_time_ms=15.3,
        )

        assert entry.query == "machine learning"
        assert entry.timestamp == now
        assert entry.result_count == 42
        assert entry.search_time_ms == 15.3

    def test_entry_serialization(self):
        """Should serialize to dictionary."""
        from bibmgr.search.history import SearchHistoryEntry

        now = datetime.now()
        entry = SearchHistoryEntry(
            query="test", timestamp=now, result_count=10, search_time_ms=5.0
        )

        data = entry.to_dict()

        assert data["query"] == "test"
        assert data["timestamp"] == now.isoformat()
        assert data["result_count"] == 10
        assert data["search_time_ms"] == 5.0

    def test_entry_deserialization(self):
        """Should deserialize from dictionary."""
        from bibmgr.search.history import SearchHistoryEntry

        now = datetime.now()
        data = {
            "query": "test",
            "timestamp": now.isoformat(),
            "result_count": 10,
            "search_time_ms": 5.0,
        }

        entry = SearchHistoryEntry.from_dict(data)

        assert entry.query == "test"
        assert entry.timestamp.isoformat() == now.isoformat()
        assert entry.result_count == 10
        assert entry.search_time_ms == 5.0


class TestSavedSearch:
    """Test saved search model."""

    def test_saved_search_creation(self):
        """Should create saved search with minimal fields."""
        from bibmgr.search.history import SavedSearch

        saved = SavedSearch(name="ml_papers", query="machine learning year:2024")

        assert saved.name == "ml_papers"
        assert saved.query == "machine learning year:2024"
        assert saved.description is None
        assert isinstance(saved.created_at, datetime)
        assert saved.tags == []

    def test_saved_search_with_metadata(self):
        """Should create saved search with full metadata."""
        from bibmgr.search.history import SavedSearch

        now = datetime.now()
        saved = SavedSearch(
            name="recent_transformers",
            query="transformer attention year:2023..2024",
            description="Recent transformer papers",
            created_at=now,
            tags=["ml", "nlp", "transformers"],
        )

        assert saved.name == "recent_transformers"
        assert saved.description == "Recent transformer papers"
        assert saved.created_at == now
        assert len(saved.tags) == 3
        assert "ml" in saved.tags

    def test_saved_search_serialization(self):
        """Should serialize to dictionary."""
        from bibmgr.search.history import SavedSearch

        saved = SavedSearch(
            name="test",
            query="test query",
            description="Test description",
            tags=["tag1", "tag2"],
        )

        data = saved.to_dict()

        assert data["name"] == "test"
        assert data["query"] == "test query"
        assert data["description"] == "Test description"
        assert data["tags"] == ["tag1", "tag2"]
        assert "created_at" in data

    def test_saved_search_deserialization(self):
        """Should deserialize from dictionary."""
        from bibmgr.search.history import SavedSearch

        now = datetime.now()
        data = {
            "name": "test",
            "query": "test query",
            "description": "Test",
            "created_at": now.isoformat(),
            "tags": ["tag1"],
        }

        saved = SavedSearch.from_dict(data)

        assert saved.name == "test"
        assert saved.query == "test query"
        assert saved.description == "Test"
        assert saved.tags == ["tag1"]


class TestSearchHistoryInitialization:
    """Test search history manager initialization."""

    def test_default_initialization(self):
        """Should initialize with default directory."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir) / "history")

            assert history.data_dir.exists()
            assert history.data_dir.name == "history"
            assert history.history == []
            assert history.saved_searches == {}

    def test_custom_directory(self):
        """Should use custom data directory."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "custom"
            history = SearchHistory(data_dir=data_dir)

            assert history.data_dir == data_dir
            assert data_dir.exists()

    def test_load_existing_history(self):
        """Should load existing history from disk."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            history_file = data_dir / "history.json"

            # Create existing history
            history_data = [
                {
                    "query": "existing",
                    "timestamp": datetime.now().isoformat(),
                    "result_count": 5,
                    "search_time_ms": 10.0,
                }
            ]
            history_file.write_text(json.dumps(history_data))

            # Load it
            history = SearchHistory(data_dir=data_dir)

            assert len(history.history) == 1
            assert history.history[0].query == "existing"

    def test_load_existing_saved_searches(self):
        """Should load existing saved searches from disk."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            saved_file = data_dir / "saved_searches.json"

            # Create existing saved searches
            saved_data = {
                "test_search": {
                    "name": "test_search",
                    "query": "test",
                    "description": None,
                    "created_at": datetime.now().isoformat(),
                    "tags": [],
                }
            }
            saved_file.write_text(json.dumps(saved_data))

            # Load it
            history = SearchHistory(data_dir=data_dir)

            assert len(history.saved_searches) == 1
            assert "test_search" in history.saved_searches

    def test_handle_corrupt_files(self):
        """Should handle corrupt data files gracefully."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)

            # Create corrupt files
            (data_dir / "history.json").write_text("not valid json{")
            (data_dir / "saved_searches.json").write_text("corrupt]")

            # Should not crash
            history = SearchHistory(data_dir=data_dir)

            assert history.history == []
            assert history.saved_searches == {}


class TestAddingSearchHistory:
    """Test adding searches to history."""

    def test_add_search(self):
        """Should add search to history."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            history.add_search(query="test query", result_count=10, search_time_ms=15.5)

            assert len(history.history) == 1
            assert history.history[0].query == "test query"
            assert history.history[0].result_count == 10
            assert history.history[0].search_time_ms == 15.5

    def test_add_multiple_searches(self):
        """Should add multiple searches."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            for i in range(5):
                history.add_search(
                    query=f"query {i}", result_count=i * 10, search_time_ms=i * 5.0
                )

            assert len(history.history) == 5
            assert history.history[-1].query == "query 4"

    def test_persist_history(self):
        """Should persist history to disk."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)

            # Add search
            history1 = SearchHistory(data_dir=data_dir)
            history1.add_search("test", 10, 5.0)

            # Load in new instance
            history2 = SearchHistory(data_dir=data_dir)

            assert len(history2.history) == 1
            assert history2.history[0].query == "test"

    def test_history_size_limit(self):
        """Should limit history to last 1000 entries."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            # Add more than 1000 entries
            for i in range(1100):
                history.add_search(f"query{i}", 1, 1.0)

            # Force save
            history._save_history()

            # Reload
            history2 = SearchHistory(data_dir=Path(tmpdir))

            # Should keep only last 1000
            assert len(history2.history) <= 1000


class TestSavingSearches:
    """Test saving and managing saved searches."""

    def test_save_search(self):
        """Should save a search."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            history.save_search(
                name="ml_papers",
                query="machine learning",
                description="ML research papers",
                tags=["ml", "ai"],
            )

            assert "ml_papers" in history.saved_searches
            saved = history.saved_searches["ml_papers"]
            assert saved.query == "machine learning"
            assert saved.description == "ML research papers"
            assert saved.tags == ["ml", "ai"]

    def test_overwrite_saved_search(self):
        """Should overwrite existing saved search."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            # Save initial
            history.save_search("test", "query1")

            # Overwrite
            history.save_search("test", "query2", description="Updated")

            assert history.saved_searches["test"].query == "query2"
            assert history.saved_searches["test"].description == "Updated"

    def test_get_saved_search(self):
        """Should retrieve saved search by name."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            history.save_search("test", "test query")

            saved = history.get_saved("test")
            assert saved is not None
            assert saved.query == "test query"

            # Non-existent
            assert history.get_saved("nonexistent") is None

    def test_list_saved_searches(self):
        """Should list all saved searches."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            # Save multiple searches
            for i in range(3):
                history.save_search(
                    name=f"search{i}", query=f"query{i}", tags=[f"tag{i}"]
                )

            searches = history.list_saved()

            assert len(searches) == 3
            # Should be sorted by creation date (newest first)
            assert searches[0].name == "search2"

    def test_list_saved_by_tag(self):
        """Should filter saved searches by tag."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            history.save_search("ml1", "query1", tags=["ml", "ai"])
            history.save_search("ml2", "query2", tags=["ml", "deep"])
            history.save_search("db1", "query3", tags=["database"])

            ml_searches = history.list_saved(tag="ml")

            assert len(ml_searches) == 2
            assert all("ml" in s.tags for s in ml_searches)

    def test_persist_saved_searches(self):
        """Should persist saved searches to disk."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)

            # Save search
            history1 = SearchHistory(data_dir=data_dir)
            history1.save_search("test", "test query", tags=["tag1"])

            # Load in new instance
            history2 = SearchHistory(data_dir=data_dir)

            assert "test" in history2.saved_searches
            assert history2.saved_searches["test"].query == "test query"


class TestQueryAnalytics:
    """Test query analytics and statistics."""

    def test_popular_queries(self):
        """Should track most popular queries."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            # Add searches with different frequencies
            for _ in range(5):
                history.add_search("popular", 10, 5.0)
            for _ in range(3):
                history.add_search("medium", 5, 5.0)
            history.add_search("rare", 1, 5.0)

            popular = history.get_popular_queries(limit=2)

            assert len(popular) == 2
            assert popular[0] == ("popular", 5)
            assert popular[1] == ("medium", 3)

    def test_recent_queries(self):
        """Should get recent queries."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            # Add searches
            for i in range(5):
                history.add_search(f"query{i}", i, 5.0)

            recent = history.get_recent_queries(limit=3)

            assert len(recent) == 3
            # Should be in reverse order (newest first)
            assert recent[0].query == "query4"
            assert recent[1].query == "query3"
            assert recent[2].query == "query2"

    def test_empty_statistics(self):
        """Should handle empty history statistics."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            stats = history.get_statistics()

            assert stats["total_searches"] == 0
            assert stats["unique_queries"] == 0
            assert stats["avg_search_time_ms"] == 0.0
            assert stats["avg_result_count"] == 0.0

    def test_statistics_with_data(self):
        """Should calculate statistics from history."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            # Add varied searches
            history.add_search("query1", 10, 5.0)
            history.add_search("query2", 20, 10.0)
            history.add_search("query1", 10, 6.0)  # Duplicate
            history.save_search("saved1", "test")
            history.save_search("saved2", "test2")

            stats = history.get_statistics()

            assert stats["total_searches"] == 3
            assert stats["unique_queries"] == 2
            assert stats["avg_search_time_ms"] == 7.0  # (5+10+6)/3
            assert stats["avg_result_count"] == pytest.approx(13.33, rel=0.01)
            assert stats["saved_searches"] == 2


class TestHistoryManagement:
    """Test history management operations."""

    def test_clear_history(self):
        """Should clear all search history."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            # Add some history
            for i in range(5):
                history.add_search(f"query{i}", i, 5.0)

            assert len(history.history) == 5

            # Clear
            history.clear_history()

            assert len(history.history) == 0

            # Saved searches should remain
            history.save_search("test", "query")
            history.clear_history()
            assert len(history.saved_searches) == 1

    def test_persistence_after_clear(self):
        """Should persist cleared state."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)

            # Add and clear
            history1 = SearchHistory(data_dir=data_dir)
            history1.add_search("test", 10, 5.0)
            history1.clear_history()

            # Load in new instance
            history2 = SearchHistory(data_dir=data_dir)

            assert len(history2.history) == 0


class TestIntegration:
    """Test complete history workflows."""

    def test_search_session_workflow(self):
        """Test typical search session with history."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            # User does exploratory searches
            history.add_search("machine learning", 150, 25.0)
            history.add_search("deep learning", 89, 18.0)
            history.add_search("neural networks", 203, 30.0)

            # Refines search - searching neural networks again
            history.add_search("neural networks", 45, 12.0)

            # Saves refined search
            history.save_search(
                name="recent_nn",
                query="neural networks",
                description="Recent neural network papers",
                tags=["ml", "recent"],
            )

            # Check analytics
            popular = history.get_popular_queries(limit=1)
            assert popular[0][0] == "neural networks"  # Most searched

            recent = history.get_recent_queries(limit=1)
            assert recent[0].query == "neural networks"

            saved = history.get_saved("recent_nn")
            assert saved is not None
            assert saved.query == "neural networks"

    def test_persistent_workflow(self):
        """Test workflow across multiple sessions."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)

            # Session 1: Initial searches
            session1 = SearchHistory(data_dir=data_dir)
            session1.add_search("transformers", 67, 15.0)
            session1.save_search("transformers", "transformers", tags=["nlp"])

            # Session 2: Continue searching
            session2 = SearchHistory(data_dir=data_dir)
            assert len(session2.history) == 1
            assert "transformers" in session2.saved_searches

            session2.add_search("bert", 34, 10.0)
            session2.add_search("gpt", 28, 9.0)

            # Session 3: Review statistics
            session3 = SearchHistory(data_dir=data_dir)
            stats = session3.get_statistics()

            assert stats["total_searches"] == 3
            assert stats["unique_queries"] == 3
            assert stats["saved_searches"] == 1

    def test_search_refinement_tracking(self):
        """Test tracking search refinement patterns."""
        from bibmgr.search.history import SearchHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history = SearchHistory(data_dir=Path(tmpdir))

            # User refines search progressively
            searches = [
                ("learning", 500, 50.0),
                ("machine learning", 150, 25.0),
                ("machine learning 2024", 45, 15.0),
                ("machine learning 2024 transformer", 12, 8.0),
            ]

            for query, count, time_ms in searches:
                history.add_search(query, count, time_ms)

            # Can analyze refinement pattern
            recent = history.get_recent_queries(limit=4)

            # Results get more specific
            assert recent[0].result_count < recent[3].result_count

            # Search times generally decrease (cached results)
            assert recent[0].search_time_ms < recent[3].search_time_ms
