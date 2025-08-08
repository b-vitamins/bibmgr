"""Template system for note creation.

This module provides a flexible template system for creating notes
with predefined structures and variable substitution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from bibmgr.core.models import Entry
from bibmgr.notes.exceptions import (
    TemplateNotFoundError,
    TemplateValidationError,
)
from bibmgr.notes.models import NoteType


@dataclass(frozen=True)
class NoteTemplate:
    """Template for creating notes with consistent structure."""

    name: str
    type: NoteType
    title_template: str
    content_template: str
    tags: list[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        """Validate template data."""
        if not self.name:
            raise ValueError("Template name cannot be empty")

        if not self.title_template:
            raise ValueError("Title template cannot be empty")

        if not self.content_template:
            raise ValueError("Content template cannot be empty")

        if not isinstance(self.type, NoteType):
            try:
                object.__setattr__(self, "type", NoteType(self.type))
            except (ValueError, KeyError):
                raise ValueError(f"Invalid note type: {self.type}")

        # Make tags immutable
        object.__setattr__(self, "tags", tuple(self.tags))

    def is_valid(self) -> bool:
        """Check if template is valid."""
        return bool(self.name and self.title_template and self.content_template)

    def render(
        self,
        entry: Optional[Entry] = None,
        **variables: Any,
    ) -> tuple[str, str]:
        """Render template with variables.

        Args:
            entry: Optional bibliography entry for context
            **variables: Additional template variables

        Returns:
            Tuple of (rendered_title, rendered_content)

        Raises:
            KeyError: If required variable is missing
        """
        # Build context with defaults
        context = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "year": datetime.now().year,
            "month": datetime.now().strftime("%B"),
            "day": datetime.now().day,
        }

        # Add entry data if provided
        if entry:
            context.update(
                {
                    "entry_key": entry.key,
                    "title": entry.title or "Untitled",
                    "author": entry.author or "Unknown",
                    "authors": entry.author or "Unknown",  # Alias
                    "year": entry.year or "n.d.",
                    "journal": entry.journal or "",
                    "publisher": entry.publisher or "",
                    "doi": entry.doi or "",
                    "url": entry.url or "",
                    "abstract": entry.abstract or "",
                }
            )

        # Add custom variables (override defaults)
        context.update(variables)

        # Render templates
        try:
            title = self.title_template.format(**context)
            content = self.content_template.format(**context)
        except KeyError as e:
            raise KeyError(
                f"Missing required template variable: {e}. "
                f"Available variables: {list(context.keys())}"
            )

        return title, content


# Default templates
DEFAULT_TEMPLATES = [
    NoteTemplate(
        name="summary",
        type=NoteType.SUMMARY,
        title_template="Summary: {title}",
        content_template="""## Summary

**Entry**: {entry_key}
**Title**: {title}
**Author**: {author}
**Year**: {year}
**Date**: {date}

### Main Points
- 

### Key Findings
- 

### Methodology
- 

### Conclusions
- 

### Relevance to My Research
- 
""",
        tags=["summary"],
        description="Comprehensive summary of a paper",
    ),
    NoteTemplate(
        name="critique",
        type=NoteType.CRITIQUE,
        title_template="Critique: {title}",
        content_template="""## Critical Analysis

**Entry**: {entry_key}
**Date**: {date}

### Strengths
- 

### Weaknesses
- 

### Methodological Issues
- 

### Alternative Interpretations
- 

### Suggestions for Improvement
- 

### Overall Assessment
- 
""",
        tags=["critique", "analysis"],
        description="Critical analysis of a paper",
    ),
    NoteTemplate(
        name="idea",
        type=NoteType.IDEA,
        title_template="Research Idea from {title}",
        content_template="""## Research Idea

**Inspired by**: {entry_key}
**Date**: {date}

### The Idea
- 

### Motivation
- 

### Potential Approach
- 

### Expected Outcomes
- 

### Resources Needed
- 

### Next Steps
- [ ] 
""",
        tags=["idea", "research"],
        description="Research idea inspired by a paper",
    ),
    NoteTemplate(
        name="methodology",
        type=NoteType.METHODOLOGY,
        title_template="Methodology Notes: {title}",
        content_template="""## Methodology Notes

**Entry**: {entry_key}
**Date**: {date}

### Method Overview
- 

### Data Collection
- **Sample Size**: 
- **Sampling Method**: 
- **Data Sources**: 

### Analysis Techniques
- 

### Statistical Tests
- 

### Limitations
- 

### Applicability to My Work
- 
""",
        tags=["methodology", "methods"],
        description="Detailed methodology notes",
    ),
    NoteTemplate(
        name="paper_review",
        type=NoteType.CRITIQUE,
        title_template="Review: {title}",
        content_template="""## Review of {title}

**Authors**: {authors}
**Year**: {year}
**Date**: {date}

### Summary
{summary}

### Contributions
- 

### Strengths
- 

### Weaknesses
- 

### Technical Quality
- **Clarity**: /5
- **Originality**: /5
- **Significance**: /5
- **Evaluation**: /5

### Detailed Comments

#### Introduction
- 

#### Related Work
- 

