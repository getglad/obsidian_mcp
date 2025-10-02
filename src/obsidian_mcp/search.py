"""Search functionality for Obsidian vaults."""

import logging
from dataclasses import dataclass
from typing import Literal

from .vault import ObsidianVault

SearchType = Literal["content", "title", "tags", "all"]

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SearchResult:
    """A search result with context (immutable)."""

    path: str
    name: str
    score: float
    snippet: str | None = None
    matched_tags: list[str] | None = None


class VaultSearch:
    """Search operations for Obsidian vaults."""

    def __init__(self, vault: ObsidianVault):
        """Initialize search with a vault."""
        self.vault = vault

    def _create_snippet(self, content: str, query: str, max_length: int = 200) -> str:
        """Create a snippet around the search query."""
        content_lower = content.lower()
        query_lower = query.lower()

        # Find first occurrence
        pos = content_lower.find(query_lower)
        if pos == -1:
            return content[:max_length] + "..." if len(content) > max_length else content

        # Calculate snippet bounds
        start = max(0, pos - max_length // 2)
        end = min(len(content), pos + len(query) + max_length // 2)

        snippet = content[start:end]

        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

    async def _search_in_content(
        self, query: str, limit: int, folder: str = ""
    ) -> list[SearchResult]:
        """Search for query in note content."""
        results: list[SearchResult] = []
        query_lower = query.lower()

        notes = self.vault.list_notes(folder=folder, recursive=True, limit=None)

        for note_meta in notes:
            if len(results) >= limit:
                break

            try:
                note = await self.vault.read_note(note_meta.path)
                content_lower = note.body.lower()

                # Check if query exists in content
                if query_lower in content_lower:
                    # Count occurrences for scoring
                    occurrences = content_lower.count(query_lower)
                    score = float(occurrences)

                    # Create snippet
                    snippet = self._create_snippet(
                        note.body, query, self.vault.config.snippet_length
                    )

                    results.append(
                        SearchResult(
                            path=note.path, name=note_meta.name, score=score, snippet=snippet
                        )
                    )
            except (OSError, UnicodeDecodeError) as e:
                logger.debug(f"Failed to read note {note_meta.path}: {e}")
                continue

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:limit]

    def _search_by_title(self, query: str, limit: int, folder: str = "") -> list[SearchResult]:
        """Search for query in note titles."""
        results: list[SearchResult] = []
        query_lower = query.lower()

        notes = self.vault.list_notes(folder=folder, recursive=True, limit=None)

        for note_meta in notes:
            if len(results) >= limit:
                break

            name_lower = note_meta.name.lower()

            if query_lower in name_lower:
                # Exact match scores higher
                if name_lower == query_lower:
                    score = 10.0
                elif name_lower.startswith(query_lower):
                    score = 5.0
                else:
                    score = 1.0

                results.append(SearchResult(path=note_meta.path, name=note_meta.name, score=score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _search_by_tags(self, query: str, limit: int, folder: str = "") -> list[SearchResult]:
        """Search for notes with matching tags."""
        results: list[SearchResult] = []
        query_lower = query.lower().lstrip("#")  # Remove # if present

        notes = self.vault.list_notes(folder=folder, recursive=True, limit=None, include_tags=True)

        for note_meta in notes:
            if len(results) >= limit:
                break

            matched = [tag for tag in note_meta.tags if query_lower in tag.lower()]

            if matched:
                # More matched tags = higher score
                score = float(len(matched))

                results.append(
                    SearchResult(
                        path=note_meta.path, name=note_meta.name, score=score, matched_tags=matched
                    )
                )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def search(
        self, query: str, search_type: SearchType = "all", folder: str = "", limit: int = 20
    ) -> list[SearchResult]:
        """
        Search the vault.

        Args:
            query: Search query string
            search_type: Type of search to perform
            folder: Limit search to this folder
            limit: Maximum number of results

        Returns:
            List of search results sorted by relevance
        """
        logger.debug(
            f"Searching for '{query}' (type={search_type}, folder={folder}, limit={limit})"
        )

        if not query:
            return []

        if search_type == "content":
            return await self._search_in_content(query, limit, folder)
        elif search_type == "title":
            return self._search_by_title(query, limit, folder)
        elif search_type == "tags":
            return self._search_by_tags(query, limit, folder)
        else:  # "all"
            # Combine results from all search types (each with full limit to ensure enough results)
            title_results = self._search_by_title(query, limit, folder)
            tag_results = self._search_by_tags(query, limit, folder)
            content_results = await self._search_in_content(query, limit, folder)

            # Merge and deduplicate by path
            seen_paths = set()
            all_results = []

            for result in title_results + tag_results + content_results:
                if result.path not in seen_paths:
                    seen_paths.add(result.path)
                    all_results.append(result)

            # Sort by score and return top results up to limit
            all_results.sort(key=lambda r: r.score, reverse=True)

            return all_results[:limit]

    async def search_by_property(
        self, property_name: str, property_value: str | None = None, limit: int = 50
    ) -> list[SearchResult]:
        """
        Search for notes by frontmatter property.

        Args:
            property_name: Name of the frontmatter property
            property_value: Optional value to match (if None, matches any note with the property)
            limit: Maximum number of results

        Returns:
            List of search results
        """
        results: list[SearchResult] = []
        notes = self.vault.list_notes(limit=None)

        for note_meta in notes:
            if len(results) >= limit:
                break

            try:
                note = await self.vault.read_note(note_meta.path)

                if not note.frontmatter:
                    continue

                # Check if property exists
                if property_name not in note.frontmatter:
                    continue

                prop_val = note.frontmatter[property_name]

                # If no value specified, just match presence
                if property_value is None:
                    score = 1.0
                else:
                    # Check if value matches
                    if isinstance(prop_val, list):
                        # Check if value is in list
                        if property_value in prop_val or property_value in str(prop_val):
                            score = 2.0
                        else:
                            continue
                    elif str(prop_val).lower() == property_value.lower():
                        score = 5.0  # Exact match
                    elif property_value.lower() in str(prop_val).lower():
                        score = 2.0  # Partial match
                    else:
                        continue

                # Create snippet from frontmatter
                snippet = f"{property_name}: {prop_val}"

                results.append(
                    SearchResult(
                        path=note_meta.path, name=note_meta.name, score=score, snippet=snippet
                    )
                )

            except (OSError, UnicodeDecodeError) as e:
                logger.debug(f"Failed to read note {note_meta.path}: {e}")
                continue

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
