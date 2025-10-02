"""MCP server for Obsidian vault access."""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .calendar import CalendarAuthError, CalendarError, CalendarService
from .config import ObsidianConfig
from .search import SearchType, VaultSearch
from .vault import ObsidianVault, VaultSecurityError

# Load environment variables from .env file
load_dotenv()

# Configure logging to stderr (required for STDIO-based MCP servers)
# Optional: also log to file for debugging (set OBSIDIAN_MCP_LOG_FILE env var)
log_handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
log_file = os.getenv("OBSIDIAN_MCP_LOG_FILE")
if log_file:
    log_handlers.append(logging.FileHandler(log_file))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)

if log_file:
    logger.info(f"Logging to file: {log_file}")

# Initialize MCP server
mcp = FastMCP(
    name="obsidian",
    instructions="""
This MCP server provides access to an Obsidian vault for reading, searching, and managing notes.

Use these tools to:
- Search for notes by content, title, or tags
- Read note contents
- List notes in the vault
- Access note metadata and relationships

All paths are relative to the vault root directory.
""".strip(),
)


class ServerContext:
    """Server context holding vault and search instances."""

    def __init__(self) -> None:
        config = ObsidianConfig.from_env()
        self.config = config
        self.vault = ObsidianVault(config)
        self.search = VaultSearch(self.vault)
        self._calendar: CalendarService | None = None
        logger.info(f"Initialized vault at: {config.vault_path}")

        if config.calendar_enabled:
            logger.info("Google Calendar integration enabled")

    def get_calendar(self) -> CalendarService:
        """
        Get or create calendar service.

        Returns:
            Calendar service

        Raises:
            CalendarAuthError: If calendar not configured or auth fails
        """
        if not self.config.calendar_enabled or not self.config.calendar_credentials_path:
            raise CalendarAuthError(
                "Google Calendar not configured. Set GOOGLE_CALENDAR_CREDENTIALS_PATH"
            )

        if self._calendar is None:
            self._calendar = CalendarService(
                str(self.config.calendar_credentials_path),
                self.config.calendar_id,
                headless=self.config.calendar_headless,
            )

        return self._calendar


# Module-level context (initialized lazily)
_context: ServerContext | None = None


# Pydantic models for batch operations


class NoteUpdate(BaseModel):
    """Schema for updating a single note."""

    path: str = Field(description="Relative path to the note (e.g., 'Projects/note.md')")
    content: str = Field(description="New content for the note")
    frontmatter: dict[str, Any] | None = Field(
        default=None, description="Optional frontmatter dict (replaces existing if provided)"
    )


class NoteAppend(BaseModel):
    """Schema for appending to a single note."""

    path: str = Field(description="Relative path to the note")
    content: str = Field(description="Content to append to the note")


def _get_context() -> ServerContext:
    """Get or create server context."""
    global _context
    if _context is None:
        _context = ServerContext()
    return _context


@mcp.tool(name="read_note", description="Read the full content of a note from the vault")
async def read_note(path: str) -> str:
    """
    Read a note from the vault.

    Args:
        path: Relative path to the note (e.g., "Projects/MCP.md")

    Returns:
        Note content as markdown text with frontmatter
    """
    # Validate input
    if not path or not path.strip():
        return "Error: Path cannot be empty"
    if len(path) > 1000:
        return "Error: Path too long"

    context = _get_context()

    try:
        note = await context.vault.read_note(path)

        # Format response with metadata
        result = f"# {note.path}\n\n"

        if note.frontmatter:
            result += "## Frontmatter\n```yaml\n"
            result += yaml.dump(note.frontmatter, default_flow_style=False)
            result += "```\n\n"

        result += "## Content\n"
        result += note.body

        return result

    except FileNotFoundError:
        return f"Error: Note not found: {path}"
    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception(f"Error reading note {path}")
        return f"Error reading note: {e}"


@mcp.tool(name="search_notes", description="Search the vault by content, title, tags, or all")
async def search_notes(
    query: str, search_type: SearchType = "all", folder: str = "", limit: int = 20
) -> str:
    """
    Search for notes in the vault.

    Args:
        query: Search query string
        search_type: Type of search - "content", "title", "tags", or "all"
        folder: Optional folder to limit search (e.g., "Projects")
        limit: Maximum number of results (default: 20)

    Returns:
        Formatted list of search results with snippets
    """
    # Validate input
    if not query or not query.strip():
        return "Error: Query cannot be empty"
    if len(query) > 500:
        return "Error: Query too long"
    if limit <= 0 or limit > 1000:
        return "Error: Limit must be between 1 and 1000"

    context = _get_context()

    try:
        results = await context.search.search(
            query=query, search_type=search_type, folder=folder, limit=limit
        )

        if not results:
            return f"No results found for query: {query}"

        # Format results
        output = f"Found {len(results)} results for '{query}':\n\n"

        for i, result in enumerate(results, 1):
            output += f"{i}. **{result.name}**\n"
            output += f"   Path: `{result.path}`\n"
            output += f"   Score: {result.score:.1f}\n"

            if result.snippet:
                output += f"   Snippet: {result.snippet}\n"

            if result.matched_tags:
                output += f"   Tags: {', '.join(result.matched_tags)}\n"

            output += "\n"

        return output

    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception("Error searching notes")
        return f"Error searching notes: {e}"


