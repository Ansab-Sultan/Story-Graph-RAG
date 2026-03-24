"""Prompt helpers for ingestion workflow."""

from __future__ import annotations


def build_deduplication_prompt(entity_names: list[str]) -> str:
    return (
        "These names were extracted from a story.\n"
        "Group any names that refer to the same character or entity.\n"
        "Pick the most complete or formal name as the canonical name.\n\n"
        f"Names: {entity_names}"
    )

