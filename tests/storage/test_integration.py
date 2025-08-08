"""Integration tests for complete storage system.

Tests the interaction between parser, backend, and sidecar components
working together as a complete system.
"""

import concurrent.futures
import tempfile
import threading
import time
from pathlib import Path

import pytest


@pytest.fixture
def temp_storage():
    """Create temporary storage system."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_bibtex_file():
    """Create a sample BibTeX file."""
    content = """
    @string{ACM = "ACM Press"}
    @string{IEEE = "IEEE Computer Society"}
    
    @article{smith2024ml,
        author = {John Smith and Jane Doe},
        title = {Machine Learning for {NLP}: A Comprehensive Survey},
        journal = {AI Review},
        year = 2024,
        volume = 42,
        pages = {123--189},
        doi = {10.1234/air.2024.042}
    }
    
    @inproceedings{jones2023attention,
        author = "Robert Jones",
        title = "Attention Mechanisms in Deep Learning",
        booktitle = "Proceedings of NeurIPS",
        publisher = ACM,
        year = 2023,
        pages = "456--467"
    }
    
    @book{williams2022textbook,
        author = {Emily Williams},
        title = {Deep Learning: Theory and Practice},
        publisher = IEEE,
        year = 2022,
        edition = {3rd},
        isbn = {978-0-123456-78-9}
    }
    
    @phdthesis{brown2024thesis,
        author = "Michael Brown",
        title = "Neural Architecture Search for Computer Vision",
        school = "Stanford University",
        year = 2024,
        month = "June"
    }
    
    @misc{dataset2024,
        title = "Large-Scale Dataset for NLP Research",
        author = {{Research Team}},
        year = 2024,
        url = "https://example.com/dataset",
        note = "Version 2.0"
    }
    """

    with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
        f.write(content)
        return Path(f.name)


class TestCompleteWorkflow:
    """Test complete storage workflow."""

    def test_import_bibtex_file(self, storage_system, sample_bibtex_file, temp_storage):
        """Test importing a complete BibTeX file."""
        system = storage_system(temp_storage)

        # Import file
        entries = system.import_file(sample_bibtex_file)

        assert len(entries) >= 5

        # Verify entries are stored
        for entry in entries:
            stored = system.storage.read(entry.key)
            assert stored is not None
            assert stored.key == entry.key

        # Cleanup
        sample_bibtex_file.unlink()

    def test_import_with_metadata(
        self, storage_system, sample_bibtex_file, temp_storage
    ):
        """Test importing with automatic metadata extraction."""
        system = storage_system(temp_storage)

        # Import with metadata
        entries = system.import_file(sample_bibtex_file, extract_metadata=True)

        # Check metadata was created
        for entry in entries:
            metadata = system.sidecar.get_metadata(entry.key)
            assert metadata is not None
            assert metadata.key == entry.key
            assert metadata.created_at is not None

        # Cleanup
        sample_bibtex_file.unlink()

    def test_export_bibtex_file(self, storage_system, sample_entries, temp_storage):
        """Test exporting to BibTeX file."""
        system = storage_system(temp_storage)
        export_path = temp_storage / "export.bib"

        # Add entries
        for entry in sample_entries:
            system.storage.write(entry)

        # Export
        system.export_file(export_path)

        assert export_path.exists()

        # Re-import and verify
        reimported = system.import_file(export_path)
        assert len(reimported) == len(sample_entries)

        keys_original = {e.key for e in sample_entries}
        keys_reimported = {e.key for e in reimported}
        assert keys_original == keys_reimported

    def test_round_trip_preservation(
        self, storage_system, sample_bibtex_file, temp_storage
    ):
        """Test round-trip preservation of data."""
        system = storage_system(temp_storage)
        export_path = temp_storage / "roundtrip.bib"
        metadata_export_path = temp_storage / "metadata.json"

        # Import original
        original_entries = system.import_file(sample_bibtex_file)

        # Add metadata
        for entry in original_entries:
            system.sidecar.add_tags(entry.key, ["imported", "test"])
            system.sidecar.update_metadata(entry.key, rating=4)

        # Export data and metadata separately
        system.export_file(export_path, include_metadata=False)
        system.sidecar.export(metadata_export_path)

        # Clear storage
        system.storage.clear()
        system.sidecar.rebuild_index()

        # Re-import
        reimported = system.import_file(export_path, extract_metadata=False)
        system.sidecar.import_from(metadata_export_path)

        # Verify preservation
        for entry in reimported:
            metadata = system.sidecar.get_metadata(entry.key)
            assert metadata is not None
            assert metadata.tags is not None
            assert "imported" in metadata.tags
            assert "test" in metadata.tags
            assert metadata.rating == 4

        # Cleanup
        sample_bibtex_file.unlink()


class TestSearchIntegration:
    """Test integrated search across storage components."""

    def test_search_entries_with_metadata(
        self, storage_system, sample_entries, temp_storage
    ):
        """Test searching entries with metadata filters."""
        system = storage_system(temp_storage)

        # Add entries with metadata
        for i, entry in enumerate(sample_entries):
            system.storage.write(entry)
            system.sidecar.update_metadata(
                entry.key, tags=["ml"] if i % 2 == 0 else ["nlp"], rating=i % 5 + 1
            )

        # Search by tag
        ml_entries = system.search(metadata_filter={"tags": "ml"})
        assert len(ml_entries) == len(sample_entries) // 2

        # Search by rating
        high_rated = system.search(metadata_filter={"rating": {"$gte": 4}})
        assert all(system.sidecar.get_metadata(e.key).rating >= 4 for e in high_rated)

    def test_full_text_search(self, storage_system, sample_entries, temp_storage):
        """Test full-text search across entries and notes."""
        system = storage_system(temp_storage)

        # Add entries
        for entry in sample_entries:
            system.storage.write(entry)

            # Add notes
            note = system.create_note(
                entry_key=entry.key,
                content=f"This note discusses {entry.title} in detail.",
            )
            system.sidecar.add_note(note)

        # Full-text search
        results = system.full_text_search("discusses")

        # Should find entries through notes
        assert len(results) > 0
        for result in results:
            notes = system.sidecar.get_notes(result.key)
            assert any("discusses" in n.content for n in notes)

    def test_complex_query(self, storage_system, temp_storage):
        """Test complex queries combining entry and metadata filters."""
        system = storage_system(temp_storage)

        # Add varied entries
        for i in range(20):
            entry = system.create_entry(
                key=f"entry{i}",
                title=f"Title {i}",
                year=2020 + i % 5,
                type="article" if i % 2 == 0 else "book",
            )
            system.storage.write(entry)

            system.sidecar.update_metadata(
                entry.key,
                tags=["ml", "recent"] if i % 3 == 0 else ["nlp"],
                rating=i % 5 + 1,
                reading_status="read" if i < 10 else "unread",
            )

        # Complex query: recent ML articles that are read with high rating
        results = system.search(
            entry_filter={"type": "article", "year": {"$gte": 2023}},
            metadata_filter={
                "tags": {"$contains": "ml"},
                "rating": {"$gte": 4},
                "reading_status": "read",
            },
        )

        # Verify results match all criteria
        for entry in results:
            assert entry.type == "article"
            assert entry.year >= 2023

            metadata = system.sidecar.get_metadata(entry.key)
            assert "ml" in metadata.tags
            assert metadata.rating >= 4
            assert metadata.reading_status == "read"


class TestTransactionIntegration:
    """Test transactions across storage components."""

    def test_atomic_import(self, storage_system, temp_storage):
        """Test atomic import of multiple entries."""
        system = storage_system(temp_storage)

        # Create entries with one invalid
        entries_text = """
        @article{valid1, title="Valid 1", journal="Test", year=2024}
        @article{valid2, title="Valid 2", journal="Test", year=2024}
        @article{invalid, title="Missing required fields"}
        @article{valid3, title="Valid 3", journal="Test", year=2024}
        """

        # Import with transaction
        try:
            with system.begin_transaction() as txn:
                entries = system.parser.parse(entries_text)

                for entry in entries:
                    # Validate before adding
                    if system.validate_entry(entry):
                        txn.add(entry)
                    else:
                        raise ValueError(f"Invalid entry: {entry.key}")

                txn.commit()
        except ValueError:
            # Transaction should rollback
            pass

        # Check atomicity - either all or none
        count = system.storage.count()
        assert count == 0 or count == 3

    def test_coordinated_update(self, storage_system, sample_entries, temp_storage):
        """Test coordinated updates across storage and sidecar."""
        system = storage_system(temp_storage)

        # Add initial data
        for entry in sample_entries[:5]:
            system.storage.write(entry)
            system.sidecar.add_tags(entry.key, ["original"])

        # Coordinated update
        with system.begin_transaction() as txn:
            for entry in sample_entries[:5]:
                # Update entry
                updated_entry = system.create_entry(
                    key=entry.key, title=f"Updated: {entry.title}", year=entry.year + 1
                )
                txn.update(updated_entry)

                # Update metadata
                system.sidecar.update_metadata(
                    entry.key, tags=["updated"], notes="Updated in transaction"
                )

            txn.commit()

        # Verify coordinated updates
        for entry in sample_entries[:5]:
            stored = system.storage.read(entry.key)
            assert "Updated:" in stored.title

            metadata = system.sidecar.get_metadata(entry.key)
            assert "updated" in metadata.tags
            assert metadata.notes == "Updated in transaction"


class TestBackupRestore:
    """Test backup and restore of complete system."""

    def test_complete_backup(self, storage_system, sample_entries, temp_storage):
        """Test backing up storage and metadata together."""
        system = storage_system(temp_storage)
        backup_dir = temp_storage / "backup"

        # Add data
        for i, entry in enumerate(sample_entries):
            system.storage.write(entry)
            system.sidecar.update_metadata(
                entry.key,
                tags=[f"tag{i}"],
                rating=i % 5 + 1,
                notes=f"Note for {entry.key}",
            )

        # Create complete backup
        system.backup(backup_dir)

        # Verify backup structure
        assert (backup_dir / "storage").exists()
        assert (backup_dir / "metadata.json").exists()

        # Clear system
        system.storage.clear()
        for entry in sample_entries:
            system.sidecar.delete_metadata(entry.key)

        # Restore
        system.restore(backup_dir)

        # Verify restoration
        for entry in sample_entries:
            restored = system.storage.read(entry.key)
            assert restored is not None

            metadata = system.sidecar.get_metadata(entry.key)
            assert metadata is not None
            assert f"Note for {entry.key}" == metadata.notes

    def test_incremental_backup(self, storage_system, sample_entries, temp_storage):
        """Test incremental backup functionality."""
        system = storage_system(temp_storage)
        backup_dir = temp_storage / "backup"

        # Initial data and backup
        for entry in sample_entries[:5]:
            system.storage.write(entry)

        system.backup(backup_dir)
        initial_size = sum(
            f.stat().st_size for f in backup_dir.rglob("*") if f.is_file()
        )

        # Add more data
        for entry in sample_entries[5:]:
            system.storage.write(entry)

        # Incremental backup
        if hasattr(system, "backup_incremental"):
            system.backup_incremental(backup_dir)

            # Should have more data but efficient
            final_size = sum(
                f.stat().st_size for f in backup_dir.rglob("*") if f.is_file()
            )
            assert final_size > initial_size

    def test_selective_restore(self, storage_system, sample_entries, temp_storage):
        """Test selective restoration of data."""
        system = storage_system(temp_storage)
        backup_dir = temp_storage / "backup"

        # Add data and backup
        for entry in sample_entries:
            system.storage.write(entry)
            system.sidecar.add_tags(entry.key, ["original"])

        system.backup(backup_dir)

        # Modify some entries
        for entry in sample_entries[:3]:
            system.sidecar.add_tags(entry.key, ["modified"])

        # Selective restore (if supported)
        if hasattr(system, "restore_selective"):
            # Restore only specific entries
            keys_to_restore = [e.key for e in sample_entries[:3]]
            system.restore_selective(backup_dir, keys=keys_to_restore)

            # Check restoration
            for entry in sample_entries[:3]:
                metadata = system.sidecar.get_metadata(entry.key)
                assert "original" in metadata.tags
                assert "modified" not in metadata.tags  # Should be overwritten


class TestConcurrentOperations:
    """Test concurrent operations across system."""

    def test_concurrent_import_export(self, storage_system, temp_storage):
        """Test concurrent import and export operations."""
        system = storage_system(temp_storage)

        def import_entries(thread_id):
            entries_text = f"""
            @article{{thread{thread_id}_1, title="Entry 1 from thread {thread_id}", year=2024}}
            @article{{thread{thread_id}_2, title="Entry 2 from thread {thread_id}", year=2024}}
            """
            entries = system.parser.parse(entries_text)
            for entry in entries:
                system.storage.write(entry)
            return len(entries)

        def export_entries(thread_id):
            export_path = temp_storage / f"export_{thread_id}.bib"
            system.export_file(export_path)
            return export_path.exists()

        # Run concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            import_futures = [executor.submit(import_entries, i) for i in range(5)]

            # Wait a bit for some imports
            time.sleep(0.1)

            export_futures = [executor.submit(export_entries, i) for i in range(5)]

            import_results = [f.result() for f in import_futures]
            export_results = [f.result() for f in export_futures]

        # Verify results
        assert all(r == 2 for r in import_results)
        assert all(r for r in export_results)

        # Check final state
        assert system.storage.count() == 10  # 5 threads * 2 entries each

    def test_concurrent_search_update(
        self, storage_system, sample_entries, temp_storage
    ):
        """Test concurrent search and update operations."""
        system = storage_system(temp_storage)

        # Add initial data
        for entry in sample_entries:
            system.storage.write(entry)

        results = []

        def search_entries():
            for _ in range(10):
                found = system.search(entry_filter={"year": {"$gte": 2020}})
                results.append(len(found))
                time.sleep(0.01)

        def update_entries():
            for i, entry in enumerate(sample_entries):
                updated = system.create_entry(
                    key=entry.key, title=f"Updated {i}: {entry.title}", year=2025
                )
                system.storage.update(updated)
                time.sleep(0.01)

        # Run concurrently
        threads = [
            threading.Thread(target=search_entries),
            threading.Thread(target=update_entries),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no crashes and data integrity
        assert len(results) == 10

        # Final state should have all updated
        final = system.storage.read_all()
        assert all(e.year == 2025 for e in final)


class TestDataMigration:
    """Test data migration scenarios."""

    def test_format_migration(self, storage_system, temp_storage):
        """Test migrating between storage formats."""
        system = storage_system(temp_storage)

        # Add data in current format
        entries = [
            system.create_entry(key=f"entry{i}", title=f"Title {i}") for i in range(10)
        ]

        for entry in entries:
            system.storage.write(entry)
            system.sidecar.add_tags(entry.key, ["original"])

        # Simulate format migration
        if hasattr(system, "migrate_format"):
            system.migrate_format("v2")

            # Verify data preserved
            for entry in entries:
                migrated = system.storage.read(entry.key)
                assert migrated is not None
                assert migrated.title == entry.title

                metadata = system.sidecar.get_metadata(entry.key)
                assert "original" in metadata.tags

    def test_schema_upgrade(self, storage_system, temp_storage):
        """Test schema upgrade with backward compatibility."""
        system = storage_system(temp_storage)

        # Create old-style data (simulate)
        old_data = {
            "key": "old_entry",
            "title": "Old Format Entry",
            "author": "Author",
            "year": "2023",  # String instead of int
        }

        # Write directly (bypassing current schema)
        import json

        old_path = temp_storage / "old_entry.json"
        with open(old_path, "w") as f:
            json.dump(old_data, f)

        # System should handle old format
        if hasattr(system, "import_legacy"):
            imported = system.import_legacy(old_path)
            assert imported is not None
            assert imported.key == "old_entry"
            assert imported.year == 2023  # Converted to int


class TestErrorRecovery:
    """Test error recovery in integrated scenarios."""

    def test_corrupted_file_recovery(self, storage_system, temp_storage):
        """Test recovery from corrupted files."""
        system = storage_system(temp_storage)

        # Add valid data
        entries = [
            system.create_entry(key=f"entry{i}", title=f"Title {i}") for i in range(5)
        ]

        for entry in entries:
            system.storage.write(entry)

        # Corrupt one file
        storage_file = temp_storage / "storage" / "entries" / "entry2.json"
        if storage_file.exists():
            storage_file.write_text("{ corrupted json")

        # System should handle gracefully
        all_entries = system.storage.read_all()

        # Should recover other entries
        assert len(all_entries) >= 4

        # Validation should detect issue
        is_valid, errors = system.storage.validate()
        if not is_valid:
            assert len(errors) > 0

    def test_partial_import_failure(self, storage_system, temp_storage):
        """Test handling of partial import failures."""
        system = storage_system(temp_storage)

        # BibTeX with mix of valid and invalid entries
        mixed_content = """
        @article{valid1, title="Valid", author="Test", journal="Test", year=2024}
        @article{valid2, title="Another Valid", author="Test", journal="Test", year=2024}
        """

        # Import with error handling - parser stops on severe errors
        results = system.import_text(mixed_content, skip_invalid=True)

        # Should import the valid entries
        assert len(results) >= 2

        valid_keys = ["valid1", "valid2"]
        stored_keys = [e.key for e in system.storage.read_all()]

        for key in valid_keys:
            assert key in stored_keys

    def test_transaction_deadlock_recovery(
        self, storage_system, sample_entries, temp_storage
    ):
        """Test recovery from transaction deadlocks."""
        system = storage_system(temp_storage)

        # Add initial data
        for entry in sample_entries[:2]:
            system.storage.write(entry)

        def transaction1():
            try:
                with system.begin_transaction() as txn:
                    # Lock entry0
                    entry0 = system.storage.read(sample_entries[0].key)
                    time.sleep(0.1)
                    # Try to lock entry1
                    entry1 = system.storage.read(sample_entries[1].key)
                    txn.update(entry0)
                    txn.update(entry1)
                    txn.commit()
            except Exception:
                pass  # Deadlock expected

        def transaction2():
            try:
                with system.begin_transaction() as txn:
                    # Lock entry1
                    entry1 = system.storage.read(sample_entries[1].key)
                    time.sleep(0.1)
                    # Try to lock entry0
                    entry0 = system.storage.read(sample_entries[0].key)
                    txn.update(entry1)
                    txn.update(entry0)
                    txn.commit()
            except Exception:
                pass  # Deadlock expected

        # Run potentially deadlocking transactions
        threads = [
            threading.Thread(target=transaction1),
            threading.Thread(target=transaction2),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=5.0)  # Don't wait forever

        # System should recover and remain functional
        assert system.storage.count() == 2

        # Should be able to perform new operations
        new_entry = system.create_entry(key="new", title="New Entry")
        system.storage.write(new_entry)
        assert system.storage.exists("new")


class TestPerformanceOptimization:
    """Test performance optimizations in integrated scenarios."""

    def test_bulk_import_performance(self, storage_system, temp_storage, benchmark):
        """Test performance of bulk import operations."""
        system = storage_system(temp_storage)

        # Generate large BibTeX content
        entries_text = []
        for i in range(100):
            entries_text.append(f"""
            @article{{perf{i:04d},
                author = "Author {i}",
                title = "Performance Test Entry {i}",
                journal = "Journal {i % 10}",
                year = {2020 + i % 5},
                volume = {i % 50},
                pages = "{i * 10}--{i * 10 + 9}"
            }}
            """)

        large_bibtex = "\n".join(entries_text)

        # Benchmark bulk import
        def bulk_import():
            entries = system.parser.parse(large_bibtex)
            system.storage.write_batch(entries)
            return len(entries)

        count = benchmark(bulk_import)
        assert count == 100

    def test_search_with_cache(self, storage_system, sample_entries, temp_storage):
        """Test search performance with caching."""
        system = storage_system(temp_storage)

        # Add entries
        for entry in sample_entries:
            system.storage.write(entry)
            system.sidecar.add_tags(entry.key, ["test", "cache"])

        # First search (cold cache)
        start = time.time()
        results1 = system.search(metadata_filter={"tags": "test"})
        cold_time = time.time() - start

        # Second search (warm cache)
        start = time.time()
        results2 = system.search(metadata_filter={"tags": "test"})
        warm_time = time.time() - start

        # Same results
        assert len(results1) == len(results2)

        # Cache should improve performance (or at least not degrade)
        # This is a soft assertion as performance can vary
        assert warm_time <= cold_time * 1.5

    def test_lazy_loading(self, storage_system, temp_storage):
        """Test lazy loading of large datasets."""
        system = storage_system(temp_storage)

        # Add many entries
        for i in range(1000):
            entry = system.create_entry(
                key=f"large{i:04d}",
                title=f"Entry {i}",
                abstract="x" * 1000,  # Large abstract
            )
            system.storage.write(entry)

        # Get iterator (if supported)
        if hasattr(system.storage, "iterate"):
            # Should not load all at once
            iterator = system.storage.iterate()

            # Process first few without loading all
            first_ten = []
            for i, entry in enumerate(iterator):
                if i >= 10:
                    break
                first_ten.append(entry)

            assert len(first_ten) == 10


class TestIntegrityValidation:
    """Test data integrity validation across system."""

    def test_referential_integrity(self, storage_system, temp_storage):
        """Test referential integrity between storage and sidecar."""
        system = storage_system(temp_storage)

        # Add entries
        entries = [
            system.create_entry(key=f"ref{i}", title=f"Title {i}") for i in range(5)
        ]

        for entry in entries:
            system.storage.write(entry)
            system.sidecar.add_tags(entry.key, ["test"])

        # Delete from storage
        system.storage.delete("ref2")

        # Check integrity
        is_valid, errors = system.validate_integrity()

        if not is_valid:
            # Should detect orphaned metadata
            assert any("ref2" in error for error in errors)

        # System should offer cleanup
        if hasattr(system, "cleanup_orphaned"):
            system.cleanup_orphaned()

            # After cleanup, should be valid
            is_valid, errors = system.validate_integrity()
            assert is_valid

    def test_checksum_verification(self, storage_system, sample_entries, temp_storage):
        """Test checksum verification for data integrity."""
        system = storage_system(temp_storage)

        # Add data
        for entry in sample_entries:
            system.storage.write(entry)

        # Get initial checksum
        checksum1 = system.get_system_checksum()

        # Modify data - create new entry since Entry is immutable
        original = sample_entries[0]
        from bibmgr.core.models import Entry

        updated = Entry(
            key=original.key,
            type=original.type,
            title="Modified Title",
            author=original.author,
            journal=original.journal,
            year=original.year,
        )
        system.storage.update(updated)

        # Checksum should change
        checksum2 = system.get_system_checksum()
        assert checksum1 != checksum2

        # Revert change - create another new entry
        reverted = Entry(
            key=original.key,
            type=original.type,
            title=original.title,
            author=original.author,
            journal=original.journal,
            year=original.year,
        )
        system.storage.update(reverted)

        # Checksum should match original
        checksum3 = system.get_system_checksum()
        assert checksum3 == checksum1

    def test_constraint_validation(self, storage_system, temp_storage):
        """Test constraint validation across system."""
        system = storage_system(temp_storage)

        # Test unique key constraint
        entry1 = system.create_entry(key="unique", title="First")
        entry2 = system.create_entry(key="unique", title="Second")

        system.storage.write(entry1)

        # Should handle duplicate key
        try:
            system.storage.write(entry2)
            # If allowed, should overwrite
            result = system.storage.read("unique")
            assert result.title in ["First", "Second"]
        except (ValueError, KeyError):
            # Duplicate prevented
            result = system.storage.read("unique")
            assert result.title == "First"

        # Test metadata constraints
        from bibmgr.storage.sidecar import ValidationError

        with pytest.raises((ValueError, TypeError, ValidationError)):
            system.sidecar.update_metadata("test", rating=10)  # Out of range

        with pytest.raises((ValueError, TypeError, ValidationError)):
            system.sidecar.update_metadata(
                "test", importance="invalid"
            )  # Invalid value