@mcp.tool(name="list_notes", description="List notes in the vault with optional filters")
def list_notes(folder: str = "", recursive: bool = True, limit: int = 100) -> str:
    """
    List notes in the vault.

    Args:
        folder: Folder to list (empty for root)
        recursive: Include subfolders (default: true)
        limit: Maximum number of results (default: 100)

    Returns:
        Formatted list of notes with metadata
    """
    # Validate input
    if limit <= 0 or limit > 10000:
        return "Error: Limit must be between 1 and 10000"

    context = _get_context()

    try:
        notes = context.vault.list_notes(folder=folder, recursive=recursive, limit=limit)

        if not notes:
            folder_desc = f" in '{folder}'" if folder else ""
            return f"No notes found{folder_desc}"

        # Format results
        folder_desc = f" in '{folder}'" if folder else ""
        output = f"Found {len(notes)} notes{folder_desc}:\n\n"

        for i, note in enumerate(notes, 1):
            output += f"{i}. **{note.name}**\n"
            output += f"   Path: `{note.path}`\n"
            output += f"   Size: {note.size} bytes\n"

            if note.tags:
                output += f"   Tags: {', '.join(note.tags)}\n"

            output += "\n"

        return output

    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception("Error listing notes")
        return f"Error listing notes: {e}"


@mcp.tool(
    name="get_backlinks",
    description="Get all notes that link to a specific note (incoming links)",
)
async def get_backlinks(path: str, limit: int | None = None) -> str:
    """
    Get all notes that link to this note.

    Args:
        path: Relative path to the note (e.g., "Projects/MCP.md")
        limit: Optional maximum number of notes to scan (recommended for large vaults)

    Returns:
        Formatted list of notes that link to this note
    """
    if not path or not path.strip():
        return "Error: Path cannot be empty"
    if len(path) > 1000:
        return "Error: Path too long"

    context = _get_context()

    try:
        backlinks = await context.vault.get_backlinks(path, limit=limit)

        if not backlinks:
            return f"No backlinks found for '{path}'"

        output = f"Found {len(backlinks)} note(s) linking to '{path}':\n\n"
        for i, link_path in enumerate(backlinks, 1):
            output += f"{i}. `{link_path}`\n"

        return output

    except FileNotFoundError:
        return f"Error: Note not found: {path}"
    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception(f"Error getting backlinks for {path}")
        return f"Error getting backlinks: {e}"


@mcp.tool(
    name="get_outgoing_links",
    description="Get all links from a note to other notes (outgoing links)",
)
async def get_outgoing_links(path: str) -> str:
    """
    Get all outgoing links from a note.

    Args:
        path: Relative path to the note (e.g., "Projects/MCP.md")

    Returns:
        Formatted list of linked notes
    """
    if not path or not path.strip():
        return "Error: Path cannot be empty"
    if len(path) > 1000:
        return "Error: Path too long"

    context = _get_context()

    try:
        outgoing = await context.vault.get_outgoing_links(path)

        if not outgoing:
            return f"No outgoing links found in '{path}'"

        output = f"Found {len(outgoing)} outgoing link(s) from '{path}':\n\n"
        for i, link_path in enumerate(outgoing, 1):
            output += f"{i}. `{link_path}`\n"

        return output

    except FileNotFoundError:
        return f"Error: Note not found: {path}"
    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception(f"Error getting outgoing links for {path}")
        return f"Error getting outgoing links: {e}"


@mcp.tool(name="list_all_tags", description="Get all tags in the vault with usage counts")
def list_all_tags(limit: int = 100) -> str:
    """
    List all tags in the vault with their usage counts.

    Args:
        limit: Maximum number of tags to return (default: 100)

    Returns:
        Formatted list of tags with counts
    """
    if limit <= 0 or limit > 10000:
        return "Error: Limit must be between 1 and 10000"

    context = _get_context()

    try:
        tags = context.vault.get_all_tags()

        if not tags:
            return "No tags found in vault"

        # Limit results
        tags_list = list(tags.items())[:limit]

        output = f"Found {len(tags)} unique tags (showing top {len(tags_list)}):\n\n"
        for tag, count in tags_list:
            output += f"- **#{tag}** ({count} note{'s' if count != 1 else ''})\n"

        return output

    except Exception as e:
        logger.exception("Error listing tags")
        return f"Error listing tags: {e}"


@mcp.tool(name="get_notes_by_tag", description="Find all notes with a specific tag")
def get_notes_by_tag(tag: str, limit: int = 50) -> str:
    """
    Get all notes with a specific tag.

    Args:
        tag: Tag to search for (with or without #)
        limit: Maximum number of results (default: 50)

    Returns:
        Formatted list of notes with this tag
    """
    if not tag or not tag.strip():
        return "Error: Tag cannot be empty"
    if limit <= 0 or limit > 1000:
        return "Error: Limit must be between 1 and 1000"

    context = _get_context()

    try:
        notes = context.vault.get_notes_by_tag(tag, limit=limit)

        if not notes:
            return f"No notes found with tag: {tag}"

        # Normalize tag for display
        tag_display = tag if tag.startswith("#") else f"#{tag}"

        output = f"Found {len(notes)} note(s) with tag '{tag_display}':\n\n"
        for i, note in enumerate(notes, 1):
            output += f"{i}. **{note.name}**\n"
            output += f"   Path: `{note.path}`\n"
            output += f"   Size: {note.size} bytes\n"
            if note.tags:
                output += f"   All tags: {', '.join(f'#{t}' for t in note.tags)}\n"
            output += "\n"

        return output

    except Exception as e:
        logger.exception(f"Error getting notes by tag: {tag}")
        return f"Error getting notes by tag: {e}"


@mcp.tool(name="get_vault_stats", description="Get statistics about the vault")
def get_vault_stats() -> str:
    """
    Get statistics about the vault.

    Returns:
        Formatted vault statistics
    """
    context = _get_context()

    try:
        stats = context.vault.get_vault_stats()

        output = "# Vault Statistics\n\n"
        output += f"**Total Notes:** {stats['total_notes']}\n"
        output += f"**Total Tags:** {stats['total_tags']}\n"
        output += f"**Total Size:** {stats['total_size_bytes']:,} bytes\n\n"

        if stats["unique_tags"]:
            output += "**Top Tags:**\n"
            for tag in stats["unique_tags"][:20]:
                output += f"- #{tag}\n"

        return output

    except Exception as e:
        logger.exception("Error getting vault stats")
        return f"Error getting vault stats: {e}"


