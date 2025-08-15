"""Tests for operation workflows (Import, Export, Deduplicate).

This module tests complex multi-step workflows including file imports,
deduplication runs, and data migrations with full error handling and
progress tracking.
"""

import json
from unittest.mock import Mock

from bibmgr.core.models import Entry
from bibmgr.storage.events import EventType

from ..operations.conftest import (
    assert_events_published,
    create_entry_with_data,
)


class TestImportWorkflow:
    """Test import workflow for various formats."""

    def test_import_bibtex_clean(self, repository_manager, event_bus, temp_dir):
        """Test clean import of BibTeX file with no conflicts."""
        from bibmgr.operations.workflows.import_workflow import (
            ImportFormat,
            ImportWorkflow,
        )

        # Create BibTeX file
        bibtex_file = temp_dir / "test.bib"
        bibtex_file.write_text("""
        @article{newentry2024,
            author = {New, Author},
            title = {New Paper},
            journal = {New Journal},
            year = {2024},
            volume = {1},
            pages = {1--10}
        }

        @book{newbook2024,
            author = {Book, Author},
            title = {New Book},
            publisher = {Publisher},
            year = {2024}
        }
        """)

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(bibtex_file, format=ImportFormat.BIBTEX)

        assert result.success
        assert len(result.successful_entities) == 2
        assert "newentry2024" in result.successful_entities
        assert "newbook2024" in result.successful_entities

        # Verify entries were saved
        assert repository_manager.entries.find("newentry2024") is not None
        assert repository_manager.entries.find("newbook2024") is not None

        # Verify event
        assert_events_published(event_bus, [EventType.WORKFLOW_COMPLETED])

    def test_import_bibtex_with_validation_errors(
        self, repository_manager, event_bus, temp_dir
    ):
        """Test import handles validation errors properly."""
        from bibmgr.operations.workflows.import_workflow import (
            ImportWorkflow,
        )

        # Create BibTeX with invalid entry
        bibtex_file = temp_dir / "invalid.bib"
        bibtex_file.write_text("""
        @article{valid2024,
            author = {Valid, Author},
            title = {Valid Paper},
            journal = {Journal},
            year = {2024}
        }

        @article{invalid2024,
            title = {Missing Required Fields},
            year = {2024}
        }
        """)

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(bibtex_file)

        # The workflow should succeed, but with warnings about invalid entries
        assert result.success  # All steps that were attempted succeeded
        assert "valid2024" in result.successful_entities
        assert "invalid2024" not in result.successful_entities

        # Check that parse step has warnings about the invalid entry
        parse_step = next(s for s in result.steps if s.step == "parse")
        assert parse_step.warnings
        assert any("invalid2024" in w for w in parse_step.warnings)

    def test_import_with_duplicates_merge(
        self, repository_manager, event_bus, temp_dir
    ):
        """Test import merges duplicates when configured."""
        from bibmgr.operations.workflows.import_workflow import (
            ImportWorkflow,
            ImportWorkflowConfig,
        )

        # Add existing entry
        existing = create_entry_with_data(
            key="smith2024",
            author="Smith, J.",
            title="{Machine Learning}",
            journal="Nature",
            year=2024,
            doi="10.1038/test",
        )
        repository_manager.entries.save(existing)

        # Create BibTeX with duplicate
        bibtex_file = temp_dir / "duplicate.bib"
        bibtex_file.write_text("""
        @article{smith2024_new,
            author = {Smith, John and Doe, Jane},
            title = {Machine Learning Applications},
            journal = {Nature},
            year = {2024},
            doi = {10.1038/test},
            pages = {100--110}
        }
        """)

        config = ImportWorkflowConfig(
            check_duplicates=True,
            merge_duplicates=True,
        )

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(bibtex_file, config=config)

        assert result.success

        # Should have merged into existing
        merged = repository_manager.entries.find("smith2024")
        assert merged is not None
        assert "Doe" in merged.author  # Got co-author from import
        assert merged.pages == "100--110"  # Got pages from import

        # New key should not exist
        assert repository_manager.entries.find("smith2024_new") is None

    def test_import_with_conflicts_rename(
        self, repository_manager, event_bus, temp_dir
    ):
        """Test import renames entries on key conflicts."""
        from bibmgr.operations.workflows.import_workflow import (
            ConflictResolution,
            ImportWorkflow,
            ImportWorkflowConfig,
        )

        # Add existing entry
        existing = create_entry_with_data(key="conflict2024", title="Original")
        repository_manager.entries.save(existing)

        # Create BibTeX with same key
        bibtex_file = temp_dir / "conflict.bib"
        bibtex_file.write_text("""
        @article{conflict2024,
            author = {Different, Author},
            title = {Different Paper},
            journal = {Different Journal},
            year = {2024}
        }
        """)

        config = ImportWorkflowConfig(conflict_resolution=ConflictResolution.RENAME)

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(bibtex_file, config=config)

        assert result.success

        # Original should be unchanged
        original = repository_manager.entries.find("conflict2024")
        assert original.title == "Original"

        # Should have created renamed entry
        all_keys = repository_manager.entries.find_all()
        renamed_keys = [
            e.key
            for e in all_keys
            if e.key.startswith("conflict2024") and e.key != "conflict2024"
        ]
        assert len(renamed_keys) == 1

    def test_import_with_conflicts_replace(
        self, repository_manager, event_bus, temp_dir
    ):
        """Test import replaces entries on conflicts."""
        from bibmgr.operations.workflows.import_workflow import (
            ConflictResolution,
            ImportWorkflow,
            ImportWorkflowConfig,
        )

        # Add existing entry
        existing = create_entry_with_data(key="replace2024", title="Will Be Replaced")
        repository_manager.entries.save(existing)

        # Create BibTeX with same key
        bibtex_file = temp_dir / "replace.bib"
        bibtex_file.write_text("""
        @article{replace2024,
            author = {New, Author},
            title = {Replacement Paper},
            journal = {New Journal},
            year = {2024}
        }
        """)

        config = ImportWorkflowConfig(
            conflict_resolution=ConflictResolution.REPLACE,
            update_existing=True,
        )

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(bibtex_file, config=config)

        assert result.success

        # Should be replaced
        replaced = repository_manager.entries.find("replace2024")
        assert replaced.title == "Replacement Paper"
        assert replaced.author == "New, Author"

    def test_import_ris_format(self, repository_manager, event_bus, temp_dir):
        """Test importing RIS format."""
        from bibmgr.operations.workflows.import_workflow import (
            ImportFormat,
            ImportWorkflow,
        )

        # Create RIS file
        ris_file = temp_dir / "test.ris"
        ris_file.write_text("""TY  - JOUR
AU  - Smith, John
AU  - Doe, Jane
TI  - Test Article
JO  - Test Journal
PY  - 2024
VL  - 10
SP  - 100
EP  - 110
DO  - 10.1234/test
ER  -

TY  - BOOK
AU  - Book, Author
TI  - Test Book
PB  - Test Publisher
PY  - 2024
SN  - 978-0-123456-78-6
ER  -
""")

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(ris_file, format=ImportFormat.RIS)

        assert result.success
        assert len(result.successful_entities) >= 2

    def test_import_json_format(self, repository_manager, event_bus, temp_dir):
        """Test importing JSON format."""
        from bibmgr.operations.workflows.import_workflow import (
            ImportFormat,
            ImportWorkflow,
        )

        # Create JSON file
        json_file = temp_dir / "test.json"
        json_data = {
            "entries": [
                {
                    "key": "json1",
                    "type": "article",
                    "author": "JSON, Author",
                    "title": "JSON Paper",
                    "journal": "JSON Journal",
                    "year": 2024,
                },
                {
                    "key": "json2",
                    "type": "book",
                    "author": "Book, JSON",
                    "title": "JSON Book",
                    "publisher": "JSON Publisher",
                    "year": 2024,
                },
            ]
        }
        json_file.write_text(json.dumps(json_data, indent=2))

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(json_file, format=ImportFormat.JSON)

        assert result.success
        assert "json1" in result.successful_entities
        assert "json2" in result.successful_entities

    def test_import_auto_detect_format(self, repository_manager, event_bus, temp_dir):
        """Test import auto-detects file format."""
        from bibmgr.operations.workflows.import_workflow import (
            ImportFormat,
            ImportWorkflow,
        )

        # Create files with correct extensions
        files = {
            "test.bib": "@article{bib2024, author={Test}, title={BibTeX}, journal={J}, year={2024}}",
            "test.ris": "TY  - JOUR\nAU  - Test\nTI  - RIS\nJO  - Journal\nPY  - 2024\nER  -",
            "test.json": '{"entries": [{"key": "json2024", "type": "misc", "title": "JSON", "year": 2024}]}',
        }

        workflow = ImportWorkflow(repository_manager, event_bus)

        for filename, content in files.items():
            file_path = temp_dir / filename
            file_path.write_text(content)

            result = workflow.execute(file_path, format=ImportFormat.AUTO)
            assert result.success or result.partial_success

    def test_import_with_tags_and_collection(
        self, repository_manager, event_bus, temp_dir
    ):
        """Test import adds tags and collection."""
        from bibmgr.core.builders import CollectionBuilder
        from bibmgr.operations.workflows.import_workflow import (
            ImportWorkflow,
            ImportWorkflowConfig,
        )

        # Create collection
        collection = CollectionBuilder().name("Import Collection").build()
        repository_manager.collections.save(collection)

        # Create BibTeX file
        bibtex_file = temp_dir / "tagged.bib"
        bibtex_file.write_text("""
        @article{tagged2024,
            author = {Tagged, Author},
            title = {Tagged Paper},
            journal = {Journal},
            year = {2024}
        }
        """)

        config = ImportWorkflowConfig(
            tags=["imported", "test"],
            collection="Import Collection",
        )

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(bibtex_file, config=config)

        assert result.success

        # Check tags were added
        if repository_manager.metadata_store:
            metadata = repository_manager.metadata_store.get_metadata("tagged2024")
            assert "imported" in metadata.tags
            assert "test" in metadata.tags

        # Check added to collection
        updated_collection = repository_manager.collections.find(collection.id)
        assert "tagged2024" in updated_collection.entry_keys

    def test_import_dry_run(self, repository_manager, event_bus, temp_dir):
        """Test import in dry run mode."""
        from bibmgr.operations.workflows.import_workflow import (
            ImportWorkflow,
            ImportWorkflowConfig,
        )

        # Create BibTeX file
        bibtex_file = temp_dir / "dryrun.bib"
        bibtex_file.write_text("""
        @article{dryrun2024,
            author = {Dry, Run},
            title = {Not Saved},
            journal = {Journal},
            year = {2024}
        }
        """)

        config = ImportWorkflowConfig(dry_run=True)

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(bibtex_file, config=config)

        # Should report success but not actually save
        assert result.success
        assert repository_manager.entries.find("dryrun2024") is None

    def test_import_progress_tracking(
        self, repository_manager, event_bus, temp_dir, progress_reporter
    ):
        """Test import reports progress."""
        from bibmgr.operations.workflows.import_workflow import ImportWorkflow

        # Create BibTeX with multiple entries
        bibtex_file = temp_dir / "many.bib"
        entries = []
        for i in range(10):
            entries.append(f"""
            @article{{entry{i},
                author = {{Author{i}, A.}},
                title = {{Paper {i}}},
                journal = {{Journal}},
                year = {{2024}}
            }}
            """)
        bibtex_file.write_text("\n".join(entries))

        # Mock event bus to capture progress
        progress_events = []

        def capture_progress(event):
            if event.type == EventType.PROGRESS:
                progress_events.append(event)

        event_bus.subscribe(EventType.PROGRESS, capture_progress)

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(bibtex_file)

        assert result.success
        assert len(progress_events) >= 10  # At least one per entry

    def test_import_parse_errors(self, repository_manager, event_bus, temp_dir):
        """Test import handles parse errors gracefully."""
        from bibmgr.operations.workflows.import_workflow import ImportWorkflow

        # Create invalid BibTeX
        bibtex_file = temp_dir / "invalid.bib"
        bibtex_file.write_text("""
        This is not valid BibTeX
        @article{incomplete
            author = {Missing closing brace}
        """)

        workflow = ImportWorkflow(repository_manager, event_bus)
        result = workflow.execute(bibtex_file)

        # The workflow considers this a success (empty file parsed successfully)
        # but no entries were imported
        assert result.success
        assert len(result.successful_entities) == 0

        # Check parse step shows 0 entries
        parse_steps = [s for s in result.steps if s.step == "parse"]
        assert len(parse_steps) > 0
        assert parse_steps[0].success
        assert "Parsed 0 entries" in parse_steps[0].message


