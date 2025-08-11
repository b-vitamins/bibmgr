"""Tests for operation policies (Conflict, Merge, Naming).

This module tests business policies that guide operation behavior including
conflict resolution strategies, merge rules, and key naming conventions.
"""

from datetime import datetime, timedelta

from bibmgr.core.models import Entry

from ..operations.conftest import create_entry_with_data


class TestConflictPolicy:
    """Test conflict resolution policies."""

    def test_default_conflict_resolution(self):
        """Test default conflict resolution strategy."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )

        policy = ConflictPolicy(default_resolution=ConflictResolution.SKIP)

        new_entry = create_entry_with_data(key="test", title="New")
        existing_entry = create_entry_with_data(key="test", title="Existing")

        decision = policy.resolve(new_entry, existing_entry)

        assert decision.action == "skip"
        assert decision.new_key is None

    def test_conflict_resolution_rename(self, entry_repository):
        """Test rename conflict resolution."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )

        policy = ConflictPolicy()

        new_entry = create_entry_with_data(key="smith2024", title="New Paper")
        existing_entry = create_entry_with_data(key="smith2024", title="Existing Paper")

        # Add existing to repository for unique key generation
        entry_repository.save(existing_entry)

        decision = policy.resolve(
            new_entry,
            existing_entry,
            ConflictResolution.RENAME,
            {"repository": entry_repository},
        )

        assert decision.action == "rename"
        assert decision.new_key is not None
        assert decision.new_key != "smith2024"
        assert decision.new_key.startswith("smith2024")

    def test_conflict_resolution_replace(self):
        """Test replace conflict resolution."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )

        policy = ConflictPolicy()

        new_entry = create_entry_with_data(key="test", title="New")
        existing_entry = create_entry_with_data(key="test", title="Old")

        decision = policy.resolve(
            new_entry,
            existing_entry,
            ConflictResolution.REPLACE,
        )

        assert decision.action == "replace"

    def test_conflict_resolution_merge(self):
        """Test merge conflict resolution."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )

        policy = ConflictPolicy()

        new_entry = create_entry_with_data(key="test", doi="10.1234/test")
        existing_entry = create_entry_with_data(key="test", doi="10.1234/test")

        decision = policy.resolve(
            new_entry,
            existing_entry,
            ConflictResolution.MERGE,
        )

        assert decision.action == "merge"

    def test_conflict_resolution_fail(self):
        """Test fail conflict resolution."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )

        policy = ConflictPolicy()

        new_entry = create_entry_with_data(key="test")
        existing_entry = create_entry_with_data(key="test")

        decision = policy.resolve(
            new_entry,
            existing_entry,
            ConflictResolution.FAIL,
        )

        assert decision.action == "fail"
        assert decision.reason == "Conflict not allowed"

    def test_conflict_rules_more_fields(self):
        """Test rule that prefers entry with more fields."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )

        policy = ConflictPolicy()

        # New entry has more fields
        new_entry = create_entry_with_data(
            key="test",
            title="Complete Entry",
            author="Author, A.",
            journal="Journal",
            year=2024,
            volume="1",
            pages="1--10",
        )
        existing_entry = create_entry_with_data(
            key="test",
            title="Minimal Entry",
            year=2024,
        )

        decision = policy.resolve(
            new_entry,
            existing_entry,
            ConflictResolution.ASK,  # Rules apply in ASK mode
        )

        assert decision.action == "replace"
        assert decision.reason is not None and "more data" in decision.reason

    def test_conflict_rules_same_doi(self):
        """Test rule that merges entries with same DOI."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )

        policy = ConflictPolicy()

        new_entry = create_entry_with_data(
            key="new",
            title="New Version",
            doi="10.1234/same",
        )
        existing_entry = create_entry_with_data(
            key="existing",
            title="Old Version",
            doi="10.1234/same",
        )

        decision = policy.resolve(
            new_entry,
            existing_entry,
            ConflictResolution.ASK,
        )

        assert decision.action == "merge"
        assert decision.reason is not None and "Same DOI" in decision.reason

    def test_conflict_rules_recent_entry(self):
        """Test rule that skips if existing entry is recent."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )

        policy = ConflictPolicy()

        new_entry = create_entry_with_data(key="test")

        # Create existing entry with recent added date
        existing_data = {
            "key": "test",
            "type": "article",
            "title": "Recent Entry",
            "year": 2024,
            "added": datetime.now() - timedelta(hours=12),  # Added 12 hours ago
        }
        existing_entry = Entry.from_dict(existing_data)

        decision = policy.resolve(
            new_entry,
            existing_entry,
            ConflictResolution.ASK,
        )

        assert decision.action == "skip"
        assert decision.reason is not None and "recent" in decision.reason

    def test_custom_conflict_resolver(self):
        """Test custom conflict resolver."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )

        # Custom resolver that always merges
        class AlwaysMergeResolver:
            def resolve(self, new_entry, existing_entry, context):
                from bibmgr.operations.policies.conflict import ConflictDecision

                return ConflictDecision(
                    action="merge", new_key=None, reason="Custom merge"
                )

        policy = ConflictPolicy(
            default_resolution=ConflictResolution.SKIP,
            custom_resolver=AlwaysMergeResolver(),
        )

        new_entry = create_entry_with_data(key="test")
        existing_entry = create_entry_with_data(key="test")

        decision = policy.resolve(new_entry, existing_entry)

        assert decision.action == "merge"
        assert decision.reason == "Custom merge"

    def test_generate_unique_key_simple(self):
        """Test simple unique key generation without repository."""
        from bibmgr.operations.policies.conflict import ConflictPolicy

        policy = ConflictPolicy()

        new_key = policy._generate_unique_key("test", None)

        assert new_key != "test"
        assert new_key.startswith("test_")

    def test_generate_unique_key_with_repository(self, entry_repository):
        """Test unique key generation with repository."""
        from bibmgr.operations.policies.conflict import ConflictPolicy

        policy = ConflictPolicy()

        # Add some existing entries
        for suffix in ["", "_1", "_2", "a", "b"]:
            entry = create_entry_with_data(key=f"test{suffix}")
            entry_repository.save(entry)

        new_key = policy._generate_unique_key("test", entry_repository)

        assert new_key not in ["test", "test_1", "test_2", "testa", "testb"]
        assert entry_repository.find(new_key) is None


class TestMergePolicy:
    """Test entry merge policies."""

    def test_merge_basic_two_entries(self):
        """Test basic merge of two entries."""
        from bibmgr.operations.policies.merge import MergePolicy

        policy = MergePolicy()

        entry1 = create_entry_with_data(
            key="v1",
            author="Smith, J.",
            title="Paper",
            year=2020,
        )
        entry2 = create_entry_with_data(
            key="v2",
            author="Smith, John",
            title="Complete Paper Title",
            journal="Nature",
            year=2020,
        )

        merged = policy.merge_entries([entry1, entry2])

        assert merged.author == "Smith, John"  # More complete
        assert merged.title == "Complete Paper Title"  # More complete
        assert merged.journal == "Nature"  # Additional field

    def test_merge_select_target_key(self):
        """Test target key selection based on completeness."""
        from bibmgr.operations.policies.merge import MergePolicy

        policy = MergePolicy()

        minimal = create_entry_with_data(key="minimal", title="Title", year=2020)
        complete = create_entry_with_data(
            key="complete",
            author="Author",
            title="Title",
            journal="Journal",
            year=2020,
            volume="1",
        )

        target_key = policy.select_target_key([minimal, complete])

        assert target_key == "complete"  # Has more fields

    def test_merge_with_explicit_target(self):
        """Test merge with explicitly specified target key."""
        from bibmgr.operations.policies.merge import MergePolicy

        policy = MergePolicy()

        entry1 = create_entry_with_data(key="source1", title="Title 1")
        entry2 = create_entry_with_data(key="source2", title="Title 2")

        merged = policy.merge_entries([entry1, entry2], target_key="custom_key")

        assert merged.key == "custom_key"

    def test_merge_strategy_prefer_first(self):
        """Test PREFER_FIRST merge strategy."""
        from bibmgr.operations.policies.merge import MergePolicy, MergeStrategy

        policy = MergePolicy()

        entries = [
            create_entry_with_data(key="e1", title="First Title", note="First"),
            create_entry_with_data(key="e2", title="Second Title", note="Second"),
            create_entry_with_data(key="e3", title="Third Title", note="Third"),
        ]

        merged = policy.merge_entries(entries, strategy=MergeStrategy.PREFER_FIRST)

        assert merged.title == "First Title"
        assert merged.note == "First"

    def test_merge_strategy_prefer_newest(self):
        """Test PREFER_NEWEST merge strategy."""
        from bibmgr.operations.policies.merge import MergePolicy, MergeStrategy

        policy = MergePolicy()

        # Create entries with different added dates
        old_data = {
            "key": "old",
            "type": "article",
            "title": "Old Title",
            "year": 2020,
            "added": datetime.now() - timedelta(days=30),
        }
        new_data = {
            "key": "new",
            "type": "article",
            "title": "New Title",
            "year": 2020,
            "added": datetime.now() - timedelta(days=1),
        }

        entries = [
            Entry.from_dict(old_data),
            Entry.from_dict(new_data),
        ]

        merged = policy.merge_entries(entries, strategy=MergeStrategy.PREFER_NEWEST)

        assert merged.title == "New Title"  # From newer entry

    def test_merge_strategy_prefer_complete(self):
        """Test PREFER_COMPLETE merge strategy."""
        from bibmgr.operations.policies.merge import MergePolicy, MergeStrategy

        policy = MergePolicy()

        entries = [
            create_entry_with_data(key="e1", title="Short", abstract=""),
            create_entry_with_data(
                key="e2",
                title="Longer Title",
                abstract="This is a complete abstract with details",
            ),
            create_entry_with_data(key="e3", title="Mid", abstract="Brief"),
        ]

        merged = policy.merge_entries(entries, strategy=MergeStrategy.PREFER_COMPLETE)

        assert merged.title == "Longer Title"  # Longest string
        assert (
            merged.abstract is not None and "complete abstract" in merged.abstract
        )  # Most complete

    def test_merge_strategy_union(self):
        """Test UNION merge strategy for lists."""
        from bibmgr.operations.policies.merge import MergePolicy, MergeStrategy

        policy = MergePolicy()

        entries = [
            create_entry_with_data(key="e1", keywords=["ML", "AI"]),
            create_entry_with_data(key="e2", keywords=["AI", "Deep Learning"]),
            create_entry_with_data(key="e3", keywords=["ML", "Neural Networks"]),
        ]

        merged = policy.merge_entries(entries, strategy=MergeStrategy.UNION)

        # Should have all unique keywords
        assert merged.keywords is not None
        assert set(merged.keywords) == {"ML", "AI", "Deep Learning", "Neural Networks"}

    def test_merge_strategy_intersection(self):
        """Test INTERSECTION merge strategy."""
        from bibmgr.operations.policies.merge import MergePolicy, MergeStrategy

        policy = MergePolicy()

        entries = [
            create_entry_with_data(key="e1", keywords=["ML", "AI", "Common"]),
            create_entry_with_data(
                key="e2", keywords=["AI", "Deep Learning", "Common"]
            ),
            create_entry_with_data(key="e3", keywords=["Neural Networks", "Common"]),
        ]

        merged = policy.merge_entries(entries, strategy=MergeStrategy.INTERSECTION)

        # Should have only common keywords
        assert merged.keywords == ("Common",)

    def test_merge_smart_authors(self):
        """Test smart merging of author fields."""
        from bibmgr.operations.policies.merge import MergePolicy, MergeStrategy

        policy = MergePolicy()

        entries = [
            create_entry_with_data(key="e1", author="Smith, J."),
            create_entry_with_data(key="e2", author="Smith, John and Doe, Jane"),
            create_entry_with_data(key="e3", author="Smith, J. and Brown, Bob"),
        ]

        merged = policy.merge_entries(entries, strategy=MergeStrategy.SMART)

        # Should combine all unique authors
        assert merged.author is not None
        assert "John" in merged.author or "J." in merged.author
        assert "Doe" in merged.author
        assert "Brown" in merged.author

    def test_merge_smart_pages(self):
        """Test smart merging of page ranges."""
        from bibmgr.operations.policies.merge import MergePolicy, MergeStrategy

        policy = MergePolicy()

        entries = [
            create_entry_with_data(key="e1", pages="100--110"),
            create_entry_with_data(key="e2", pages="105"),
            create_entry_with_data(key="e3", pages="100-115"),  # Single dash
        ]

        merged = policy.merge_entries(entries, strategy=MergeStrategy.SMART)

        # Should create full range
        assert merged.pages == "100--115"

    def test_merge_field_rules(self):
        """Test field-specific merge rules."""
        from bibmgr.operations.policies.merge import MergePolicy

        policy = MergePolicy()

        # Create entries with different timestamps
        old_data = {
            "key": "old",
            "type": "article",
            "title": "Title",
            "year": 2020,
            "added": datetime(2020, 1, 1),
            "modified": datetime(2020, 1, 1),
        }
        new_data = {
            "key": "new",
            "type": "article",
            "title": "Title",
            "year": 2020,
            "added": datetime(2024, 1, 1),
            "modified": datetime(2024, 6, 1),
        }

        entries = [Entry.from_dict(old_data), Entry.from_dict(new_data)]

        merged = policy.merge_entries(entries)

        # Should keep oldest added, newest modified
        assert merged.added.year == 2020  # Oldest
        assert merged.modified.year == 2024  # Newest

    def test_merge_fix_validation_errors(self):
        """Test fixing validation errors after merge."""
        from bibmgr.core.validators import ValidationError
        from bibmgr.operations.policies.merge import MergePolicy

        policy = MergePolicy()

        # Entry missing author but has editor
        entry = create_entry_with_data(
            key="test",
            type="article",
            editor="Editor, E.",
            title="Title",
            journal="Journal",
            year=2024,
        )

        errors = [
            ValidationError(
                field="author",
                message="Required field missing",
                severity="error",
            )
        ]

        fixed = policy.fix_validation_errors(entry, errors)

        # Should use editor as author
        assert fixed.author == "Editor, E."

    def test_merge_custom_function(self):
        """Test merge with custom merge function."""
        from bibmgr.operations.policies.merge import (
            FieldMergeRule,
            MergePolicy,
            MergeStrategy,
        )

        # Custom merger that concatenates with semicolon
        def concat_with_semicolon(values):
            return "; ".join(v for v in values if v)

        policy = MergePolicy()
        policy.field_rules["note"] = FieldMergeRule(
            "note",
            MergeStrategy.CUSTOM,
            custom_merger=concat_with_semicolon,
        )

        entries = [
            create_entry_with_data(key="e1", note="Note 1"),
            create_entry_with_data(key="e2", note="Note 2"),
            create_entry_with_data(key="e3", note="Note 3"),
        ]

        merged = policy.merge_entries(entries)

        assert merged.note == "Note 1; Note 2; Note 3"


class TestKeyNamingPolicy:
    """Test key naming policies."""

    def test_generate_author_year_key(self):
        """Test author_year key generation."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(style="author_year")

        entry = create_entry_with_data(
            author="Smith, John and Doe, Jane",
            title="Test Paper",
            year=2024,
        )

        key = policy.generate_key(entry)

        assert key == "smith_2024"

    def test_generate_author_year_key_no_comma(self):
        """Test author_year with name not in Last, First format."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(style="author_year")

        entry = create_entry_with_data(
            author="John Smith",
            year=2024,
        )

        key = policy.generate_key(entry)

        assert key == "smith_2024"

    def test_generate_author_title_year_key(self):
        """Test author_title_year key generation."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(style="author_title_year")

        entry = create_entry_with_data(
            author="Doe, Jane",
            title="The Machine Learning Revolution in Science",
            year=2024,
        )

        key = policy.generate_key(entry)

        # Should skip "The" and use "machine"
        assert "doe" in key
        assert "machine" in key
        assert "2024" in key

    def test_generate_title_year_key(self):
        """Test title_year key generation."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(style="title_year")

        entry = create_entry_with_data(
            title="A Study of Neural Networks and Deep Learning",
            year=2024,
        )

        key = policy.generate_key(entry)

        # Should use significant words
        assert "study" in key or "neural" in key
        assert "2024" in key

    def test_generate_numeric_key(self):
        """Test numeric key generation."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(style="numeric")

        entry = create_entry_with_data(
            type="article",
            title="Any Title",
        )

        key = policy.generate_key(entry)

        assert key.startswith("article_")
        # Should have timestamp
        assert len(key) > len("article_")

    def test_generate_key_missing_fields(self):
        """Test key generation with missing fields."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(style="author_year")

        # Missing both author and year
        entry = create_entry_with_data(
            type="misc",
            title="No Author or Year",
        )

        key = policy.generate_key(entry)

        # Should fallback to type and timestamp
        assert key.startswith("misc_")

    def test_sanitize_key(self):
        """Test key sanitization."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(max_length=20)

        # Key with invalid characters
        dirty_key = "test@key#with$special%chars^and&very*long(name)here!"

        clean_key = policy.sanitize_key(dirty_key)

        assert len(clean_key) <= 20
        assert "@" not in clean_key
        assert "#" not in clean_key
        assert all(c.isalnum() or c in "-_" for c in clean_key)

    def test_validate_key(self):
        """Test key validation."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(max_length=50, allowed_chars=r"[a-zA-Z0-9_-]")

        # Valid key
        errors = policy.validate_key("valid_key-2024")
        assert len(errors) == 0

        # Empty key
        errors = policy.validate_key("")
        assert any("empty" in e for e in errors)

        # Too long
        errors = policy.validate_key("a" * 100)
        assert any("too long" in e for e in errors)

        # Invalid characters
        errors = policy.validate_key("invalid@key!")
        assert any("invalid characters" in e for e in errors)

    def test_generate_alternative_simple(self):
        """Test alternative key generation without repository."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy()

        alt = policy.generate_alternative("base_key", None)

        assert alt != "base_key"
        assert alt == "base_key_alt"

    def test_generate_alternative_with_repository(self, entry_repository):
        """Test alternative key generation with repository."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy()

        # Add base key
        entry_repository.save(create_entry_with_data(key="smith2024"))

        # First alternative
        alt1 = policy.generate_alternative("smith2024", entry_repository)
        assert alt1 == "smith2024a"

        # Add it and get next
        entry_repository.save(create_entry_with_data(key=alt1))
        alt2 = policy.generate_alternative("smith2024", entry_repository)
        assert alt2 == "smith2024b"

    def test_special_characters_in_author(self):
        """Test handling special characters in author names."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(style="author_year")

        entry = create_entry_with_data(
            author="Müller, Hans-Peter",
            year=2024,
        )

        key = policy.generate_key(entry)

        # Should remove special characters
        assert "ü" not in key
        assert "-" not in key or key.count("-") <= 1  # Might be converted to underscore

    def test_handle_latex_in_title(self):
        """Test handling LaTeX in titles."""
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        policy = KeyNamingPolicy(style="title_year")

        entry = create_entry_with_data(
            title=r"The $\alpha$-Algorithm for \textit{Machine Learning}",
            year=2024,
        )

        key = policy.generate_key(entry)

        # Should remove LaTeX commands
        assert "$" not in key
        assert "\\" not in key
        assert "alpha" in key or "algorithm" in key