@mcp.tool(
    name="get_orphaned_notes",
    description="Find notes with no incoming or outgoing links",
)
async def get_orphaned_notes(limit: int = 50) -> str:
    """
    Get notes with no incoming or outgoing links.

    Args:
        limit: Maximum number of results (default: 50)

    Returns:
        Formatted list of orphaned notes
    """
    if limit <= 0 or limit > 1000:
        return "Error: Limit must be between 1 and 1000"

    context = _get_context()

    try:
        orphans = await context.vault.get_orphaned_notes()

        if not orphans:
            return "No orphaned notes found (all notes are connected!)"

        # Limit results
        orphans = orphans[:limit]

        output = f"Found {len(orphans)} orphaned note(s) (showing first {len(orphans)}):\n\n"
        for i, path in enumerate(orphans, 1):
            output += f"{i}. `{path}`\n"

        return output

    except Exception as e:
        logger.exception("Error finding orphaned notes")
        return f"Error finding orphaned notes: {e}"


@mcp.tool(
    name="search_by_property",
    description="Search for notes by frontmatter property (metadata field)",
)
async def search_by_property(property_name: str, property_value: str = "", limit: int = 50) -> str:
    """
    Search for notes by frontmatter property.

    Args:
        property_name: Name of the frontmatter property to search
        property_value: Optional value to match (empty to find all notes with this property)
        limit: Maximum number of results (default: 50)

    Returns:
        Formatted list of notes matching the property
    """
    if not property_name or not property_name.strip():
        return "Error: Property name cannot be empty"
    if limit <= 0 or limit > 1000:
        return "Error: Limit must be between 1 and 1000"

    context = _get_context()

    try:
        # Convert empty string to None for "any value" search
        value = property_value if property_value else None
        results = await context.search.search_by_property(property_name, value, limit=limit)

        if not results:
            if value:
                return f"No notes found with property '{property_name}' = '{value}'"
            else:
                return f"No notes found with property '{property_name}'"

        # Format results
        if value:
            output = f"Found {len(results)} note(s) with '{property_name}' = '{value}':\n\n"
        else:
            output = f"Found {len(results)} note(s) with property '{property_name}':\n\n"

        for i, result in enumerate(results, 1):
            output += f"{i}. **{result.name}**\n"
            output += f"   Path: `{result.path}`\n"
            if result.snippet:
                output += f"   {result.snippet}\n"
            output += "\n"

        return output

    except Exception as e:
        logger.exception(f"Error searching by property: {property_name}")
        return f"Error searching by property: {e}"


@mcp.tool(name="create_note", description="Create a new note in the vault")
def create_note(
    path: str, content: str, tags: list[str] | None = None, overwrite: bool = False
) -> str:
    """
    Create a new note.

    Args:
        path: Relative path for the new note (e.g., "Projects/New Idea.md")
        content: Content of the note
        tags: Optional list of tags to add to frontmatter
        overwrite: If true, overwrite existing note

    Returns:
        Success message
    """
    if not path or not path.strip():
        return "Error: Path cannot be empty"
    if len(path) > 1000:
        return "Error: Path too long"
    if len(content) > 1_000_000:
        return "Error: Content too large (max 1MB)"

    context = _get_context()

    try:
        # Build frontmatter if tags provided
        frontmatter = None
        if tags:
            frontmatter = {"tags": tags}

        context.vault.create_note(path, content, frontmatter, overwrite)
        return f"✓ Created note: {path}"

    except FileExistsError:
        return f"Error: Note already exists: {path} (use overwrite=true to replace)"
    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception(f"Error creating note {path}")
        return f"Error creating note: {e}"


@mcp.tool(name="update_note", description="Update an existing note's content")
async def update_note(path: str, content: str) -> str:
    """
    Update an existing note's content (preserves frontmatter).

    Args:
        path: Relative path to the note
        content: New content for the note body

    Returns:
        Success message
    """
    if not path or not path.strip():
        return "Error: Path cannot be empty"
    if len(path) > 1000:
        return "Error: Path too long"
    if len(content) > 1_000_000:
        return "Error: Content too large (max 1MB)"

    context = _get_context()

    try:
        await context.vault.update_note(path, content)
        return f"✓ Updated note: {path}"

    except FileNotFoundError:
        return f"Error: Note not found: {path}"
    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception(f"Error updating note {path}")
        return f"Error updating note: {e}"


@mcp.tool(name="append_to_note", description="Append content to an existing note")
async def append_to_note(path: str, content: str) -> str:
    """
    Append content to the end of an existing note.

    Args:
        path: Relative path to the note
        content: Content to append

    Returns:
        Success message
    """
    if not path or not path.strip():
        return "Error: Path cannot be empty"
    if len(path) > 1000:
        return "Error: Path too long"
    if len(content) > 1_000_000:
        return "Error: Content too large (max 1MB)"

    context = _get_context()

    try:
        await context.vault.append_to_note(path, content)
        return f"✓ Appended to note: {path}"

    except FileNotFoundError:
        return f"Error: Note not found: {path}"
    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception(f"Error appending to note {path}")
        return f"Error appending to note: {e}"


@mcp.tool(name="delete_note", description="Delete a note (moves to .trash by default)")
def delete_note(path: str, permanent: bool = False) -> str:
    """
    Delete a note from the vault.

    Args:
        path: Relative path to the note
        permanent: If true, permanently delete; otherwise move to .trash folder

    Returns:
        Success message
    """
    if not path or not path.strip():
        return "Error: Path cannot be empty"
    if len(path) > 1000:
        return "Error: Path too long"

    context = _get_context()

    try:
        context.vault.delete_note(path, use_trash=not permanent)

        if permanent:
            return f"✓ Permanently deleted note: {path}"
        else:
            return f"✓ Moved note to trash: {path}"

    except FileNotFoundError:
        return f"Error: Note not found: {path}"
    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception(f"Error deleting note {path}")
        return f"Error deleting note: {e}"


