"""Tests for search functionality."""

from pathlib import Path

import pytest

from obsidian_mcp.search import VaultSearch
from obsidian_mcp.vault import ObsidianVault


async def test_search_by_content(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test searching notes by content."""
    search = VaultSearch(test_vault)
    results = await search.search(query="frontmatter", search_type="content")

    assert len(results) > 0
    # Should find the note with "frontmatter" in content
    assert any("with_frontmatter" in result.name for result in results)
    # Results should have snippets
    assert any(result.snippet is not None for result in results)


async def test_search_by_title(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test searching notes by title."""
    search = VaultSearch(test_vault)
    results = await search.search(query="MCP", search_type="title")

    assert len(results) > 0
    assert any("mcp-project" in result.name for result in results)


async def test_search_by_tags(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test searching notes by tags."""
    search = VaultSearch(test_vault)
    results = await search.search(query="inline-tags", search_type="tags")

    assert len(results) > 0
    # Should find the tagged note
    assert any("tagged" in result.name for result in results)
    # Should have matched_tags
    assert any(result.matched_tags is not None for result in results)


async def test_search_all_types(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test searching across all types."""
    search = VaultSearch(test_vault)
    results = await search.search(query="Note", search_type="all")

    # Should find notes matching in title, content, or tags
    assert len(results) >= 3


async def test_search_with_limit(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test search with result limit."""
    search = VaultSearch(test_vault)
    results = await search.search(query="note", search_type="all", limit=2)

    assert len(results) <= 2


async def test_search_in_folder(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test searching within a specific folder."""
    search = VaultSearch(test_vault)
    results = await search.search(query="note", search_type="all", folder="projects")

    # Should only find notes in projects folder
    assert all("projects" in result.path for result in results)


async def test_search_empty_query(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test that empty query returns no results."""
    search = VaultSearch(test_vault)
    results = await search.search(query="", search_type="all")

    assert len(results) == 0


async def test_search_no_results(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test search that finds nothing."""
    search = VaultSearch(test_vault)
    results = await search.search(query="nonexistent_query_xyz", search_type="all")

    assert len(results) == 0


async def test_search_scoring(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test that search results are scored and sorted."""
    search = VaultSearch(test_vault)
    results = await search.search(query="Note", search_type="content")

    if len(results) > 1:
        # Scores should be in descending order
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score


async def test_search_result_immutable(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test that SearchResult objects are immutable."""
    search = VaultSearch(test_vault)
    results = await search.search(query="Note", search_type="all")

    if results:
        with pytest.raises(AttributeError):
            results[0].score = 100.0  # type: ignore


async def test_snippet_creation(test_vault: ObsidianVault, sample_notes: dict[str, Path]) -> None:
    """Test that snippets are created around search query."""
    search = VaultSearch(test_vault)
    results = await search.search(query="Model Context Protocol", search_type="content")

    # Find result with snippet
    result_with_snippet = next((r for r in results if r.snippet), None)
    if result_with_snippet:
        # Snippet should contain the query
        assert (
            "Model Context Protocol" in result_with_snippet.snippet
            or "model context protocol" in result_with_snippet.snippet.lower()
        )
