"""Shell completion utilities for the CLI.

Provides functions for command and argument completion.
"""

from bibmgr.core.models import EntryType


def get_entry_keys(ctx, args, incomplete: str) -> list[str]:
    """Complete entry keys.

    Args:
        ctx: Click context
        args: Command arguments
        incomplete: Incomplete string to match

    Returns:
        List of matching entry keys
    """
    from .context import get_context

    try:
        cli_ctx = get_context()
        if cli_ctx.repository_manager is None:
            return []

        # Get all entry keys
        repo = cli_ctx.repository_manager.get_repository("entry")  # type: ignore
        entries = repo.find_all()

        # Filter by incomplete string
        keys = [e.key for e in entries if e.key.startswith(incomplete)]

        # Sort and limit results
        return sorted(keys)[:50]
    except Exception:
        return []


def get_entry_types(ctx, args, incomplete: str) -> list[str]:
    """Complete entry types.

    Args:
        ctx: Click context
        args: Command arguments
        incomplete: Incomplete string to match

    Returns:
        List of matching entry types
    """
    types = [t.value for t in EntryType]
    return [t for t in types if t.startswith(incomplete.lower())]


def get_collection_names(ctx, args, incomplete: str) -> list[str]:
    """Complete collection names.

    Args:
        ctx: Click context
        args: Command arguments
        incomplete: Incomplete string to match

    Returns:
        List of matching collection names
    """
    from .context import get_context

    try:
        cli_ctx = get_context()
        if cli_ctx.repository_manager is None:
            return []

        # Get all collections
        repo = cli_ctx.repository_manager.get_repository("collection")  # type: ignore
        collections = repo.find_all()

        # Filter by incomplete string
        names = [c.name for c in collections if c.name.startswith(incomplete)]

        # Sort and return
        return sorted(names)
    except Exception:
        return []


def get_tag_names(ctx, args, incomplete: str) -> list[str]:
    """Complete tag names.

    Args:
        ctx: Click context
        args: Command arguments
        incomplete: Incomplete string to match

    Returns:
        List of matching tag names
    """
    from .context import get_context

    try:
        cli_ctx = get_context()
        if cli_ctx.metadata_store is None:
            return []

        # Get all tags
        all_tags = set()
        for entry_key in cli_ctx.metadata_store.list_entries():  # type: ignore
            metadata = cli_ctx.metadata_store.get(entry_key)  # type: ignore
            if metadata and metadata.tags:
                all_tags.update(metadata.tags)

        # Filter by incomplete string
        tags = [t for t in all_tags if t.startswith(incomplete)]

        # Sort and return
        return sorted(tags)
    except Exception:
        return []


def get_field_names(ctx, args, incomplete: str) -> list[str]:
    """Complete field names.

    Args:
        ctx: Click context
        args: Command arguments
        incomplete: Incomplete string to match

    Returns:
        List of matching field names
    """
    # Common BibTeX fields
    fields = [
        "title",
        "author",
        "year",
        "journal",
        "booktitle",
        "publisher",
        "volume",
        "number",
        "pages",
        "doi",
        "isbn",
        "issn",
        "url",
        "abstract",
        "keywords",
        "month",
        "note",
        "edition",
        "series",
        "chapter",
        "address",
        "organization",
        "school",
        "institution",
    ]

    return [f for f in fields if f.startswith(incomplete.lower())]


def get_format_names(ctx, args, incomplete: str) -> list[str]:
    """Complete output format names.

    Args:
        ctx: Click context
        args: Command arguments
        incomplete: Incomplete string to match

    Returns:
        List of matching format names
    """
    formats = [
        "table",
        "bibtex",
        "json",
        "yaml",
        "csv",
        "markdown",
        "apa",
        "ieee",
        "mla",
        "chicago",
    ]

    return [f for f in formats if f.startswith(incomplete.lower())]


def get_sort_fields(ctx, args, incomplete: str) -> list[str]:
    """Complete sort field names.

    Args:
        ctx: Click context
        args: Command arguments
        incomplete: Incomplete string to match

    Returns:
        List of matching sort fields
    """
    # Sort fields with optional :desc suffix
    fields = [
        "key",
        "title",
        "author",
        "year",
        "added",
        "modified",
        "journal",
        "type",
    ]

    results = []

    # Add plain fields
    for field in fields:
        if field.startswith(incomplete.lower()):
            results.append(field)

    # Add fields with :desc
    if ":" in incomplete:
        field_part, _ = incomplete.split(":", 1)
        if any(f.startswith(field_part.lower()) for f in fields):
            results.append(f"{field_part}:desc")
            results.append(f"{field_part}:asc")
    else:
        # Suggest :desc for exact matches
        if incomplete.lower() in fields:
            results.append(f"{incomplete}:desc")
            results.append(f"{incomplete}:asc")

    return results


def install_completion(shell: str = "bash") -> str:
    """Generate shell completion script.

    Args:
        shell: Shell type (bash, zsh, fish)

    Returns:
        Completion script
    """
    if shell == "bash":
        return """# Bash completion for bib
_bib_completion() {
    local IFS=$'\n'
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                   COMP_CWORD=$COMP_CWORD \
                   _BIB_COMPLETE=bash_complete $1 ) )
    return 0
}

complete -F _bib_completion -o default bib
"""
    elif shell == "zsh":
        return """# Zsh completion for bib
_bib_completion() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    (( ! $+commands[bib] )) && return 1

    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _BIB_COMPLETE=zsh_complete bib)}")

    for type arg in ${response}; do
        if [[ "$type" == "plain" ]]; then
            completions+=(${arg})
        elif [[ "$type" == "dir" ]]; then
            _path_files -/
        elif [[ "$type" == "file" ]]; then
            _path_files -f
        fi
    done

    if [ -n "$completions_with_descriptions" ]; then
        _describe -V unsorted completions_with_descriptions -U
    fi

    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}

compdef _bib_completion bib
"""
    elif shell == "fish":
        return """# Fish completion for bib
complete -c bib -f -a '(env _BIB_COMPLETE=fish_complete COMP_WORDS=(commandline -cp) COMP_CWORD=(commandline -t) bib)'
"""
    else:
        return f"# Completion not available for {shell}"