@mcp.tool(
    name="update_frontmatter",
    description="Update frontmatter fields in a note (preserves content)",
)
async def update_frontmatter(path: str, property_name: str, property_value: str) -> str:
    """
    Update a frontmatter property in a note.

    Args:
        path: Relative path to the note
        property_name: Name of the frontmatter field
        property_value: Value to set (as string)

    Returns:
        Success message
    """
    if not path or not path.strip():
        return "Error: Path cannot be empty"
    if not property_name or not property_name.strip():
        return "Error: Property name cannot be empty"
    if len(path) > 1000:
        return "Error: Path too long"

    context = _get_context()

    try:
        # Simple string value for now
        # TODO: Could enhance to support lists/objects via JSON parsing
        updates = {property_name: property_value}
        await context.vault.update_frontmatter(path, updates)

        return f"✓ Updated frontmatter in {path}: {property_name} = {property_value}"

    except FileNotFoundError:
        return f"Error: Note not found: {path}"
    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception(f"Error updating frontmatter for {path}")
        return f"Error updating frontmatter: {e}"


@mcp.tool(name="get_daily_note", description="Get or create a daily note for a specific date")
async def get_daily_note(
    date_str: str = "", folder: str = "Daily Notes", create: bool = True
) -> str:
    """
    Get or create a daily note.

    Args:
        date_str: Date in YYYY-MM-DD format (empty for today)
        folder: Folder where daily notes are stored
        create: If true, create the note if it doesn't exist

    Returns:
        Daily note content
    """
    context = _get_context()

    try:
        # Parse date
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = None

        note = await context.vault.get_daily_note(target_date, folder, create)

        result = f"# Daily Note: {note.path}\n\n"
        if note.frontmatter:
            result += "## Frontmatter\n```yaml\n"
            result += yaml.dump(note.frontmatter, default_flow_style=False)
            result += "```\n\n"

        result += "## Content\n"
        result += note.body

        return result

    except ValueError as e:
        return f"Error: Invalid date format (use YYYY-MM-DD): {e}"
    except FileNotFoundError:
        return f"Error: Daily note not found for {date_str}"
    except Exception as e:
        logger.exception("Error getting daily note")
        return f"Error getting daily note: {e}"


@mcp.tool(name="list_daily_notes", description="List recent daily notes")
def list_daily_notes(folder: str = "Daily Notes", limit: int = 30) -> str:
    """
    List recent daily notes.

    Args:
        folder: Folder where daily notes are stored
        limit: Maximum number of notes (default: 30)

    Returns:
        Formatted list of daily notes
    """
    if limit <= 0 or limit > 365:
        return "Error: Limit must be between 1 and 365"

    context = _get_context()

    try:
        notes = context.vault.list_daily_notes(folder, limit)

        if not notes:
            return f"No daily notes found in '{folder}'"

        output = f"Found {len(notes)} daily note(s) in '{folder}':\n\n"
        for i, note in enumerate(notes, 1):
            output += f"{i}. **{note.name}**\n"
            output += f"   Path: `{note.path}`\n"
            output += f"   Size: {note.size} bytes\n\n"

        return output

    except Exception as e:
        logger.exception("Error listing daily notes")
        return f"Error listing daily notes: {e}"


@mcp.tool(name="list_templates", description="List available note templates")
def list_templates(folder: str = "Templates") -> str:
    """
    List available templates.

    Args:
        folder: Folder where templates are stored

    Returns:
        Formatted list of templates
    """
    context = _get_context()

    try:
        templates = context.vault.list_templates(folder)

        if not templates:
            return f"No templates found in '{folder}'"

        output = f"Found {len(templates)} template(s) in '{folder}':\n\n"
        for i, template in enumerate(templates, 1):
            output += f"{i}. **{template.name}**\n"
            output += f"   Path: `{template.path}`\n"
            output += f"   Size: {template.size} bytes\n\n"

        return output

    except Exception as e:
        logger.exception("Error listing templates")
        return f"Error listing templates: {e}"


@mcp.tool(name="create_from_template", description="Create a new note from a template")
async def create_from_template(template_path: str, new_note_path: str, title: str = "") -> str:
    """
    Create a note from a template.

    Args:
        template_path: Path to the template note
        new_note_path: Path for the new note
        title: Optional title to replace {{title}} placeholder

    Returns:
        Success message
    """
    if not template_path or not new_note_path:
        return "Error: Template path and new note path are required"

    context = _get_context()

    try:
        # Build replacements
        replacements = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        if title:
            replacements["title"] = title

        await context.vault.create_from_template(template_path, new_note_path, replacements)
        return f"✓ Created note from template: {new_note_path}"

    except FileNotFoundError:
        return f"Error: Template not found: {template_path}"
    except FileExistsError:
        return f"Error: Note already exists: {new_note_path}"
    except Exception as e:
        logger.exception("Error creating from template")
        return f"Error creating from template: {e}"


@mcp.tool(name="get_link_graph", description="Get the link graph for the vault")
async def get_link_graph(max_notes: int = 500) -> str:
    """
    Build a link graph of the vault.

    Args:
        max_notes: Maximum number of notes to include (default: 500)

    Returns:
        JSON representation of the graph with nodes and edges
    """
    if max_notes <= 0 or max_notes > 10000:
        return "Error: max_notes must be between 1 and 10000"

    context = _get_context()

    try:
        graph = await context.vault.get_link_graph(max_notes)

        output = "# Link Graph\n\n"
        output += f"**Total Nodes:** {graph['total_nodes']}\n"
        output += f"**Total Edges:** {graph['total_edges']}\n\n"

        output += "## Sample Nodes (first 10):\n"
        for node in graph["nodes"][:10]:
            output += f"- {node['name']} ({node['id']})\n"

        output += "\n## Sample Edges (first 10):\n"
        for edge in graph["edges"][:10]:
            output += f"- {edge['source']} → {edge['target']}\n"

        output += "\n\n**Full Graph Data (JSON):**\n```json\n"
        output += json.dumps(graph, indent=2)
        output += "\n```"

        return output

    except Exception as e:
        logger.exception("Error building link graph")
        return f"Error building link graph: {e}"