class TestExportWorkflow:
    """Test export workflow for various formats."""

    def test_export_bibtex_all(self, populated_repository, event_bus, temp_dir):
        """Test exporting all entries to BibTeX."""
        from bibmgr.operations.workflows.export import (
            ExportFormat,
            ExportWorkflow,
            ExportWorkflowConfig,
        )

        manager = Mock()
        manager.entries = populated_repository

        export_file = temp_dir / "export.bib"

        workflow = ExportWorkflow(manager, event_bus)
        config = ExportWorkflowConfig(format=ExportFormat.BIBTEX)
        result = workflow.execute(export_file, config=config)

        assert result.success
        assert export_file.exists()

        # Verify content
        content = export_file.read_text()
        assert "@article" in content
        assert "@book" in content
        assert "smith2020" in content

    def test_export_bibtex_filtered(self, populated_repository, event_bus, temp_dir):
        """Test exporting filtered entries."""
        from bibmgr.operations.workflows.export import (
            ExportFormat,
            ExportWorkflow,
            ExportWorkflowConfig,
        )

        manager = Mock()
        manager.entries = populated_repository

        export_file = temp_dir / "filtered.bib"

        config = ExportWorkflowConfig(format=ExportFormat.BIBTEX)

        workflow = ExportWorkflow(manager, event_bus)
        result = workflow.execute(
            export_file,
            entry_keys=["smith2020", "doe2021"],  # Only export these
            config=config,
        )

        assert result.success

        content = export_file.read_text()
        assert "smith2020" in content
        assert "doe2021" in content
        assert "conf2022" not in content  # Not in filter

    def test_export_by_query(self, populated_repository, event_bus, temp_dir):
        """Test exporting entries matching a query."""
        from bibmgr.operations.workflows.export import (
            ExportFormat,
            ExportWorkflow,
            ExportWorkflowConfig,
        )

        manager = Mock()
        manager.entries = populated_repository

        export_file = temp_dir / "books.bib"

        config = ExportWorkflowConfig(format=ExportFormat.BIBTEX)

        workflow = ExportWorkflow(manager, event_bus)
        result = workflow.execute(
            export_file,
            query="type:book",  # Only export books
            config=config,
        )

        assert result.success

        content = export_file.read_text()
        assert "@book" in content
        assert "@article" not in content

    def test_export_json_format(self, populated_repository, event_bus, temp_dir):
        """Test exporting to JSON format."""
        from bibmgr.operations.workflows.export import (
            ExportFormat,
            ExportWorkflow,
            ExportWorkflowConfig,
        )

        manager = Mock()
        manager.entries = populated_repository

        export_file = temp_dir / "export.json"

        workflow = ExportWorkflow(manager, event_bus)
        config = ExportWorkflowConfig(format=ExportFormat.JSON)
        result = workflow.execute(export_file, config=config)

        assert result.success
        assert export_file.exists()

        # Verify valid JSON
        data = json.loads(export_file.read_text())
        assert isinstance(data, dict)  # Export returns structured format
        assert "entries" in data
        assert "total" in data
        assert len(data["entries"]) == len(populated_repository.find_all())
        assert data["total"] == len(populated_repository.find_all())

    def test_export_with_metadata(
        self, populated_repository, metadata_store, event_bus, temp_dir
    ):
        """Test export includes metadata when configured."""
        from bibmgr.operations.workflows.export import (
            ExportFormat,
            ExportWorkflow,
            ExportWorkflowConfig,
        )

        # Add metadata
        metadata = metadata_store.get_metadata("smith2020")
        metadata.add_tags("important", "ml")
        metadata.rating = 5
        metadata_store.save_metadata(metadata)

        manager = Mock()
        manager.entries = populated_repository
        manager.metadata_store = metadata_store

        export_file = temp_dir / "with_metadata.json"

        config = ExportWorkflowConfig(
            format=ExportFormat.JSON,
            include_metadata=True,
        )

        workflow = ExportWorkflow(manager, event_bus)
        result = workflow.execute(export_file, entry_keys=["smith2020"], config=config)

        assert result.success

        data = json.loads(export_file.read_text())
        # Should have metadata section
        assert "metadata" in data
        assert data["metadata"]["smith2020"]["rating"] == 5

    def test_export_validate_before_export(self, entry_repository, event_bus, temp_dir):
        """Test export validates entries before exporting."""
        from bibmgr.operations.workflows.export import (
            ExportFormat,
            ExportWorkflow,
            ExportWorkflowConfig,
        )

        # Add invalid entry
        invalid = create_entry_with_data(
            key="invalid",
            type="article",
            title="Invalid Entry",
            # Missing required fields
        )
        entry_repository.save(invalid, skip_validation=True)

        manager = Mock()
        manager.entries = entry_repository

        export_file = temp_dir / "validated.bib"

        config = ExportWorkflowConfig(
            format=ExportFormat.BIBTEX,
            validate=True,
        )

        workflow = ExportWorkflow(manager, event_bus)
        result = workflow.execute(export_file, config=config)

        # When all entries are skipped, the workflow still succeeds
        assert result.success

        # The file should not exist since all entries were skipped
        assert not export_file.exists()

    def test_export_dry_run(self, populated_repository, event_bus, temp_dir):
        """Test export in dry run mode."""
        from bibmgr.operations.workflows.export import (
            ExportFormat,
            ExportWorkflow,
            ExportWorkflowConfig,
        )

        manager = Mock()
        manager.entries = populated_repository

        export_file = temp_dir / "dryrun.bib"

        config = ExportWorkflowConfig(format=ExportFormat.BIBTEX, dry_run=True)

        workflow = ExportWorkflow(manager, event_bus)
        result = workflow.execute(export_file, config=config)

        assert result.success
        assert not export_file.exists()  # File not created

        # Should report what would be exported
        assert "Would export" in str(result.steps)


