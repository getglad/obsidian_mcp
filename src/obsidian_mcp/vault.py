"""Vault operations for reading and managing Obsidian notes."""

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import aiofiles
import yaml

from .config import ObsidianConfig

# Module-level compiled regex patterns
TAG_PATTERN = re.compile(r"#([\w/-]+)")
# Matches [[note]] or [[note|alias]] or [[note#heading]]
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")

logger = logging.getLogger(__name__)


class VaultSecurityError(Exception):
    """Raised when a vault operation violates security constraints."""

    pass


@dataclass(slots=True, frozen=True)
class Note:
    """Represents an Obsidian note (immutable)."""

    path: str
    content: str
    frontmatter: dict[str, Any] | None = None

    @property
    def body(self) -> str:
        """Get note content without frontmatter."""
        if self.frontmatter is None:
            return self.content

        # Find end of frontmatter block
        if self.content.startswith("---\n"):
            parts = self.content.split("---\n", 2)
            if len(parts) >= 3:
                return parts[2]
        return self.content


@dataclass(slots=True, frozen=True)
class NoteMetadata:
    """Metadata about a note without full content (immutable)."""

    path: str
    name: str
    extension: str
    size: int
    modified: float
    tags: list[str]


class ObsidianVault:
    """Interface for accessing an Obsidian vault."""

    def __init__(self, config: ObsidianConfig):
        """Initialize vault with configuration."""
        self.config = config
        self.vault_path = config.vault_path
        logger.info(f"Initialized vault at {self.vault_path}")

    def _validate_path(self, relative_path: str) -> Path:
        """
        Validate and resolve a relative path within the vault.

        Raises VaultSecurityError if path tries to escape vault.
        """
        # Security: Check for null bytes
        if "\x00" in relative_path:
            raise VaultSecurityError("Path contains null byte")

        # Security: Reject absolute paths
        if Path(relative_path).is_absolute():
            raise VaultSecurityError(f"Absolute paths not allowed: {relative_path}")

        # Normalize the path
        requested_path = (self.vault_path / relative_path).resolve()

        # Ensure it's within vault (protects against ../ traversal)
        try:
            requested_path.relative_to(self.vault_path)
        except ValueError as e:
            raise VaultSecurityError(
                f"Path '{relative_path}' attempts to access files outside vault"
            ) from e

        return requested_path

    def _is_excluded(self, path: Path) -> bool:
        """Check if a path should be excluded."""
        parts = path.relative_to(self.vault_path).parts
        for excluded in self.config.exclude_folders:
            if excluded in parts:
                return True
        return False

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any] | None, str]:
        """
        Parse YAML frontmatter from note content.

        Returns (frontmatter_dict, full_content).
        """
        if not content.startswith("---\n"):
            return None, content

        parts = content.split("---\n", 2)
        if len(parts) < 3:
            return None, content

        try:
            frontmatter = yaml.safe_load(parts[1])
            return frontmatter, content
        except yaml.YAMLError as e:
            logger.debug(f"Failed to parse frontmatter: {e}")
            return None, content

    def _extract_tags(self, content: str, frontmatter: dict[str, Any] | None = None) -> list[str]:
        """Extract tags from frontmatter and content."""
        tags = set()

        # Get tags from frontmatter
        if frontmatter:
            fm_tags = frontmatter.get("tags", [])
            if isinstance(fm_tags, list):
                tags.update(fm_tags)
            elif isinstance(fm_tags, str):
                tags.add(fm_tags)

        # Get inline tags from content (e.g., #tag)
        inline_tags = TAG_PATTERN.findall(content)
        tags.update(inline_tags)

        return sorted(list(tags))

    async def read_note(self, relative_path: str) -> Note:
        """
        Read a note from the vault.

        Args:
            relative_path: Path relative to vault root

        Returns:
            Note object with content and metadata

        Raises:
            VaultSecurityError: If path is invalid
            FileNotFoundError: If note doesn't exist
        """
        file_path = self._validate_path(relative_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Note not found: {relative_path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {relative_path}")

        async with aiofiles.open(file_path, encoding="utf-8") as f:
            content = await f.read()
        frontmatter, content = self._parse_frontmatter(content)

        return Note(path=relative_path, content=content, frontmatter=frontmatter)

    def list_notes(
        self,
        folder: str = "",
        recursive: bool = True,
        limit: int | None = None,
        include_tags: bool = False,
    ) -> list[NoteMetadata]:
        """
        List notes in the vault.

        Args:
            folder: Subfolder to list (empty for root)
            recursive: Include subfolders
            limit: Maximum number of results
            include_tags: Whether to extract tags (slower)

        Returns:
            List of note metadata
        """
        start_path = self.vault_path
        if folder:
            start_path = self._validate_path(folder)

        notes: list[NoteMetadata] = []
        count = 0
        max_count = limit or self.config.max_results

        pattern = "**/*" if recursive else "*"

        for file_path in start_path.glob(pattern):
            if count >= max_count:
                break

            if not file_path.is_file():
                continue

            if self._is_excluded(file_path):
                continue

            if file_path.suffix not in self.config.file_extensions:
                continue

            relative_path = str(file_path.relative_to(self.vault_path))
            stats = file_path.stat()

            # Read file to extract tags (only if requested)
            if include_tags:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    frontmatter, _ = self._parse_frontmatter(content)
                    tags = self._extract_tags(content, frontmatter)
                except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
                    logger.debug(f"Failed to extract tags from {file_path}: {e}")
                    tags = []
            else:
                tags = []

            notes.append(
                NoteMetadata(
                    path=relative_path,
                    name=file_path.stem,
                    extension=file_path.suffix,
                    size=stats.st_size,
                    modified=stats.st_mtime,
                    tags=tags,
                )
            )
            count += 1

        # Sort by modification time (newest first)
        notes.sort(key=lambda n: n.modified, reverse=True)

        return notes

    def _extract_links(self, content: str) -> list[str]:
        """
        Extract wikilinks from note content.

        Returns list of link destinations (without .md extension).
        """
        links = WIKILINK_PATTERN.findall(content)
        # Normalize links (remove .md if present)
        return [link.replace(".md", "") for link in links]

    async def get_outgoing_links(self, relative_path: str) -> list[str]:
        """
        Get all outgoing links from a note.

        Args:
            relative_path: Path to the note

        Returns:
            List of linked note paths (relative to vault)
        """
        note = await self.read_note(relative_path)
        links = self._extract_links(note.content)

        # Resolve links to actual file paths
        resolved = []
        for link in links:
            # Try to find the note in the vault
            resolved_path = self._resolve_link(link, relative_path)
            if resolved_path:
                resolved.append(resolved_path)

        return resolved

    def _resolve_link(self, link: str, source_path: str) -> str | None:
        """
        Resolve a wikilink to an actual file path.

        Args:
            link: Link destination (e.g., "My Note" or "folder/My Note")
            source_path: Path of the source note (for relative links)

        Returns:
            Resolved path or None if not found
        """
        # If link already has extension, use as-is
        if link.endswith(".md"):
            link_path = link
        else:
            link_path = f"{link}.md"

        # Try direct path first
        try:
            if self.note_exists(link_path):
                return link_path
        except VaultSecurityError:
            pass

        # Try in same folder as source
        source_dir = str(Path(source_path).parent)
        if source_dir != ".":
            try:
                same_folder_path = f"{source_dir}/{link_path}"
                if self.note_exists(same_folder_path):
                    return same_folder_path
            except VaultSecurityError:
                pass

        # Search for file by name in entire vault
        for note_meta in self.list_notes(limit=10000):
            if note_meta.name == link or note_meta.path == link_path:
                return note_meta.path

        return None

    async def get_backlinks(self, relative_path: str, limit: int | None = None) -> list[str]:
        """
        Get all notes that link to this note.

        Warning: This method scans all notes in the vault (O(n) behavior) which can be slow
        for large vaults. Consider using the 'limit' parameter to cap the number of notes
        scanned, or wait for future versions with persistent link indexing for better performance.

        Args:
            relative_path: Path to the target note
            limit: Optional maximum number of notes to scan. If None, scans all notes but
                   logs a warning for large vaults (>1000 notes).

        Returns:
            List of note paths that link to this note

        Future: A persistent link index will be added to eliminate the O(n) scan overhead.
        """
        target_name = Path(relative_path).stem
        backlinks = []

        # Get list of notes to scan
        all_notes = list(self.list_notes(limit=10000))
        notes_to_scan = all_notes if limit is None else all_notes[:limit]

        # Warn if scanning large vault without limit
        if limit is None and len(all_notes) > 1000:
            logger.warning(
                f"get_backlinks scanning {len(all_notes)} notes without limit. "
                f"Consider using limit parameter for better performance on large vaults."
            )

        # Search through notes
        scanned = 0
        for note_meta in notes_to_scan:
            try:
                note = await self.read_note(note_meta.path)
                links = self._extract_links(note.content)

                # Check if any link resolves to target
                for link in links:
                    # Match by filename or full path
                    if link == target_name or link == relative_path.replace(".md", ""):
                        backlinks.append(note_meta.path)
                        break

                scanned += 1
                if limit and scanned >= limit:
                    break
            except Exception as e:
                logger.debug(f"Error checking backlinks in {note_meta.path}: {e}")
                continue

        return backlinks

    def get_all_tags(self) -> dict[str, int]:
        """
        Get all tags in the vault with their usage counts.

        Returns:
            Dict mapping tag names to usage counts
        """
        tag_counts: dict[str, int] = {}

        for note_meta in self.list_notes(limit=10000, include_tags=True):
            for tag in note_meta.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True))

    def get_notes_by_tag(self, tag: str, limit: int | None = None) -> list[NoteMetadata]:
        """
        Get all notes with a specific tag.

        Args:
            tag: Tag to search for (with or without #)
            limit: Maximum number of results

        Returns:
            List of note metadata
        """
        # Normalize tag (remove # if present)
        tag = tag.lstrip("#")
        matching_notes: list[NoteMetadata] = []
        max_count = limit or self.config.max_results

        for note_meta in self.list_notes(limit=10000, include_tags=True):
            if len(matching_notes) >= max_count:
                break
            if tag in note_meta.tags:
                matching_notes.append(note_meta)

        return matching_notes

    async def get_orphaned_notes(self) -> list[str]:
        """
        Get notes with no incoming or outgoing links.

        Returns:
            List of orphaned note paths
        """
        orphans = []

        for note_meta in self.list_notes(limit=10000):
            try:
                # Check outgoing links
                note = await self.read_note(note_meta.path)
                outgoing = self._extract_links(note.content)

                # Check backlinks (simplified - just check if mentioned anywhere)
                backlinks = await self.get_backlinks(note_meta.path)

                if not outgoing and not backlinks:
                    orphans.append(note_meta.path)
            except Exception as e:
                logger.debug(f"Error checking orphan status for {note_meta.path}: {e}")
                continue

        return orphans

    def get_vault_stats(self) -> dict[str, Any]:
        """
        Get statistics about the vault.

        Returns:
            Dict with vault statistics
        """
        notes = self.list_notes(limit=100000, include_tags=True)
        tags = self.get_all_tags()

        total_size = sum(note.size for note in notes)

        return {
            "total_notes": len(notes),
            "total_tags": len(tags),
            "total_size_bytes": total_size,
            "unique_tags": sorted(tags.keys()),
        }

    def note_exists(self, relative_path: str) -> bool:
        """Check if a note exists."""
        try:
            file_path = self._validate_path(relative_path)
            return file_path.exists() and file_path.is_file()
        except VaultSecurityError:
            return False

    def create_note(
        self,
        relative_path: str,
        content: str,
        frontmatter: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> None:
        """
        Create a new note in the vault.

        Args:
            relative_path: Path where to create the note
            content: Content of the note
            frontmatter: Optional frontmatter dict
            overwrite: If True, overwrite existing file

        Raises:
            VaultSecurityError: If path is invalid
            FileExistsError: If note already exists and overwrite=False
        """
        file_path = self._validate_path(relative_path)

        # Check if already exists
        if file_path.exists() and not overwrite:
            raise FileExistsError(f"Note already exists: {relative_path}")

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Build full content with frontmatter
        full_content = ""
        if frontmatter:
            full_content = "---\n"
            full_content += yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
            full_content += "---\n"

        full_content += content

        # Write file
        file_path.write_text(full_content, encoding="utf-8")
        logger.info(f"Created note: {relative_path}")

    async def update_note(
        self, relative_path: str, content: str, frontmatter: dict[str, Any] | None = None
    ) -> None:
        """
        Update an existing note's content.

        Args:
            relative_path: Path to the note
            content: New content for the note
            frontmatter: Optional frontmatter dict (replaces existing if provided)

        Raises:
            VaultSecurityError: If path is invalid
            FileNotFoundError: If note doesn't exist
        """
        file_path = self._validate_path(relative_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Note not found: {relative_path}")

        # If frontmatter not provided, preserve existing
        if frontmatter is None:
            note = await self.read_note(relative_path)
            frontmatter = note.frontmatter

        # Build full content
        full_content = ""
        if frontmatter:
            full_content = "---\n"
            full_content += yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
            full_content += "---\n"

        full_content += content

        # Write file
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(full_content)
        logger.info(f"Updated note: {relative_path}")

    async def append_to_note(self, relative_path: str, content: str) -> None:
        """
        Append content to an existing note.

        Args:
            relative_path: Path to the note
            content: Content to append

        Raises:
            VaultSecurityError: If path is invalid
            FileNotFoundError: If note doesn't exist
        """
        file_path = self._validate_path(relative_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Note not found: {relative_path}")

        # Read existing content
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            existing = await f.read()

        # Append new content (with newline separator if needed)
        if not existing.endswith("\n"):
            existing += "\n"

        existing += content

        # Write back
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(existing)
        logger.info(f"Appended to note: {relative_path}")

    def delete_note(self, relative_path: str, use_trash: bool = True) -> None:
        """
        Delete a note from the vault.

        Args:
            relative_path: Path to the note
            use_trash: If True, move to .trash folder instead of permanent delete

        Raises:
            VaultSecurityError: If path is invalid
            FileNotFoundError: If note doesn't exist
        """
        file_path = self._validate_path(relative_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Note not found: {relative_path}")

        if use_trash:
            # Move to .trash folder at vault root
            trash_dir = self.vault_path / ".trash"
            trash_dir.mkdir(exist_ok=True)

            # Create unique name if needed
            trash_path = trash_dir / file_path.name
            counter = 1
            while trash_path.exists():
                name_parts = file_path.stem, counter, file_path.suffix
                trash_path = trash_dir / f"{name_parts[0]}.{name_parts[1]}{name_parts[2]}"
                counter += 1

            # Move file
            file_path.rename(trash_path)
            logger.info(f"Moved to trash: {relative_path} -> {trash_path.name}")
        else:
            # Permanent delete
            file_path.unlink()
            logger.info(f"Deleted note: {relative_path}")

    async def update_frontmatter(self, relative_path: str, updates: dict[str, Any]) -> None:
        """
        Update frontmatter fields in a note.

        Args:
            relative_path: Path to the note
            updates: Dict of frontmatter fields to update/add

        Raises:
            VaultSecurityError: If path is invalid
            FileNotFoundError: If note doesn't exist
        """
        note = await self.read_note(relative_path)

        # Merge frontmatter
        frontmatter = note.frontmatter or {}
        frontmatter.update(updates)

        # Update note with merged frontmatter
        await self.update_note(relative_path, note.body, frontmatter)

    def get_daily_note_path(
        self, target_date: date | None = None, folder: str = "Daily Notes"
    ) -> str:
        """
        Get the path for a daily note.

        Args:
            target_date: Date for the daily note (defaults to today)
            folder: Folder where daily notes are stored

        Returns:
            Relative path to the daily note
        """
        if target_date is None:
            target_date = date.today()

        # Format: YYYY-MM-DD.md
        filename = f"{target_date.strftime('%Y-%m-%d')}.md"

        if folder:
            return f"{folder}/{filename}"
        return filename

    async def get_daily_note(
        self,
        target_date: date | None = None,
        folder: str = "Daily Notes",
        create_if_missing: bool = True,
    ) -> Note:
        """
        Get or create a daily note.

        Args:
            target_date: Date for the daily note (defaults to today)
            folder: Folder where daily notes are stored
            create_if_missing: If True, create the note if it doesn't exist

        Returns:
            Daily note
        """
        if target_date is None:
            target_date = date.today()

        note_path = self.get_daily_note_path(target_date, folder)

        # Try to read existing note
        try:
            return await self.read_note(note_path)
        except FileNotFoundError:
            if not create_if_missing:
                raise

            # Create new daily note
            frontmatter = {
                "date": target_date.strftime("%Y-%m-%d"),
                "tags": ["daily-note"],
            }

            content = f"# {target_date.strftime('%A, %B %d, %Y')}\n\n"

            self.create_note(note_path, content, frontmatter)
            return await self.read_note(note_path)

    def list_daily_notes(
        self, folder: str = "Daily Notes", limit: int = 30, days_back: int = 90
    ) -> list[NoteMetadata]:
        """
        List recent daily notes.

        Args:
            folder: Folder where daily notes are stored
            limit: Maximum number of notes to return
            days_back: How many days back to search

        Returns:
            List of daily notes sorted by date (newest first)
        """
        notes = self.list_notes(folder=folder, recursive=False, limit=None)

        # Filter to date-formatted notes (YYYY-MM-DD.md)
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
        daily_notes = []

        cutoff_date = date.today() - timedelta(days=days_back)

        for note in notes:
            filename = Path(note.path).name

            if date_pattern.match(filename):
                # Parse date from filename
                try:
                    note_date = datetime.strptime(filename[:-3], "%Y-%m-%d").date()
                    if note_date >= cutoff_date:
                        daily_notes.append(note)
                except ValueError:
                    continue

        # Sort by modification time (newest first)
        daily_notes.sort(key=lambda n: n.modified, reverse=True)

        return daily_notes[:limit]

    def list_templates(self, folder: str = "Templates") -> list[NoteMetadata]:
        """
        List available templates.

        Args:
            folder: Folder where templates are stored

        Returns:
            List of template notes
        """
        try:
            return self.list_notes(folder=folder, recursive=True, limit=None)
        except FileNotFoundError:
            return []

    async def create_from_template(
        self,
        template_path: str,
        new_note_path: str,
        replacements: dict[str, str] | None = None,
    ) -> None:
        """
        Create a new note from a template.

        Args:
            template_path: Path to the template note
            new_note_path: Path for the new note
            replacements: Dict of placeholder -> value replacements

        Raises:
            FileNotFoundError: If template doesn't exist
        """
        # Read template
        template = await self.read_note(template_path)

        content = template.content
        frontmatter = template.frontmatter.copy() if template.frontmatter else None

        # Apply replacements
        if replacements:
            for placeholder, value in replacements.items():
                content = content.replace(f"{{{{{placeholder}}}}}", value)

                # Also replace in frontmatter values
                if frontmatter:
                    for key, fm_value in frontmatter.items():
                        if isinstance(fm_value, str):
                            frontmatter[key] = fm_value.replace(f"{{{{{placeholder}}}}}", value)

        # Create new note
        self.create_note(new_note_path, content, frontmatter)

    async def get_link_graph(self, max_notes: int = 1000) -> dict[str, Any]:
        """
        Build a link graph for the vault.

        Returns:
            Dict with 'nodes' and 'edges' for visualization
        """
        nodes = []
        edges = []
        seen_paths = set()

        for note_meta in self.list_notes(limit=max_notes):
            # Add node
            if note_meta.path not in seen_paths:
                nodes.append(
                    {
                        "id": note_meta.path,
                        "name": note_meta.name,
                        "size": note_meta.size,
                        "tags": note_meta.tags if note_meta.tags else [],
                    }
                )
                seen_paths.add(note_meta.path)

            # Add edges (links)
            try:
                note = await self.read_note(note_meta.path)
                links = self._extract_links(note.content)

                for link in links:
                    resolved = self._resolve_link(link, note_meta.path)
                    if resolved and resolved in seen_paths:
                        edges.append(
                            {
                                "source": note_meta.path,
                                "target": resolved,
                            }
                        )
            except Exception as e:
                logger.debug(f"Error building graph for {note_meta.path}: {e}")
                continue

        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    async def get_related_notes(
        self, relative_path: str, limit: int = 10
    ) -> list[tuple[str, float]]:
        """
        Find notes related to a given note.

        Uses shared links and tags to calculate similarity.

        Args:
            relative_path: Path to the note
            limit: Maximum number of related notes

        Returns:
            List of (note_path, similarity_score) tuples
        """
        target_note = await self.read_note(relative_path)

        # Get target note's links and tags
        target_links = set(self._extract_links(target_note.content))
        target_tags = set(self._extract_tags(target_note.content, target_note.frontmatter))

        related: list[tuple[str, float]] = []

        for note_meta in self.list_notes(limit=1000, include_tags=True):
            # Skip the target note itself
            if note_meta.path == relative_path:
                continue

            try:
                note = await self.read_note(note_meta.path)
                note_links = set(self._extract_links(note.content))
                note_tags = set(note_meta.tags)

                # Calculate similarity score
                score = 0.0

                # Shared links (high weight)
                shared_links = target_links & note_links
                score += len(shared_links) * 2.0

                # Shared tags (medium weight)
                shared_tags = target_tags & note_tags
                score += len(shared_tags) * 1.0

                # Check if notes link to each other (high weight)
                links_to_note = any(
                    self._resolve_link(link, relative_path) == note_meta.path
                    for link in target_links
                )
                if links_to_note:
                    score += 3.0

                note_links_back = any(
                    self._resolve_link(link, note_meta.path) == relative_path for link in note_links
                )
                if note_links_back:
                    score += 3.0

                if score > 0:
                    related.append((note_meta.path, score))

            except Exception as e:
                logger.debug(f"Error calculating similarity for {note_meta.path}: {e}")
                continue

        # Sort by score descending
        related.sort(key=lambda x: x[1], reverse=True)

        return related[:limit]

    # Batch Operations

    async def create_batch_backup(self, relative_paths: list[str]) -> str:
        """
        Create a backup of multiple notes asynchronously.

        Args:
            relative_paths: List of note paths to backup

        Returns:
            Backup ID (timestamp) for later restoration

        Raises:
            VaultSecurityError: If any path is invalid
            FileNotFoundError: If any note doesn't exist
        """
        # Validate all paths first
        file_paths = []
        for rel_path in relative_paths:
            file_path = self._validate_path(rel_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Note not found: {rel_path}")
            file_paths.append((rel_path, file_path))

        # Create backup directory with timestamp
        backup_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.vault_path / ".batch_backups" / backup_id
        backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating batch backup {backup_id}: {len(relative_paths)} files...")

        # Copy all files to backup asynchronously
        async def copy_file(i: int, rel_path: str, file_path: Path) -> None:
            backup_file = backup_dir / rel_path
            backup_file.parent.mkdir(parents=True, exist_ok=True)

            # Use async file operations
            async with aiofiles.open(file_path, "rb") as src:
                content = await src.read()
            async with aiofiles.open(backup_file, "wb") as dst:
                await dst.write(content)

            # Preserve metadata
            shutil.copystat(file_path, backup_file)
            logger.debug(f"Backed up ({i}/{len(file_paths)}): {rel_path}")

        # Run all copies concurrently
        await asyncio.gather(
            *[
                copy_file(i, rel_path, file_path)
                for i, (rel_path, file_path) in enumerate(file_paths, 1)
            ]
        )

        logger.info(f"Completed batch backup: {backup_id} ({len(relative_paths)} notes)")
        return backup_id

    async def restore_batch_backup(self, backup_id: str) -> list[str]:
        """
        Restore notes from a batch backup asynchronously.

        Args:
            backup_id: Backup ID (timestamp) to restore from

        Returns:
            List of restored note paths

        Raises:
            FileNotFoundError: If backup doesn't exist
        """
        backup_dir = self.vault_path / ".batch_backups" / backup_id

        if not backup_dir.exists():
            raise FileNotFoundError(f"Backup not found: {backup_id}")

        logger.info(f"Restoring batch backup {backup_id}...")

        # Get all backup files
        backup_files = list(backup_dir.rglob("*.md"))

        # Restore all files asynchronously
        async def restore_file(i: int, backup_file: Path) -> str:
            # Get relative path from backup directory
            rel_path = backup_file.relative_to(backup_dir)
            target_file = self.vault_path / rel_path

            # Ensure parent directory exists
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Restore file
            async with aiofiles.open(backup_file, "rb") as src:
                content = await src.read()
            async with aiofiles.open(target_file, "wb") as dst:
                await dst.write(content)

            # Preserve metadata
            shutil.copystat(backup_file, target_file)
            logger.debug(f"Restored ({i}): {rel_path}")
            return str(rel_path)

        # Run all restores concurrently
        restored = await asyncio.gather(
            *[restore_file(i, backup_file) for i, backup_file in enumerate(backup_files, 1)]
        )

        logger.info(f"Completed batch restore: {backup_id} ({len(restored)} notes)")
        return list(restored)

    def list_batch_backups(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        List available batch backups.

        Args:
            limit: Maximum number of backups to return

        Returns:
            List of backup info dicts
        """
        backups_root = self.vault_path / ".batch_backups"

        if not backups_root.exists():
            return []

        backups = []
        for backup_dir in sorted(backups_root.iterdir(), reverse=True)[:limit]:
            if backup_dir.is_dir():
                # Count notes in backup
                note_count = len(list(backup_dir.rglob("*.md")))

                # Parse timestamp from directory name
                try:
                    timestamp = datetime.strptime(backup_dir.name, "%Y%m%d_%H%M%S")
                    created = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    created = backup_dir.name

                backups.append(
                    {
                        "backup_id": backup_dir.name,
                        "created": created,
                        "note_count": note_count,
                        "size_bytes": sum(f.stat().st_size for f in backup_dir.rglob("*.md")),
                    }
                )

        return backups

    def cleanup_old_backups(self, days_old: int = 7) -> int:
        """
        Remove batch backups older than specified days.

        Args:
            days_old: Remove backups older than this many days

        Returns:
            Number of backups removed
        """
        backups_root = self.vault_path / ".batch_backups"

        if not backups_root.exists():
            return 0

        removed = 0
        cutoff_time = datetime.now() - timedelta(days=days_old)

        for backup_dir in backups_root.iterdir():
            if backup_dir.is_dir():
                try:
                    # Parse timestamp from directory name
                    backup_time = datetime.strptime(backup_dir.name, "%Y%m%d_%H%M%S")

                    if backup_time < cutoff_time:
                        shutil.rmtree(backup_dir)
                        removed += 1
                        logger.info(f"Removed old backup: {backup_dir.name}")
                except ValueError:
                    # Skip directories that don't match timestamp format
                    continue

        return removed