@mcp.tool(name="get_related_notes", description="Find notes related to a specific note")
async def get_related_notes(path: str, limit: int = 10) -> str:
    """
    Find notes related to a given note.

    Args:
        path: Relative path to the note
        limit: Maximum number of related notes (default: 10)

    Returns:
        Formatted list of related notes with similarity scores
    """
    if not path or not path.strip():
        return "Error: Path cannot be empty"
    if limit <= 0 or limit > 100:
        return "Error: Limit must be between 1 and 100"

    context = _get_context()

    try:
        related = await context.vault.get_related_notes(path, limit)

        if not related:
            return f"No related notes found for '{path}'"

        output = f"Found {len(related)} related note(s) for '{path}':\n\n"
        for i, (note_path, score) in enumerate(related, 1):
            output += f"{i}. **{Path(note_path).stem}** (score: {score:.1f})\n"
            output += f"   Path: `{note_path}`\n\n"

        return output

    except FileNotFoundError:
        return f"Error: Note not found: {path}"
    except Exception as e:
        logger.exception(f"Error finding related notes for {path}")
        return f"Error finding related notes: {e}"


@mcp.tool(
    name="create_calendar_event",
    description="Create a Google Calendar event linked to an Obsidian note",
)
async def create_calendar_event(
    note_path: str,
    title: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    description: str = "",
    confirm: bool = False,
) -> str:
    """
    Create a Google Calendar event linked to a note.

    Args:
        note_path: Relative path to the note
        title: Event title
        date: Event date (YYYY-MM-DD)
        time: Event time (HH:MM in 24-hour format)
        duration_minutes: Event duration in minutes (default: 60)
        description: Optional event description
        confirm: Must be set to true to confirm calendar event creation

    Returns:
        Success message with event details
    """
    if not confirm:
        return (
            "Error: Calendar event creation requires explicit confirmation. "
            "Please set confirm=true to proceed with creating this event."
        )
    if not note_path or not note_path.strip():
        return "Error: Note path cannot be empty"
    if not title or not title.strip():
        return "Error: Title cannot be empty"

    context = _get_context()

    try:
        # Verify note exists
        if not context.vault.note_exists(note_path):
            return f"Error: Note not found: {note_path}"

        # Parse date and time
        try:
            event_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            end_datetime = event_datetime + timedelta(minutes=duration_minutes)
        except ValueError as e:
            return f"Error: Invalid date/time format: {e}. Use YYYY-MM-DD and HH:MM"

        # Build obsidian:// link
        obsidian_link = f"{context.config.obsidian_url_base}{note_path}"

        # Add link to description
        full_description = f"{description}\n\nLinked note: {obsidian_link}"

        # Create calendar event
        calendar = context.get_calendar()
        event = calendar.create_event(
            summary=title,
            start_datetime=event_datetime,
            end_datetime=end_datetime,
            description=full_description,
        )

        event_id = event.get("id")
        event_link = event.get("htmlLink")

        # Update note frontmatter with event info
        try:
            note = await context.vault.read_note(note_path)
            frontmatter = note.frontmatter or {}

            # Add calendar event info
            frontmatter["calendar_event_id"] = event_id
            frontmatter["calendar_event_link"] = event_link
            frontmatter["calendar_event_date"] = date
            frontmatter["calendar_event_time"] = time

            await context.vault.update_note(note_path, note.body, frontmatter)
        except Exception as e:
            logger.warning(f"Failed to update note frontmatter: {e}")

        return (
            f"✓ Created calendar event: {title}\n"
            f"   Date: {date} at {time}\n"
            f"   Duration: {duration_minutes} minutes\n"
            f"   Event link: {event_link}\n"
            f"   Note link added to event description"
        )

    except CalendarAuthError as e:
        return f"Error: Calendar not configured: {e}"
    except CalendarError as e:
        return f"Error creating event: {e}"
    except VaultSecurityError as e:
        return f"Error: Security violation: {e}"
    except Exception as e:
        logger.exception("Error creating calendar event")
        return f"Error creating calendar event: {e}"


@mcp.tool(
    name="list_calendar_events",
    description="List upcoming Google Calendar events",
)
def list_calendar_events(max_results: int = 10, days_ahead: int = 7) -> str:
    """
    List upcoming calendar events.

    Args:
        max_results: Maximum number of events (default: 10)
        days_ahead: Number of days ahead to search (default: 7)

    Returns:
        Formatted list of upcoming events
    """
    if max_results <= 0 or max_results > 100:
        return "Error: max_results must be between 1 and 100"
    if days_ahead <= 0 or days_ahead > 365:
        return "Error: days_ahead must be between 1 and 365"

    context = _get_context()

    try:
        calendar = context.get_calendar()
        time_min = datetime.utcnow()
        time_max = time_min + timedelta(days=days_ahead)

        events = calendar.list_events(max_results=max_results, time_min=time_min, time_max=time_max)

        if not events:
            return "No upcoming events found"

        output = f"Found {len(events)} upcoming event(s):\n\n"

        for i, event in enumerate(events, 1):
            title = event.get("summary", "Untitled")
            start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date"))
            event_link = event.get("htmlLink")
            description = event.get("description", "")

            output += f"{i}. **{title}**\n"
            output += f"   When: {start}\n"

            # Check if event has obsidian link
            if "obsidian://" in description:
                output += "   Has linked note\n"

            output += f"   Link: {event_link}\n\n"

        return output

    except CalendarAuthError as e:
        return f"Error: Calendar not configured: {e}"
    except CalendarError as e:
        return f"Error listing events: {e}"
    except Exception as e:
        logger.exception("Error listing calendar events")
        return f"Error listing calendar events: {e}"


