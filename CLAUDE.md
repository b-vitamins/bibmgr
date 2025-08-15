# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

bibmgr is a professional bibliography management system with powerful search capabilities and a rich CLI interface. It manages bibliographic entries with full-text search, smart query understanding, multiple format support, and quality validation.

## Development Environment

This project uses Guix + Poetry for dependency management. Always work within the Guix shell:

```bash
# Enter development environment
guix shell -m manifest.scm

# Install Python dependencies
poetry install
```

## Essential Commands

### Quality Control Pipeline (Run before commits)
```bash
# 1. Format code
ruff format .

# 2. Lint with auto-fix
ruff check . --fix

# 3. Type checking
pyright bibmgr/

# 4. Run tests
pytest -xvs

# Run a single test
pytest -xvs tests/test_module.py::test_function_name
```

### CLI Commands
```bash
# Search entries
poetry run bib search "query"
poetry run bib search "author:bengio year:2015"

# Add entries
poetry run bib add @article "author=Name title='Title' year=2024"

# Import/Export
poetry run bib import file.bib
poetry run bib export --format json

# List and show entries
poetry run bib list
poetry run bib show entry-key
```

## Architecture

The codebase follows a clean architecture pattern with these key layers:

### Core Domain (`bibmgr/core/`)
- **models.py**: Immutable Entry, Collection, Tag dataclasses with caching
- **validators.py**: Extensible validation framework for BibTeX compliance
- **duplicates.py**: Duplicate detection with normalized author comparison
- **bibtex.py**: BibTeX parsing and encoding utilities

### Storage Layer (`bibmgr/storage/`)
- Repository pattern with abstract storage backend protocol
- Backends: FileSystem (JSON), SQLite, Memory (for testing)
- Event-driven updates trigger search index refreshes
- Transaction support with validation integration

### Search Engine (`bibmgr/search/`)
- Pluggable backends: Whoosh (production), Memory (testing)
- Query parsing supports field-specific syntax (author:, title:, year:)
- Implicit AND logic for multi-term queries
- BM25 ranking with highlighting support

### CLI Layer (`bibmgr/cli/`)
- Click-based commands with Rich formatting
- Context-managed dependency injection
- Formatters for BibTeX, JSON, CSV, plain text output
- Error handling with debug modes

### Operations (`bibmgr/operations/`)
- High-level business operations and workflows
- CRUD commands with validation
- Import/export workflows with format detection
- Cleaning operations for consistency

## Key Implementation Details

### Adding New Features
1. Domain models are immutable - use `replace()` for updates
2. All storage operations go through Repository protocol
3. Search index updates automatically via EventBus
4. Validators are registered in validator registry
5. CLI commands use dependency injection via context

### Testing Approach
- Use `tmp_path` fixture for file operations
- Mock storage backends with MemoryBackend
- Integration tests cover full CLI workflows
- Environment isolation with `mock_env` fixture
- Run specific tests: `pytest -xvs -k "test_name"`

### Type Safety
- Pyright in "standard" mode enforced
- 100% type coverage on public APIs required
- Use Protocol types for backend interfaces
- Explicit type annotations on function signatures

### Data Storage
- User data: `~/.local/share/bibmgr/`
- Cache data: `~/.cache/bibmgr/`
- Never store data in repository
- XDG-compliant paths via platformdirs

## Common Development Tasks

### Adding a New Validator
1. Create validator in `bibmgr/core/validators.py`
2. Register with `@validator_registry.register`
3. Add tests in `tests/core/test_validators.py`

### Adding a New CLI Command
1. Create command in `bibmgr/cli/commands/`
2. Register in main CLI group
3. Use context for dependency injection
4. Add integration test in `tests/cli/`

### Modifying Search Behavior
1. Update query parser in `bibmgr/search/query/`
2. Adjust search backend implementation
3. Update highlighting logic if needed
4. Test with both Whoosh and Memory backends

### Working with BibTeX
1. Parser in `bibmgr/core/bibtex.py`
2. Handles standard entry types and fields
3. Preserves field order and formatting
4. Supports LaTeX special characters

## Performance Considerations

- Entry models cache computed properties (authors, search_text)
- Search uses Whoosh indexing for sub-millisecond queries
- Batch operations for import/export
- Disk caching with diskcache library
- Lazy loading of large datasets