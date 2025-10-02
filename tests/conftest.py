"""Pytest configuration and fixtures for obsidian-mcp tests."""

from pathlib import Path

import pytest

from obsidian_mcp.config import ObsidianConfig
from obsidian_mcp.vault import ObsidianVault


@pytest.fixture
def test_vault_path(tmp_path: Path) -> Path:
    """Create a temporary test vault directory."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture
def test_config(test_vault_path: Path) -> ObsidianConfig:
    """Create test configuration."""
    return ObsidianConfig(vault_path=test_vault_path)


@pytest.fixture
def test_vault(test_config: ObsidianConfig) -> ObsidianVault:
    """Create test vault instance."""
    return ObsidianVault(test_config)


@pytest.fixture
def sample_notes(test_vault_path: Path) -> dict[str, Path]:
    """
    Create sample notes in the test vault.

    Returns:
        Dictionary mapping note names to their paths
    """
    notes = {}

    # Simple note without frontmatter
    simple_note = test_vault_path / "simple.md"
    simple_note.write_text("# Simple Note\n\nThis is a simple note without frontmatter.")
    notes["simple"] = simple_note

    # Note with frontmatter
    note_with_fm = test_vault_path / "with_frontmatter.md"
    note_with_fm.write_text(
        """---
title: Note with Frontmatter
tags: [test, example]
created: 2025-01-01
---

# Note with Frontmatter

This note has YAML frontmatter.
"""
    )
    notes["with_frontmatter"] = note_with_fm

    # Note with inline tags
    tagged_note = test_vault_path / "tagged.md"
    tagged_note.write_text(
        """# Tagged Note

This note has #inline-tags and #multiple #tags in the content.
"""
    )
    notes["tagged"] = tagged_note

    # Note in subfolder
    subfolder = test_vault_path / "projects"
    subfolder.mkdir()
    project_note = subfolder / "mcp-project.md"
    project_note.write_text(
        """---
tags: [mcp, project]
---

# MCP Project

Working on the Model Context Protocol integration.
"""
    )
    notes["mcp_project"] = project_note

    # Another note in subfolder
    another_note = subfolder / "another.md"
    another_note.write_text("# Another Note\n\nJust another note in the projects folder.")
    notes["another"] = another_note

    return notes


@pytest.fixture
def empty_vault(test_vault_path: Path, test_config: ObsidianConfig) -> ObsidianVault:
    """Create an empty test vault."""
    return ObsidianVault(test_config)