@mcp.tool(
    name="get_calendar_event",
    description="Get details of a specific calendar event by ID",
)
def get_calendar_event(event_id: str) -> str:
    """
    Get a calendar event by ID.

    Args:
        event_id: Calendar event ID

    Returns:
        Event details
    """
    if not event_id or not event_id.strip():
        return "Error: Event ID cannot be empty"

    context = _get_context()

    try:
        calendar = context.get_calendar()
        event = calendar.get_event(event_id)

        result = [f"# Event: {event.get('summary', 'Untitled')}"]
        result.append(f"ID: `{event.get('id')}`")
        result.append(f"Link: {event.get('htmlLink')}")

        # Time info
        start = event.get("start", {})
        end = event.get("end", {})
        if "dateTime" in start:
            start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
            result.append(f"Start: {start_dt.strftime('%Y-%m-%d %H:%M')}")
            result.append(f"End: {end_dt.strftime('%Y-%m-%d %H:%M')}")
            duration = (end_dt - start_dt).seconds // 60
            result.append(f"Duration: {duration} minutes")

        # Optional fields
        if event.get("description"):
            result.append(f"\n**Description:**\n{event['description']}")
        if event.get("location"):
            result.append(f"\n**Location:** {event['location']}")

        return "\n".join(result)

    except CalendarError as e:
        logger.exception("Error getting calendar event")
        return f"Error: {e}"
    except Exception as e:
        logger.exception("Error getting calendar event")
        return f"Error getting calendar event: {e}"


@mcp.tool(
    name="update_calendar_event",
    description="Update/move a calendar event (change date, time, title, or description)",
)
async def update_calendar_event(
    event_id: str,
    title: str = "",
    date: str = "",
    time: str = "",
    duration_minutes: int = 0,
    description: str = "",
    location: str = "",
    confirm: bool = False,
) -> str:
    """
    Update a calendar event.

    Args:
        event_id: Calendar event ID to update
        title: New event title (optional)
        date: New date YYYY-MM-DD (optional)
        time: New time HH:MM (optional)
        duration_minutes: New duration in minutes (optional)
        description: New description (optional)
        location: New location (optional)
        confirm: Must be set to true to confirm event update

    Returns:
        Success message with updated details
    """
    if not confirm:
        return (
            "Error: Calendar event update requires explicit confirmation. "
            "Please set confirm=true to proceed with updating this event."
        )
    if not event_id or not event_id.strip():
        return "Error: Event ID cannot be empty"

    context = _get_context()

    try:
        calendar = context.get_calendar()

        # Get current event to preserve existing values
        current_event = calendar.get_event(event_id)

        # Parse new date/time if provided
        new_start = None
        new_end = None
        if date and time:
            try:
                event_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
                if duration_minutes > 0:
                    new_end = event_datetime + timedelta(minutes=duration_minutes)
                else:
                    # Preserve original duration
                    current_start = current_event.get("start", {})
                    current_end = current_event.get("end", {})
                    if "dateTime" in current_start and "dateTime" in current_end:
                        old_start = datetime.fromisoformat(
                            current_start["dateTime"].replace("Z", "+00:00")
                        )
                        old_end = datetime.fromisoformat(
                            current_end["dateTime"].replace("Z", "+00:00")
                        )
                        duration = (old_end - old_start).seconds // 60
                        new_end = event_datetime + timedelta(minutes=duration)
                new_start = event_datetime
            except ValueError as e:
                return f"Error: Invalid date/time format: {e}. Use YYYY-MM-DD and HH:MM"

        # Prepare update - preserve obsidian:// link if in description
        new_description = None
        if description:
            current_desc = current_event.get("description", "")
            # Check if there's an obsidian link to preserve
            if context.config.obsidian_url_base in current_desc:
                link_start = current_desc.find(context.config.obsidian_url_base)
                link_end = current_desc.find("\n", link_start)
                if link_end == -1:
                    link_end = len(current_desc)
                obsidian_link = current_desc[link_start:link_end].strip()
                new_description = f"{description}\n\n{obsidian_link}"
            else:
                new_description = description

        # Update event
        updated_event = calendar.update_event(
            event_id=event_id,
            summary=title if title else None,
            start_datetime=new_start,
            end_datetime=new_end,
            description=new_description,
            location=location if location else None,
        )

        # Update note frontmatter if date changed and we can find the linked note
        if new_start:
            current_desc = current_event.get("description", "")
            if context.config.obsidian_url_base in current_desc:
                link_start = current_desc.find(context.config.obsidian_url_base)
                note_path = current_desc[link_start + len(context.config.obsidian_url_base) :]
                note_path = note_path.split()[0] if note_path else ""

                if note_path and context.vault.note_exists(note_path):
                    note = await context.vault.read_note(note_path)
                    if note.frontmatter and "calendar_event_id" in note.frontmatter:
                        await context.vault.update_frontmatter(
                            note_path,
                            {
                                "calendar_event_date": new_start.strftime("%Y-%m-%d"),
                                "calendar_event_time": new_start.strftime("%H:%M"),
                            },
                        )

        result = ["✅ Calendar event updated!"]
        result.append(f"Event: {updated_event.get('summary', 'Untitled')}")
        result.append(f"Link: {updated_event.get('htmlLink')}")

        if new_start:
            result.append(f"New time: {new_start.strftime('%Y-%m-%d %H:%M')}")

        return "\n".join(result)

    except CalendarError as e:
        logger.exception("Error updating calendar event")
        return f"Error: {e}"
    except Exception as e:
        logger.exception("Error updating calendar event")
        return f"Error updating calendar event: {e}"


