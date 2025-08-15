"""Utilities for CLI.

This module provides various utility functions including:
- Path management
- Context handling
- Editor integration
- Output paging
- Input validation
- Shell completion
"""

from .completion import (
    get_collection_names,
    get_entry_keys,
    get_entry_types,
    get_field_names,
    get_format_names,
    get_sort_fields,
    get_tag_names,
    install_completion,
)
from .context import (
    Context,
    ensure_metadata_store,
    ensure_repository,
    ensure_search_engine,
    get_context,
    pass_context,
)
from .editor import (
    edit_bibtex_entry,
    edit_file,
    edit_note,
    edit_yaml_config,
    get_editor,
    open_in_editor,
)
from .pager import (
    SmartPager,
    get_system_pager,
    page_output,
    page_rich_output,
    should_use_pager,
)
from .paths import (
    ensure_directory,
    expand_path,
    find_project_root,
    get_cache_path,
    get_config_path,
    get_default_export_path,
    get_default_import_path,
    get_storage_path,
)
from .validation import (
    create_validator,
    validate_choice,
    validate_directory_path,
    validate_doi,
    validate_email,
    validate_entry_key,
    validate_entry_type,
    validate_file_path,
    validate_url,
    validate_year,
)

__all__ = [
    # Completion
    "get_collection_names",
    "get_entry_keys",
    "get_entry_types",
    "get_field_names",
    "get_format_names",
    "get_sort_fields",
    "get_tag_names",
    "install_completion",
    # Context
    "Context",
    "ensure_metadata_store",
    "ensure_repository",
    "ensure_search_engine",
    "get_context",
    "pass_context",
    # Editor
    "edit_bibtex_entry",
    "edit_file",
    "edit_note",
    "edit_yaml_config",
    "get_editor",
    "open_in_editor",
    # Pager
    "SmartPager",
    "get_system_pager",
    "page_output",
    "page_rich_output",
    "should_use_pager",
    # Paths
    "ensure_directory",
    "expand_path",
    "find_project_root",
    "get_cache_path",
    "get_config_path",
    "get_default_export_path",
    "get_default_import_path",
    "get_storage_path",
    # Validation
    "create_validator",
    "validate_choice",
    "validate_directory_path",
    "validate_doi",
    "validate_email",
    "validate_entry_key",
    "validate_entry_type",
    "validate_file_path",
    "validate_url",
    "validate_year",
]
