# bibmgr

Bibliography management system with powerful search capabilities and rich CLI interface.

## Features

- **Fast full-text search** - Sub-millisecond queries with Whoosh indexing
- **Smart query understanding** - Natural language with field-specific syntax
- **Multiple formats** - Import/export BibTeX, JSON, CSV
- **Quality validation** - Automatic consistency and integrity checks
- **Collection management** - Organize entries with tags and collections
- **Rich CLI** - Interactive terminal UI with syntax highlighting

## Installation

```bash
# Clone repository
git clone https://github.com/username/bibmgr.git
cd bibmgr

# Set up environment with Guix
guix shell -m manifest.scm

# Install with Poetry
poetry install
```

## Usage

### Basic Commands

```bash
# Add an entry
poetry run bib add @article "author=Bengio title='Deep Learning' year=2015"

# Search entries
poetry run bib search "neural networks"
poetry run bib search author:bengio year:2015..2020

# List all entries
poetry run bib list

# Show specific entry
poetry run bib show entry-id
```

### Search Syntax

```bash
# Simple search
poetry run bib search deep learning

# Field-specific
poetry run bib search author:lecun title:convolutional

# Boolean operators
poetry run bib search "machine learning" AND (lstm OR rnn)

# Wildcards
poetry run bib search optim*

# Range queries
poetry run bib search year:2020..2024
```

### Import/Export

```bash
# Import BibTeX
poetry run bib import references.bib

# Export to different formats
poetry run bib export --format json > library.json
poetry run bib export --format bibtex > references.bib
poetry run bib export --format csv > entries.csv
```

### Collections and Tags

```bash
# Create collection
poetry run bib collection create ml-papers

# Add entries to collection
poetry run bib collection add ml-papers entry-id1 entry-id2

# Tag entries
poetry run bib tag add entry-id deep-learning nlp

# Search by tag
poetry run bib search tag:deep-learning
```

### Quality Checks

```bash
# Validate all entries
poetry run bib validate

# Find duplicates
poetry run bib dedupe

# Show statistics
poetry run bib stats
```

## Architecture

```
bibmgr/
├── cli/           # Command-line interface
├── core/          # Data models and validators
├── search/        # Search engine and query parsing
├── storage/       # Entry storage and BibTeX parsing
├── quality/       # Validation and consistency checks
├── collections/   # Collection and tag management
├── operations/    # CRUD and import/export
└── citations/     # Citation key generation
```

## Development

### Setup

```bash
# Enter development environment
guix shell -m manifest.scm

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Run tests
pytest -xvs

# Format code
ruff format .

# Lint
ruff check . --fix

# Type check
pyright bibmgr/
```

### Git Hooks

This project uses pre-commit hooks to maintain code quality:

- **Conventional commits** - Enforced via commitizen
- **Code formatting** - Automatic with ruff
- **Linting** - Python code quality checks
- **Type checking** - Pyright for type safety

Commit format: `type(scope): description`

Examples:
- `feat(search): add fuzzy matching support`
- `fix(cli): correct output formatting bug`
- `docs(readme): update installation instructions`
- `chore(deps): update dependencies`

### Testing

```bash
# Run all tests
pytest

# Run specific module
pytest tests/search/

# With coverage
pytest --cov=bibmgr
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Install pre-commit hooks: `pre-commit install`
4. Make changes with tests
5. Ensure commits follow conventional format
6. Run quality checks
7. Submit pull request

## License

MIT