@mcp.tool(
    name="search_calendar_events",
    description="Search calendar events by text query or date range",
)
def search_calendar_events(
    query: str = "",
    date_from: str = "",
    date_to: str = "",
    max_results: int = 20,
) -> str:
    """
    Search calendar events.

    Args:
        query: Text to search for in event title/description (optional)
        date_from: Start date YYYY-MM-DD (default: today)
        date_to: End date YYYY-MM-DD (default: 30 days from date_from)
        max_results: Maximum number of events (default: 20)

    Returns:
        List of matching events
    """
    context = _get_context()

    try:
        # Parse date range
        if date_from:
            try:
                time_min = datetime.strptime(date_from, "%Y-%m-%d")
            except ValueError:
                return "Error: Invalid date_from format. Use YYYY-MM-DD"
        else:
            time_min = datetime.now()

        if date_to:
            try:
                time_max = datetime.strptime(date_to, "%Y-%m-%d")
            except ValueError:
                return "Error: Invalid date_to format. Use YYYY-MM-DD"
        else:
            time_max = time_min + timedelta(days=30)

        calendar = context.get_calendar()
        events = calendar.list_events(max_results=max_results, time_min=time_min, time_max=time_max)

        # Filter by query if provided
        if query:
            query_lower = query.lower()
            events = [
                e
                for e in events
                if query_lower in e.get("summary", "").lower()
                or query_lower in e.get("description", "").lower()
            ]

        if not events:
            return f"No events found matching: {query or 'criteria'}"

        result = [f"Found {len(events)} event(s):\n"]

        for i, event in enumerate(events, 1):
            title = event.get("summary", "Untitled")
            event_id = event.get("id")
            start = event.get("start", {})

            if "dateTime" in start:
                start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                time_str = start_dt.strftime("%Y-%m-%d %H:%M")
            else:
                time_str = start.get("date", "Unknown")

            result.append(f"{i}. **{title}**")
            result.append(f"   Time: {time_str}")
            result.append(f"   ID: `{event_id}`")

            # Check for linked note
            description = event.get("description", "")
            if context.config.obsidian_url_base in description:
                result.append("   📝 Linked to Obsidian note")

            result.append("")

        return "\n".join(result)

    except CalendarError as e:
        logger.exception("Error searching calendar events")
        return f"Error: {e}"
    except Exception as e:
        logger.exception("Error searching calendar events")
        return f"Error searching calendar events: {e}"


@mcp.tool(
    name="delete_calendar_event",
    description="Delete a Google Calendar event",
)
async def delete_calendar_event(
    event_id: str, update_note: bool = True, confirm: bool = False
) -> str:
    """
    Delete a calendar event.

    Args:
        event_id: Calendar event ID
        update_note: If true, remove event info from linked note (default: true)
        confirm: Must be set to true to confirm event deletion

    Returns:
        Success message
    """
    if not confirm:
        return (
            "Error: Calendar event deletion requires explicit confirmation. "
            "Please set confirm=true to proceed with deleting this event."
        )
    if not event_id or not event_id.strip():
        return "Error: Event ID cannot be empty"

    context = _get_context()

    try:
        # Get event details before deleting (for note update)
        calendar = context.get_calendar()

        if update_note:
            try:
                event = calendar.get_event(event_id)
                description = event.get("description", "")

                # Extract note path from obsidian:// link
                if "obsidian://" in description:
                    # Find the note path in the link
                    start_idx = description.find(context.config.obsidian_url_base)
                    if start_idx != -1:
                        note_path = description[start_idx + len(context.config.obsidian_url_base) :]
                        # Extract until next whitespace or newline
                        note_path = note_path.split()[0] if note_path else ""

                        if note_path and context.vault.note_exists(note_path):
                            # Remove calendar event info from frontmatter
                            note = await context.vault.read_note(note_path)
                            if note.frontmatter:
                                frontmatter = dict(note.frontmatter)
                                frontmatter.pop("calendar_event_id", None)
                                frontmatter.pop("calendar_event_link", None)
                                frontmatter.pop("calendar_event_date", None)
                                frontmatter.pop("calendar_event_time", None)
                                await context.vault.update_note(note_path, note.body, frontmatter)
            except Exception as e:
                logger.warning(f"Failed to update note: {e}")

        # Delete the event
        calendar.delete_event(event_id)

        return f"✓ Deleted calendar event: {event_id}"

    except CalendarAuthError as e:
        return f"Error: Calendar not configured: {e}"
    except CalendarError as e:
        return f"Error deleting event: {e}"
    except Exception as e:
        logger.exception("Error deleting calendar event")
        return f"Error deleting calendar event: {e}"


# Batch Operations

# Maximum batch size to prevent server hangs
MAX_BATCH_SIZE = 50