#### Methodology
- 

#### Results
- 

#### Discussion
- 

### Questions for Authors
- 

### Recommendation
- [ ] Accept
- [ ] Minor Revision
- [ ] Major Revision
- [ ] Reject

### Verdict
""",
        tags=["review", "critique"],
        description="Comprehensive paper review template",
    ),
    NoteTemplate(
        name="reading_notes",
        type=NoteType.GENERAL,
        title_template="Reading Notes: {title}",
        content_template="""## Reading Notes

**Entry**: {entry_key}
**Date**: {date}

### First Impressions
- 

### Page-by-Page Notes

#### Introduction
- 

#### Methods
- 

#### Results
- 

#### Discussion
- 

#### Conclusion
- 

### Questions
- 

### To Follow Up
- [ ] 
""",
        tags=["reading-notes"],
        description="General reading notes",
    ),
    NoteTemplate(
        name="literature_review",
        type=NoteType.REFERENCE,
        title_template="Literature Review: {title}",
        content_template="""## Literature Review Entry

**Entry**: {entry_key}
**Date**: {date}

### Contribution to Field
- 

### Relation to Other Work
- 

### Theoretical Framework
- 

### Empirical Evidence
- 

### Gaps Identified
- 

### Future Directions Suggested
- 

### Relevance to My Literature Review
- **Section**: 
- **Key Point**: 
""",
        tags=["literature-review", "reference"],
        description="Literature review notes",
    ),
    NoteTemplate(
        name="quick_note",
        type=NoteType.GENERAL,
        title_template="Quick Note: {title}",
        content_template="""**Date**: {date} {time}

""",
        tags=["quick"],
        description="Quick note or thought",
    ),
    NoteTemplate(
        name="meeting_notes",
        type=NoteType.GENERAL,
        title_template="Meeting Notes: Discussion of {title}",
        content_template="""## Meeting Notes

**Date**: {date}
**Paper Discussed**: {entry_key}
**Attendees**: 

### Discussion Points
- 

### Action Items
- [ ] 

### Decisions Made
- 

### Next Meeting
- **Date**: 
- **Topics**: 
""",
        tags=["meeting"],
        description="Meeting notes about a paper",
    ),
    NoteTemplate(
        name="question",
        type=NoteType.QUESTION,
        title_template="Questions about {title}",
        content_template="""## Questions

**Entry**: {entry_key}
**Date**: {date}

### Main Questions
1. 
2. 
3. 

### Context
- 

### Possible Answers
- 

### People to Ask
- 

### References to Check
- 
""",
        tags=["question"],
        description="Questions about a paper",
    ),
    NoteTemplate(
        name="todo",
        type=NoteType.TODO,
        title_template="TODO: {title}",
        content_template="""## Action Items

**Entry**: {entry_key}
**Date**: {date}
**Priority**: High/Medium/Low

### Tasks
- [ ] 
- [ ] 
- [ ] 

### Deadline
- 

### Notes
- 
""",
        tags=["todo", "action"],
        description="Action items related to a paper",
    ),
]


class TemplateManager:
    """Manages note templates."""

    def __init__(self):
        """Initialize with default templates."""
        self.templates: dict[str, NoteTemplate] = {}

        # Load default templates
        for template in DEFAULT_TEMPLATES:
            self.templates[template.name] = template

    def get_template(self, name: str) -> NoteTemplate:
        """Get template by name.

        Args:
            name: Template name

        Returns:
            Template

        Raises:
            TemplateNotFoundError: If template not found
        """
        if name not in self.templates:
            raise TemplateNotFoundError(name)

        return self.templates[name]

    def add_template(self, template: NoteTemplate) -> None:
        """Add a custom template.

        Args:
            template: Template to add

        Raises:
            TemplateValidationError: If template is invalid
        """
        if not template.is_valid():
            raise TemplateValidationError(
                "template",
                "Invalid template configuration",
            )

        self.templates[template.name] = template

    def remove_template(self, name: str) -> bool:
        """Remove a template.

        Args:
            name: Template name

        Returns:
            True if removed, False if not found
        """
        if name in self.templates:
            del self.templates[name]
            return True
        return False

    def list_templates(self) -> list[str]:
        """List available template names.

        Returns:
            List of template names
        """
        return sorted(self.templates.keys())

    def get_templates_for_type(self, note_type: NoteType) -> list[NoteTemplate]:
        """Get templates for a specific note type.

        Args:
            note_type: Type of note

        Returns:
            List of matching templates
        """
        return [t for t in self.templates.values() if t.type == note_type]

    def create_note_content(
        self,
        template_name: str,
        entry: Optional[Entry] = None,
        **variables: Any,
    ) -> tuple[str, str, NoteType, list[str]]:
        """Create note content from template.

        Args:
            template_name: Name of template to use
            entry: Optional bibliography entry
            **variables: Template variables

        Returns:
            Tuple of (title, content, type, tags)

        Raises:
            TemplateNotFoundError: If template not found
            KeyError: If required variable is missing
        """
        template = self.get_template(template_name)
        title, content = template.render(entry, **variables)

        return title, content, template.type, list(template.tags)