class TestPolicyIntegration:
    """Test integration between different policies."""

    def test_conflict_leads_to_merge(self):
        """Test conflict resolution that triggers merge."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )
        from bibmgr.operations.policies.merge import MergePolicy

        conflict_policy = ConflictPolicy()
        merge_policy = MergePolicy()

        # Entries with same DOI
        new_entry = create_entry_with_data(
            key="new",
            author="Author, A.",
            title="New Version",
            doi="10.1234/same",
        )
        existing_entry = create_entry_with_data(
            key="existing",
            author="Author, Alice",
            title="Existing Version",
            doi="10.1234/same",
            pages="1--10",
        )

        # Resolve conflict
        decision = conflict_policy.resolve(
            new_entry,
            existing_entry,
            ConflictResolution.ASK,
        )

        assert decision.action == "merge"

        # Perform merge
        merged = merge_policy.merge_entries(
            [existing_entry, new_entry],
            target_key=existing_entry.key,
        )

        assert merged.key == "existing"
        assert (
            merged.author is not None and "Alice" in merged.author
        )  # More complete name
        assert merged.pages == "1--10"  # Preserved from existing

    def test_rename_with_naming_policy(self, entry_repository):
        """Test conflict rename uses naming policy."""
        from bibmgr.operations.policies.conflict import (
            ConflictPolicy,
            ConflictResolution,
        )
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        naming_policy = KeyNamingPolicy(style="author_year")
        conflict_policy = ConflictPolicy()

        # Existing entry
        existing = create_entry_with_data(
            key="smith2024",
            author="Smith, John",
            year=2024,
        )
        entry_repository.save(existing)

        # New entry with same generated key
        new_entry = create_entry_with_data(
            key="different_key",
            author="Smith, Jane",
            year=2024,
        )

        # Generate key for new entry
        generated_key = naming_policy.generate_key(new_entry)
        assert generated_key == "smith_2024"

        # Check for conflict
        if entry_repository.exists(generated_key):
            decision = conflict_policy.resolve(
                new_entry,
                existing,
                ConflictResolution.RENAME,
                {"repository": entry_repository},
            )

            assert decision.action == "rename"
            assert decision.new_key != generated_key

            # Alternative should be valid
            assert decision.new_key is not None
            errors = naming_policy.validate_key(decision.new_key)
            assert len(errors) == 0