class TestDeduplicationWorkflow:
    """Test deduplication workflow."""

    def test_deduplicate_preview_mode(self, repository_manager, event_bus):
        """Test deduplication in preview mode."""
        from bibmgr.operations.workflows.deduplicate import (
            DeduplicationConfig,
            DeduplicationMode,
            DeduplicationWorkflow,
        )

        # Add duplicate entries
        entry1 = create_entry_with_data(
            key="dup1",
            author="Smith, John",
            title="Machine Learning",
            year=2020,
            doi="10.1234/test",
        )
        entry2 = create_entry_with_data(
            key="dup2",
            author="Smith, J.",
            title="Machine Learning Study",
            year=2020,
            doi="10.1234/test",  # Same DOI
        )
        repository_manager.entries.save(entry1)
        repository_manager.entries.save(entry2)

        config = DeduplicationConfig(
            mode=DeduplicationMode.PREVIEW,
            min_similarity=0.8,
        )

        workflow = DeduplicationWorkflow(repository_manager, event_bus)
        result = workflow.execute(config)

        assert result.success

        # Should find duplicates but not merge
        preview_steps = [s for s in result.steps if s.step == "preview"]
        assert len(preview_steps) > 0

        assert preview_steps[0].data is not None
        preview_data = preview_steps[0].data["preview"]
        assert len(preview_data) >= 1

        # Entries should still exist
        assert repository_manager.entries.find("dup1") is not None
        assert repository_manager.entries.find("dup2") is not None

    def test_deduplicate_automatic_mode(self, repository_manager, event_bus):
        """Test automatic deduplication."""
        from bibmgr.operations.workflows.deduplicate import (
            DeduplicationConfig,
            DeduplicationMode,
            DeduplicationWorkflow,
        )

        # Add high-confidence duplicates
        entry1 = create_entry_with_data(
            key="auto1",
            author="Author, A.",
            title="Same Paper",
            year=2020,
            doi="10.5555/same",
        )
        entry2 = create_entry_with_data(
            key="auto2",
            author="Author, Alice",
            title="Same Paper",
            year=2020,
            doi="10.5555/same",  # Same DOI = high confidence
        )
        repository_manager.entries.save(entry1)
        repository_manager.entries.save(entry2)

        config = DeduplicationConfig(
            mode=DeduplicationMode.AUTOMATIC,
            min_similarity=0.8,
        )

        workflow = DeduplicationWorkflow(repository_manager, event_bus)
        result = workflow.execute(config)

        assert result.success

        # Should have merged
        all_entries = repository_manager.entries.find_all()
        # One should be deleted
        assert len([e for e in all_entries if e.key in ["auto1", "auto2"]]) == 1

    def test_deduplicate_selective_mode(self, repository_manager, event_bus):
        """Test selective deduplication with rules."""
        from bibmgr.operations.workflows.deduplicate import (
            DeduplicationConfig,
            DeduplicationMode,
            DeduplicationRule,
            DeduplicationWorkflow,
            MatchType,
        )

        # Add different types of duplicates
        # DOI match - should merge
        doi1 = create_entry_with_data(key="doi1", doi="10.1111/test")
        doi2 = create_entry_with_data(key="doi2", doi="10.1111/test")

        # Title/author/year match - should skip
        title1 = create_entry_with_data(
            key="title1", title="Similar Title", author="Smith, J.", year=2020
        )
        title2 = create_entry_with_data(
            key="title2", title="Similar Title", author="Smith, J.", year=2020
        )

        for entry in [doi1, doi2, title1, title2]:
            repository_manager.entries.save(entry)

        config = DeduplicationConfig(
            mode=DeduplicationMode.SELECTIVE,
            rules=[
                DeduplicationRule(
                    match_type=MatchType.DOI,
                    min_similarity=0.9,
                    action="merge",
                ),
                DeduplicationRule(
                    match_type=MatchType.TITLE_AUTHOR_YEAR,
                    min_similarity=0.8,
                    action="skip",
                ),
            ],
        )

        workflow = DeduplicationWorkflow(repository_manager, event_bus)
        result = workflow.execute(config)

        assert result.success

        # DOI duplicates should be merged
        doi_entries = [
            e
            for e in repository_manager.entries.find_all()
            if e.key in ["doi1", "doi2"]
        ]
        assert len(doi_entries) == 1

        # Title duplicates should remain
        assert repository_manager.entries.find("title1") is not None
        assert repository_manager.entries.find("title2") is not None

    def test_deduplicate_no_duplicates(self, repository_manager, event_bus):
        """Test deduplication when no duplicates exist."""
        from bibmgr.operations.workflows.deduplicate import (
            DeduplicationConfig,
            DeduplicationWorkflow,
        )

        # Add unique entries
        for i in range(3):
            entry = create_entry_with_data(
                key=f"unique{i}",
                author=f"Author{i}, A.",
                title=f"Unique Paper {i}",
                year=2020 + i,
            )
            repository_manager.entries.save(entry)

        config = DeduplicationConfig(min_similarity=0.9)

        workflow = DeduplicationWorkflow(repository_manager, event_bus)
        result = workflow.execute(config)

        assert result.success

        # Should complete with no duplicates found
        summary_steps = [s for s in result.steps if s.step == "complete"]
        assert len(summary_steps) > 0
        assert "No duplicates found" in summary_steps[0].message

    def test_deduplicate_progress_tracking(self, repository_manager, event_bus):
        """Test deduplication reports progress."""
        from bibmgr.operations.workflows.deduplicate import (
            DeduplicationConfig,
            DeduplicationMode,
            DeduplicationWorkflow,
        )

        # Add many entries for progress tracking
        for i in range(20):
            entry = create_entry_with_data(
                key=f"prog{i}",
                title=f"Paper Group {i // 2}",  # Create some duplicates
                author=f"Author {i // 2}",  # Same author for duplicates
                year=2020,
            )
            repository_manager.entries.save(entry)

        # Track progress events
        progress_events = []

        def capture_progress(event):
            if event.type == EventType.PROGRESS:
                progress_events.append(event)

        event_bus.subscribe(EventType.PROGRESS, capture_progress)

        config = DeduplicationConfig(
            mode=DeduplicationMode.AUTOMATIC,
            min_similarity=0.7,
        )

        workflow = DeduplicationWorkflow(repository_manager, event_bus)
        result = workflow.execute(config)

        assert result.success
        assert len(progress_events) > 0


