# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

This project uses Guix for dependency management:
```bash
guix shell -m manifest.scm
```

Never use pip install, poetry shell, or venv directly. All dependencies are managed through manifest.scm.

## Common Development Commands

### Running the CLI
```bash
# Main entry point
poetry run bib [command]

# Or directly
python -m bibmgr.cli.main [command]
```

### Testing
```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -xvs

# Run specific test file
pytest tests/search/test_engine.py

# Run with coverage
pytest --cov=bibmgr
```

### Code Quality
```bash
# Format and lint with ruff
ruff format .
ruff check . --fix

# Type checking with pyright
pyright bibmgr/
```

## Architecture Overview

### Core Components

**Search System** (`bibmgr/search/`)
- `engine.py`: Whoosh-based full-text search with BM25F scoring, caching via diskcache
- `query.py`: Query parsing with field-specific searches, boolean operators, wildcards
- `models.py`: Data models using msgspec for fast serialization
- `history.py`: Search history tracking
- `locate.py`: File location utilities

**Storage Layer** (`bibmgr/storage/`)
- `backend.py`: Main storage interface for bibliography entries
- `parser.py`: BibTeX parsing and serialization
- `sidecar.py`: Sidecar file management for metadata
- `system.py`: System-level storage configuration

**CLI Interface** (`bibmgr/cli/`)
- `main.py`: Entry point with Click command groups
- `commands/`: Modular command implementations
  - `entry_commands.py`: CRUD operations on entries
  - `search_commands.py`: Search functionality
  - `collection_commands.py`: Collection management
  - `advanced_commands.py`: Import/export, deduplication, validation
- `formatters.py`: Output formatting (JSON, CSV, BibTeX, Rich tables)
- `output.py`: Rich console output management

**Data Models** (`bibmgr/core/`)
- `models.py`: Core bibliography entry models
- `validators.py`: Data validation logic

**Quality System** (`bibmgr/quality/`)
- `engine.py`: Quality check orchestration
- `validators.py`: Field-specific validators
- `integrity.py`: Data integrity checks
- `consistency.py`: Cross-field consistency validation

### Key Design Patterns

1. **Performance Optimization**
   - msgspec for serialization (faster than JSON/pickle)
   - Whoosh for pure-Python full-text search
   - diskcache for result caching (5-minute TTL)
   - Polars for data manipulation where applicable

2. **CLI Structure**
   - Click-based with command groups
   - Rich for terminal formatting
   - Multiple output formats via formatters
   - Context passing for configuration

3. **Storage Strategy**
   - Entries stored as JSON files
   - Optional sidecar files for metadata
   - Index in ~/.cache/bibmgr/index/
   - Cache in ~/.cache/bibmgr/cache/

4. **Search Features**
   - Field-specific queries: `author:name`, `year:2020..2024`
   - Boolean operators: AND, OR, NOT
   - Wildcards and phrase search
   - Query expansion with CS-domain synonyms
   - Fuzzy matching for spell correction

## Testing Strategy

- Unit tests for each module
- Integration tests for storage operations
- Coverage tests for quality and locate modules
- Fixtures in conftest.py files for test isolation
- Environment variable isolation via pytest fixtures

## Important Conventions

- Python 3.11+ with type hints on function signatures
- Dataclasses and enums for data modeling
- Protocol-based interfaces where applicable
- No __pycache__ or .pyc files in repo
- All paths use pathlib.Path
- f-strings for string formatting