@mcp.tool(
    name="batch_update_notes",
    description="Update multiple notes atomically with automatic backup and rollback",
)
async def batch_update_notes(
    updates: list[NoteUpdate],
    dry_run: bool = False,
    confirm: bool = False,
) -> str:
    """
    Update multiple notes in a single atomic operation.

    Args:
        updates: List of NoteUpdate objects with path, content, and optional frontmatter
        dry_run: If true, only preview changes without applying
        confirm: Must be true to apply changes (safety check)

    Returns:
        Success message with update summary or preview
    """
    if not updates:
        return "Error: No updates provided"

    # Check batch size limit
    if len(updates) > MAX_BATCH_SIZE:
        return (
            f"Error: Batch size ({len(updates)}) exceeds maximum ({MAX_BATCH_SIZE}).\n"
            f"Split into smaller batches to avoid server timeouts."
        )

    logger.info(f"Starting batch_update_notes: {len(updates)} notes")

    # Extract paths (Pydantic already validated the structure)
    paths = [update.path for update in updates]

    context = _get_context()

    # Dry run - just preview
    if dry_run:
        result = [f"**Preview: Batch update of {len(updates)} notes**\n"]
        for i, update in enumerate(updates, 1):
            content_preview = update.content[:100] + ("..." if len(update.content) > 100 else "")
            result.append(f"{i}. `{update.path}`")
            result.append(f"   Content preview: {content_preview}")
            if update.frontmatter:
                result.append(f"   Frontmatter: {list(update.frontmatter.keys())}")
            result.append("")

        result.append("Set dry_run=false and confirm=true to apply changes")
        return "\n".join(result)

    # Require confirmation for actual updates
    if not confirm:
        return (
            f"Error: Batch update of {len(updates)} notes requires explicit confirmation. "
            f"Set confirm=true to proceed. Use dry_run=true to preview changes first."
        )

    try:
        # Create backup before making any changes (async)
        backup_id = await context.vault.create_batch_backup(paths)
        logger.info(f"Created backup: {backup_id}")

        # Apply all updates
        updated = []
        failed = []

        for update in updates:
            try:
                await context.vault.update_note(
                    update.path, update.content, frontmatter=update.frontmatter
                )
                updated.append(update.path)
                logger.debug(f"Updated: {update.path}")
            except Exception as e:
                failed.append((update.path, str(e)))
                logger.error(f"Failed to update {update.path}: {e}")

        # If any failed, rollback all changes (async)
        if failed:
            logger.warning(f"Batch update failed, rolling back {len(updated)} changes")
            await context.vault.restore_batch_backup(backup_id)

            result = ["❌ Batch update failed - all changes rolled back\n"]
            result.append("**Failed updates:**")
            for path, error in failed:
                result.append(f"- `{path}`: {error}")
            result.append(f"\n**Backup preserved:** `.batch_backups/{backup_id}/`")
            return "\n".join(result)

        # All succeeded
        logger.info(f"Completed batch_update_notes: {len(updated)} notes updated successfully")
        result = [f"✅ Successfully updated {len(updated)} notes\n"]
        for i, path in enumerate(updated, 1):
            result.append(f"{i}. `{path}`")

        result.append(f"\n**Backup created:** `.batch_backups/{backup_id}/`")
        result.append("Use restore_batch_backup to undo if needed")

        return "\n".join(result)

    except FileNotFoundError as e:
        return f"Error: {e}"
    except VaultSecurityError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.exception("Error in batch update")
        return f"Error: {e}"


@mcp.tool(
    name="batch_append_notes",
    description="Append content to multiple notes atomically",
)
async def batch_append_notes(
    appends: list[NoteAppend],
    confirm: bool = False,
) -> str:
    """
    Append content to multiple notes.

    Args:
        appends: List of NoteAppend objects with path and content
        confirm: Must be true to apply changes

    Returns:
        Success message with append summary
    """
    if not appends:
        return "Error: No appends provided"

    # Check batch size limit
    if len(appends) > MAX_BATCH_SIZE:
        return (
            f"Error: Batch size ({len(appends)}) exceeds maximum ({MAX_BATCH_SIZE}).\n"
            f"Split into smaller batches to avoid server timeouts."
        )

    logger.info(f"Starting batch_append_notes: {len(appends)} notes")

    # Extract paths (Pydantic already validated)
    paths = [append.path for append in appends]

    if not confirm:
        return (
            f"Error: Batch append to {len(appends)} notes requires explicit confirmation. "
            f"Set confirm=true to proceed."
        )

    context = _get_context()

    try:
        # Create backup (async)
        backup_id = await context.vault.create_batch_backup(paths)

        # Apply all appends
        appended = []
        failed = []

        for append in appends:
            try:
                await context.vault.append_to_note(append.path, append.content)
                appended.append(append.path)
            except Exception as e:
                failed.append((append.path, str(e)))

        # Rollback on failure (async)
        if failed:
            await context.vault.restore_batch_backup(backup_id)
            result = ["❌ Batch append failed - all changes rolled back\n"]
            result.append("**Failed appends:**")
            for path, error in failed:
                result.append(f"- `{path}`: {error}")
            return "\n".join(result)

        # Success
        logger.info(f"Completed batch_append_notes: {len(appended)} notes updated successfully")
        result = [f"✅ Appended to {len(appended)} notes\n"]
        for path in appended:
            result.append(f"- `{path}`")
        result.append(f"\n**Backup:** `.batch_backups/{backup_id}/`")
        return "\n".join(result)

    except Exception as e:
        logger.exception("Error in batch append")
        return f"Error: {e}"


@mcp.tool(
    name="restore_batch_backup",
    description="Restore notes from a batch backup (undo batch operation)",
)
async def restore_batch_backup(backup_id: str) -> str:
    """
    Restore notes from a batch backup.

    Args:
        backup_id: Backup ID (timestamp) to restore from

    Returns:
        Success message with restored note count
    """
    if not backup_id or not backup_id.strip():
        return "Error: Backup ID cannot be empty"

    context = _get_context()

    try:
        restored = await context.vault.restore_batch_backup(backup_id)

        result = [f"✅ Restored {len(restored)} notes from backup `{backup_id}`\n"]
        for path in restored:
            result.append(f"- `{path}`")

        return "\n".join(result)

    except FileNotFoundError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.exception("Error restoring backup")
        return f"Error: {e}"


@mcp.tool(
    name="list_batch_backups",
    description="List available batch backups",
)
def list_batch_backups(limit: int = 10) -> str:
    """
    List available batch backups.

    Args:
        limit: Maximum number of backups to list

    Returns:
        List of backups with details
    """
    context = _get_context()

    try:
        backups = context.vault.list_batch_backups(limit=limit)

        if not backups:
            return "No batch backups found"

        result = [f"**Available batch backups ({len(backups)}):**\n"]

        for backup in backups:
            result.append(f"**{backup['backup_id']}**")
            result.append(f"  Created: {backup['created']}")
            result.append(f"  Notes: {backup['note_count']}")
            size_mb = backup["size_bytes"] / (1024 * 1024)
            result.append(f"  Size: {size_mb:.2f} MB\n")

        return "\n".join(result)

    except Exception as e:
        logger.exception("Error listing backups")
        return f"Error: {e}"


def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting Obsidian MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