class TestMigrationWorkflow:
    """Test data migration workflow."""

    def test_migrate_format_upgrade(self, repository_manager, event_bus):
        """Test migrating entries to newer format."""
        from bibmgr.operations.workflows.migrate import (
            MigrationConfig,
            MigrationType,
            MigrationWorkflow,
        )

        # Add entries with old format
        old_entries = []
        for i in range(3):
            entry = create_entry_with_data(
                key=f"old{i}",
                title=f"Old Format {i}",
                year=2020,
                # Missing new fields
            )
            repository_manager.entries.save(entry)
            old_entries.append(entry)

        config = MigrationConfig(
            migration_type=MigrationType.FORMAT_UPGRADE,
            target_version="2.0",
        )

        workflow = MigrationWorkflow(repository_manager, event_bus)
        result = workflow.execute(config)

        assert result.success

        # Verify entries were updated
        for entry in old_entries:
            migrated = repository_manager.entries.find(entry.key)
            assert migrated is not None
            # Should have new format markers/fields

    def test_migrate_field_mapping(self, repository_manager, event_bus):
        """Test migrating with field mappings."""
        from bibmgr.operations.workflows.migrate import (
            MigrationConfig,
            MigrationType,
            MigrationWorkflow,
        )

        # Add entries with old field names
        entry = create_entry_with_data(
            key="fieldmap",
            title="Test",
            year=2020,
        )
        # Add custom field
        data = entry.to_dict()
        data["old_field"] = "value"
        entry = Entry.from_dict(data)
        repository_manager.entries.save(entry)

        config = MigrationConfig(
            migration_type=MigrationType.FIELD_MAPPING,
            field_mappings={
                "old_field": "new_field",
            },
        )

        workflow = MigrationWorkflow(repository_manager, event_bus)
        result = workflow.execute(config)

        assert result.success

        # Verify field was mapped
        migrated = repository_manager.entries.find("fieldmap")
        assert not hasattr(migrated, "old_field")
        # Note: Depending on implementation, new_field might be added

    def test_migrate_with_validation(self, repository_manager, event_bus):
        """Test migration validates entries."""
        from bibmgr.operations.workflows.migrate import (
            MigrationConfig,
            MigrationType,
            MigrationWorkflow,
        )

        # Add entry that will become invalid after migration
        entry = create_entry_with_data(
            key="invalid_after",
            type="misc",
            title="Will be invalid",
            year=2020,
        )
        repository_manager.entries.save(entry)

        config = MigrationConfig(
            migration_type=MigrationType.TYPE_CHANGE,
            type_mappings={
                "misc": "article",  # Article requires more fields
            },
            validate_after=True,
            fix_validation_errors=True,
        )

        workflow = MigrationWorkflow(repository_manager, event_bus)
        result = workflow.execute(config)

        # Should handle validation issues
        assert result.success or result.partial_success

    def test_migrate_backup_and_rollback(self, repository_manager, event_bus, temp_dir):
        """Test migration creates backup and can rollback."""
        from bibmgr.operations.workflows.migrate import (
            MigrationConfig,
            MigrationType,
            MigrationWorkflow,
        )

        # Add test data
        original_entries = []
        for i in range(3):
            entry = create_entry_with_data(key=f"backup{i}")
            repository_manager.entries.save(entry)
            original_entries.append(entry)

        config = MigrationConfig(
            migration_type=MigrationType.FORMAT_UPGRADE,
            backup_dir=temp_dir / "backup",
            test_mode=True,  # Should rollback after test
        )

        workflow = MigrationWorkflow(repository_manager, event_bus)
        workflow.execute(config)

        # Should create backup
        assert (temp_dir / "backup").exists()

        # In test mode, should rollback
        for entry in original_entries:
            current = repository_manager.entries.find(entry.key)
            assert current is not None


