"""Tests for vault operations."""

from pathlib import Path

import pytest

from obsidian_mcp.vault import ObsidianVault, VaultSecurityError


async def test_read_simple_note(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test reading a simple note without frontmatter."""
    note = await test_vault.read_note("simple.md")
    assert note.path == "simple.md"
    assert "Simple Note" in note.content
    assert note.frontmatter is None
    assert "simple note without frontmatter" in note.body


async def test_read_note_with_frontmatter(
    test_vault: ObsidianVault, sample_notes: dict[str, Path]
) -> None:
    """Test reading a note with frontmatter."""
    note = await test_vault.read_note("with_frontmatter.md")
    assert note.path == "with_frontmatter.md"
    assert note.frontmatter is not None
    assert note.frontmatter["title"] == "Note with Frontmatter"
    assert "test" in note.frontmatter["tags"]
    # Body should not start with "---" (frontmatter delimiter)
    assert not note.body.startswith("---")
    # Body should contain the actual content
    assert "This note has YAML frontmatter" in note.body


async def test_read_note_in_subfolder(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test reading a note in a subfolder."""
    note = await test_vault.read_note("projects/mcp-project.md")
    assert note.path == "projects/mcp-project.md"
    assert "MCP Project" in note.content


async def test_read_nonexistent_note(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test that reading nonexistent note raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await test_vault.read_note("nonexistent.md")


async def test_path_traversal_protection(
    test_vault: ObsidianVault, sample_notes: dict[str, Path]
) -> None:
    """Test that path traversal attempts are blocked."""
    with pytest.raises(VaultSecurityError):
        await test_vault.read_note("../../../etc/passwd")

    with pytest.raises(VaultSecurityError):
        await test_vault.read_note("..")


async def test_absolute_path_rejected(test_vault: ObsidianVault) -> None:
    """Test that absolute paths are rejected."""
    with pytest.raises(VaultSecurityError, match="Absolute paths not allowed"):
        await test_vault.read_note("/etc/passwd")


async def test_null_byte_rejected(test_vault: ObsidianVault) -> None:
    """Test that null bytes in paths are rejected."""
    with pytest.raises(VaultSecurityError, match="null byte"):
        await test_vault.read_note("test\x00.md")


def test_list_notes_root(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test listing all notes in vault."""
    notes = test_vault.list_notes()
    assert len(notes) == 5
    note_names = {note.name for note in notes}
    assert "simple" in note_names
    assert "with_frontmatter" in note_names
    assert "mcp-project" in note_names


def test_list_notes_in_folder(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test listing notes in a specific folder."""
    notes = test_vault.list_notes(folder="projects", recursive=False)
    assert len(notes) == 2
    note_names = {note.name for note in notes}
    assert "mcp-project" in note_names
    assert "another" in note_names


def test_list_notes_with_limit(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test listing notes with a limit."""
    notes = test_vault.list_notes(limit=2)
    assert len(notes) == 2


def test_list_notes_empty_vault(empty_vault: ObsidianVault) -> None:
    """Test listing notes in an empty vault."""
    notes = empty_vault.list_notes()
    assert len(notes) == 0


def test_list_notes_with_tags(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test listing notes with tag extraction."""
    notes = test_vault.list_notes(include_tags=True)

    # Find the tagged note
    tagged_note = next(note for note in notes if note.name == "tagged")
    assert len(tagged_note.tags) > 0
    assert "inline-tags" in tagged_note.tags


def test_note_exists(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test checking if note exists."""
    assert test_vault.note_exists("simple.md")
    assert test_vault.note_exists("projects/mcp-project.md")
    assert not test_vault.note_exists("nonexistent.md")


async def test_note_immutable(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test that Note objects are immutable."""
    note = await test_vault.read_note("simple.md")
    with pytest.raises(AttributeError):
        note.path = "changed.md"  # type: ignore