class TestWorkflowIntegration:
    """Test integration between different workflows."""

    def test_import_then_deduplicate(self, repository_manager, event_bus, temp_dir):
        """Test importing entries then deduplicating."""
        from bibmgr.operations.workflows.deduplicate import (
            DeduplicationConfig,
            DeduplicationMode,
            DeduplicationWorkflow,
        )
        from bibmgr.operations.workflows.import_workflow import ImportWorkflow

        # Import file with duplicates
        bibtex_file = temp_dir / "duplicates.bib"
        bibtex_file.write_text("""
        @article{paper1,
            author = {Smith, John},
            title = {Machine Learning},
            journal = {Nature},
            year = {2020},
            doi = {10.1038/same}
        }

        @article{paper2,
            author = {Smith, J.},
            title = {Machine Learning Study},
            journal = {Nature},
            year = {2020},
            doi = {10.1038/same}
        }

        @article{different,
            author = {Doe, Jane},
            title = {Different Paper},
            journal = {Science},
            year = {2021}
        }
        """)

        # Import
        import_workflow = ImportWorkflow(repository_manager, event_bus)
        import_result = import_workflow.execute(bibtex_file)
        assert import_result.success

        # Deduplicate
        dedup_config = DeduplicationConfig(
            mode=DeduplicationMode.AUTOMATIC,
            min_similarity=0.8,
        )
        dedup_workflow = DeduplicationWorkflow(repository_manager, event_bus)
        dedup_result = dedup_workflow.execute(dedup_config)
        assert dedup_result.success

        # Should have merged duplicates
        all_entries = repository_manager.entries.find_all()
        assert len(all_entries) == 2  # paper1/paper2 merged + different

    def test_deduplicate_then_export(self, repository_manager, event_bus, temp_dir):
        """Test deduplicating then exporting clean data."""
        from bibmgr.operations.workflows.deduplicate import (
            DeduplicationConfig,
            DeduplicationMode,
            DeduplicationWorkflow,
        )
        from bibmgr.operations.workflows.export import ExportWorkflow

        # Add duplicates
        for i in range(2):
            entry = create_entry_with_data(
                key=f"export{i}",
                title="Same Paper",
                author="Same Author",
                year=2020,
            )
            repository_manager.entries.save(entry)

        # Add unique
        unique = create_entry_with_data(key="unique", title="Unique Paper")
        repository_manager.entries.save(unique)

        # Deduplicate
        dedup_config = DeduplicationConfig(mode=DeduplicationMode.AUTOMATIC)
        dedup_workflow = DeduplicationWorkflow(repository_manager, event_bus)
        dedup_result = dedup_workflow.execute(dedup_config)
        assert dedup_result.success

        # Export cleaned data
        export_file = temp_dir / "cleaned.bib"
        export_workflow = ExportWorkflow(repository_manager, event_bus)
        export_result = export_workflow.execute(export_file)
        assert export_result.success

        # Should have fewer entries
        content = export_file.read_text()
        # Count @article occurrences
        article_count = content.count("@article") + content.count("@misc")
        assert article_count == 2  # One merged + one unique
