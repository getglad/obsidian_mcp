# Obsidian MCP Server

Model Context Protocol (MCP) server for accessing Obsidian vaults. This server enables AI assistants like Claude to read, search, and interact with your Obsidian notes.

## Features

### Core Operations

- **Read Notes**: Access individual notes with frontmatter and content
- **Write Notes**: Create, update, append, and delete notes
- **Search**: Search notes by content, title, tags, or frontmatter properties
- **List Notes**: Browse notes with filtering options

### Link Analysis

- **Backlinks**: Find all notes that link to a specific note
- **Outgoing Links**: Get all links from a note to other notes
- **Link Graph**: Build a network graph of all note connections
- **Related Notes**: Discover notes related by shared links and tags
- **Orphaned Notes**: Find notes with no incoming or outgoing links

### Tag Management

- **List All Tags**: Get all tags with usage counts
- **Filter by Tag**: Find all notes with a specific tag
- **Tag Statistics**: Analyze tag usage across the vault

### Daily Notes

- **Get Daily Note**: Retrieve or create daily notes by date
- **List Daily Notes**: Browse recent daily notes
- **Auto-creation**: Automatically create daily notes with proper formatting

### Templates

- **List Templates**: Browse available templates
- **Create from Template**: Generate new notes from templates
- **Variable Replacement**: Support for {{date}}, {{time}}, {{title}} placeholders

### Google Calendar Integration (Optional)

- **Create Calendar Events**: Create Google Calendar events linked to notes
- **List Events**: Browse upcoming calendar events
- **Delete Events**: Remove calendar events and update note metadata
- **Bidirectional Linking**: Events link to notes via obsidian:// URLs
- **Auto-metadata**: Calendar event details stored in note frontmatter

### Vault Statistics

- **Vault Stats**: Total notes, tags, size, and distribution
- **Search by Property**: Query notes by frontmatter fields

### Security & Performance

- **Path Traversal Protection**: Prevent access outside vault
- **Input Validation**: Comprehensive validation of all inputs
- **Optimized Search**: Fast search with caching
- **Safe Deletion**: Trash folder support (reversible deletes)

## Requirements

- Python 3.10 or higher
- An Obsidian vault

## Installation

### Using uv (Recommended)

```bash
# Clone or navigate to the project directory
cd obsidian_mcp

# Install with uv
uv pip install -e .

# Or install with development dependencies
uv pip install -e ".[dev]"
```

### Using pip

```bash
pip install -e .
```

## Configuration

### Using .env File (Recommended)

Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env

# Edit with your vault path
nano .env
```

Example `.env`:

```bash
OBSIDIAN_VAULT_PATH=/Users/yourname/Documents/ObsidianVault
OBSIDIAN_MAX_RESULTS=100
OBSIDIAN_SNIPPET_LENGTH=200
```

### Using Environment Variables

Alternatively, set environment variables directly:

```bash
export OBSIDIAN_VAULT_PATH="/path/to/your/vault"
export OBSIDIAN_MAX_RESULTS=100
export OBSIDIAN_SNIPPET_LENGTH=200
```

### Google Calendar Integration (Optional)

To enable Google Calendar integration:

#### 1. Enable Google Calendar API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Calendar API**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Configure OAuth consent screen if prompted
6. Select **Application type**: Desktop app
7. Download the credentials as `credentials.json`

#### 2. Configure Credentials

```bash
# Place credentials.json in your project directory
cp ~/Downloads/credentials.json /path/to/obsidian_mcp/

# Add to your .env file
echo "GOOGLE_CALENDAR_CREDENTIALS_PATH=/path/to/obsidian_mcp/credentials.json" >> .env
echo "GOOGLE_CALENDAR_ID=primary" >> .env
echo "OBSIDIAN_VAULT_URL_BASE=obsidian://open?vault=YourVaultName&file=" >> .env
```

**Important**: Replace `YourVaultName` with your actual Obsidian vault name (found in Obsidian Settings → About).

#### 3. Scope to a Specific Calendar (Optional)

By default, the integration uses your primary calendar (`GOOGLE_CALENDAR_ID=primary`). To scope operations to a specific calendar:

**Get your Calendar ID:**

1. Go to [Google Calendar](https://calendar.google.com)
2. Click settings gear → **Settings**
3. Select the calendar you want to use (left sidebar)
4. Scroll to **Integrate calendar** section
5. Copy the **Calendar ID** (e.g., `work@group.calendar.google.com`)

**Configure it:**

```bash
# In your .env file
GOOGLE_CALENDAR_ID=work@group.calendar.google.com
```

**Important**: While OAuth grants access to all your calendars, the MCP server will ONLY create, read, update, and delete events in the configured calendar. All calendar operations respect this setting for safety.

#### 4. First-Time Authorization

When you first use a calendar tool, the server will:

1. Open your browser for Google OAuth authorization
2. Ask you to grant calendar access permissions
3. Save the token to `.credentials/token.json` for future use

**Security Notes**:

- The server uses scope `https://www.googleapis.com/auth/calendar.events` (events only, no calendar management)
- Token file is automatically protected with 600 permissions
- Both `credentials.json` and `.credentials/` are gitignored

#### 5. Event-Note Linking

Created calendar events include:

- Obsidian deep link in event description (clickable in Google Calendar)
- Event metadata in note frontmatter:
  ```yaml
  ---
  calendar_event_id: "abc123..."
  calendar_event_link: "https://www.google.com/calendar/event?eid=..."
  calendar_event_date: "2025-01-15"
  calendar_event_time: "14:00"
  ---
  ```

### Claude Desktop Integration

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "uv",
      "args": ["run", "obsidian-mcp"],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/Users/yourname/Documents/ObsidianVault"
      }
    }
  }
}
```

Or using the installed script directly:

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "/path/to/.venv/bin/obsidian-mcp",
      "env": {
        "OBSIDIAN_VAULT_PATH": "/Users/yourname/Documents/ObsidianVault"
      }
    }
  }
}
```

## Usage

### Available Tools

The server exposes 27 MCP tools organized by category:

#### Read Operations

**`read_note`** - Read the full content of a note

- `path` (string): Relative path to the note (e.g., "Projects/MCP.md")

**`search_notes`** - Search the vault by content, title, tags, or all

- `query` (string): Search query
- `search_type` (string): "content", "title", "tags", or "all" (default: "all")
- `folder` (string): Limit search to folder
- `limit` (number): Max results (default: 20)

**`list_notes`** - List notes in the vault with optional filters

- `folder` (string): Folder to list (empty for root)
- `recursive` (boolean): Include subfolders (default: true)
- `limit` (number): Max results (default: 100)

#### Link Analysis

**`get_backlinks`** - Get all notes that link to a specific note (incoming links)

- `path` (string): Relative path to the note

**`get_outgoing_links`** - Get all links from a note to other notes (outgoing links)

- `path` (string): Relative path to the note

**`get_related_notes`** - Find notes related to a specific note based on shared links and tags

- `path` (string): Relative path to the note
- `limit` (number): Maximum number of related notes (default: 10)

**`get_orphaned_notes`** - Find notes with no incoming or outgoing links

- `limit` (number): Maximum number of results (default: 50)

#### Tag Operations

**`list_all_tags`** - Get all tags in the vault with usage counts

- `limit` (number): Maximum number of tags to return (default: 100)

**`get_notes_by_tag`** - Find all notes with a specific tag

- `tag` (string): Tag to search for (with or without #)
- `limit` (number): Maximum number of results (default: 50)

#### Search & Query

**`search_by_property`** - Search for notes by frontmatter property (metadata field)

- `property_name` (string): Name of the frontmatter property to search
- `property_value` (string): Optional value to match (empty to find all notes with this property)
- `limit` (number): Maximum number of results (default: 50)

#### Statistics

**`get_vault_stats`** - Get statistics about the vault

- Returns total notes, tags, size, and top tags

#### Write Operations

**`create_note`** - Create a new note in the vault

- `path` (string): Relative path for the new note (e.g., "Projects/New Idea.md")
- `content` (string): Content of the note
- `tags` (list[string]): Optional list of tags to add to frontmatter
- `overwrite` (boolean): If true, overwrite existing note (default: false)

**`update_note`** - Update an existing note's content (preserves frontmatter)

- `path` (string): Relative path to the note
- `content` (string): New content for the note body

**`append_to_note`** - Append content to the end of an existing note

- `path` (string): Relative path to the note
- `content` (string): Content to append

**`delete_note`** - Delete a note (moves to .trash by default)

- `path` (string): Relative path to the note
- `permanent` (boolean): If true, permanently delete; otherwise move to .trash folder (default: false)

**`update_frontmatter`** - Update frontmatter fields in a note (preserves content)

- `path` (string): Relative path to the note
- `property_name` (string): Name of the frontmatter field
- `property_value` (string): Value to set

#### Batch Operations

**`batch_update_notes`** - Update multiple notes atomically with automatic backup/rollback

- `updates` (list): Array of objects with `{path, content, frontmatter?}` structure
- `dry_run` (boolean): Preview changes without applying (default: false)
- `confirm` (boolean): Must be true to apply changes (safety check)

**`batch_append_notes`** - Append content to multiple notes atomically

- `appends` (list): Array of objects with `{path, content}` structure
- `confirm` (boolean): Must be true to apply changes

**`restore_batch_backup`** - Restore notes from a batch backup (undo operation)

- `backup_id` (string): Backup timestamp ID (e.g., "20250115_143025")

**`list_batch_backups`** - List available batch backups

- `limit` (number): Maximum number of backups to list (default: 10)

See [docs/BATCH_OPERATIONS.md](docs/BATCH_OPERATIONS.md) for complete guide with examples.

#### Daily Notes

**`get_daily_note`** - Get or create a daily note for a specific date

- `date_str` (string): Date in YYYY-MM-DD format (empty for today)
- `folder` (string): Folder where daily notes are stored (default: "Daily Notes")
- `create` (boolean): If true, create the note if it doesn't exist (default: true)

**`list_daily_notes`** - List recent daily notes

- `folder` (string): Folder where daily notes are stored (default: "Daily Notes")
- `limit` (number): Maximum number of notes (default: 30)

#### Templates

**`list_templates`** - List available note templates

- `folder` (string): Folder where templates are stored (default: "Templates")

**`create_from_template`** - Create a new note from a template

- `template_path` (string): Path to the template note
- `new_note_path` (string): Path for the new note
- `title` (string): Optional title to replace {{title}} placeholder

#### Graph & Network

**`get_link_graph`** - Get the link graph for the vault (nodes and edges for visualization)

- `max_notes` (number): Maximum number of notes to include (default: 500)

#### Google Calendar (Optional)

**`create_calendar_event`** - Create a Google Calendar event linked to a note

- `note_path` (string): Path to the note to link (e.g., "Projects/Meeting.md")
- `title` (string): Event title
- `date` (string): Event date in YYYY-MM-DD format (e.g., "2025-01-15")
- `time` (string): Event time in HH:MM format (e.g., "14:00")
- `duration_minutes` (number): Event duration in minutes (default: 60)
- `description` (string): Optional event description
- `confirm` (boolean): Must be true to confirm creation (safety check)

**`list_calendar_events`** - List upcoming calendar events

- `max_results` (number): Maximum number of events (default: 10)
- `days_ahead` (number): Number of days to look ahead (default: 7)

**`get_calendar_event`** - Get details of a specific calendar event

- `event_id` (string): Calendar event ID

**`search_calendar_events`** - Search calendar events by text query or date range

- `query` (string): Text to search for in event title/description (optional)
- `date_from` (string): Start date YYYY-MM-DD (default: today)
- `date_to` (string): End date YYYY-MM-DD (default: 30 days from date_from)
- `max_results` (number): Maximum number of events (default: 20)

**`update_calendar_event`** - Update/move a calendar event

- `event_id` (string): Calendar event ID to update
- `title` (string): New event title (optional)
- `date` (string): New date YYYY-MM-DD (optional)
- `time` (string): New time HH:MM (optional)
- `duration_minutes` (number): New duration in minutes (optional)
- `description` (string): New description (optional)
- `location` (string): New location (optional)
- `confirm` (boolean): Must be true to confirm update (safety check)

**`delete_calendar_event`** - Delete a calendar event

- `event_id` (string): Calendar event ID
- `update_note` (boolean): If true, remove event info from linked note (default: true)
- `confirm` (boolean): Must be true to confirm deletion (safety check)

## Development

### Setup Development Environment

```bash
# Install with development dependencies
make dev

# Or manually
uv pip install -e ".[dev]"
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type check
make type-check

# Run all quality checks
make quality
```

### Testing

```bash
# Run unit tests only
make test

# Run integration tests
make test-integration

# Run all tests
make test-all

# Run tests with coverage
pytest tests/ --cov=src/obsidian_mcp --cov-report=html
```

### Project Structure

```
obsidian_mcp/
├── src/obsidian_mcp/
│   ├── __init__.py
│   ├── server.py      # MCP server implementation
│   ├── vault.py       # Vault operations
│   ├── search.py      # Search functionality
│   ├── calendar.py    # Google Calendar integration
│   └── config.py      # Configuration management
├── tests/
│   ├── unit/          # Unit tests
│   ├── integration/   # Integration tests
│   └── conftest.py    # Pytest fixtures
├── pyproject.toml     # Project configuration
├── Makefile           # Build automation
└── README.md          # This file
```

## Security

### Safe by Design

The server is designed to work safely within your Obsidian vault:

- Access is restricted to your configured vault directory only
- Cannot access files outside the vault (including through symbolic links)
- All file operations are validated before execution
- Batch operations create backups before making changes and restore them if any operation fails

### Best Practices

1. **Separate Vault**: Consider using a separate vault for AI access
2. **Exclude Sensitive Folders**: Configure `exclude_folders` in your setup
3. **Use Batch Operations**: When editing multiple notes, use batch operations to get automatic backups before changes and automatic restore if anything fails
4. **Regular Backups**: Always maintain backups of your vault

## Troubleshooting

### Server Not Starting

**Problem**: "OBSIDIAN_VAULT_PATH environment variable must be set"

**Solution**: Set the vault path in your environment or Claude config.

### No Notes Found

**Problem**: Search or list returns no results

**Solution**:

- Check that the vault path is correct
- Ensure notes have `.md` extension
- Check that folders aren't in the exclude list

### Path Security Errors

**Problem**: "Path attempts to access files outside vault"

**Solution**: Use relative paths only (e.g., "folder/note.md" not "/absolute/path")

### Unicode Errors

**Problem**: Errors reading notes with special characters

**Solution**: Ensure notes are saved as UTF-8 in Obsidian

### Google Calendar Issues

#### Calendar Not Authorized

**Problem**: "Calendar credentials not found" or OAuth not starting

**Solution**:

- Verify `GOOGLE_CALENDAR_CREDENTIALS_PATH` points to valid `credentials.json`
- Delete `.credentials/token.json` and re-authorize
- Check file permissions on credentials

#### Wrong Calendar Modified

**Problem**: Events created in wrong calendar

**Solution**:

- Verify `GOOGLE_CALENDAR_ID` in `.env` matches your intended calendar
- Get correct Calendar ID from Google Calendar Settings → Integrate calendar
- Restart Claude Desktop after changing `.env`
- See [Calendar Guide](docs/CALENDAR.md#finding-your-calendar-id) for detailed instructions

#### Permission Denied

**Problem**: "Insufficient permission" when creating/updating events

**Solution**:

- Re-authorize with correct scope: delete `.credentials/token.json` and retry
- Verify OAuth consent screen includes `calendar.events` scope
- Check you have edit permissions on the target calendar

#### Obsidian Links Not Working

**Problem**: Clicking event in Google Calendar doesn't open note

**Solution**:

- Verify `OBSIDIAN_VAULT_URL_BASE` exactly matches your vault name (Settings → About)
- Include proper format: `obsidian://open?vault=VaultName&file=`
- Check vault name capitalization and spaces
- Ensure Obsidian is installed and vault is open

For complete calendar documentation, see [docs/CALENDAR.md](docs/CALENDAR.md) and [docs/EXAMPLES.md](docs/EXAMPLES.md).

## Limitations

- **File Types**: Only `.md` and `.canvas` files by default
- **No Live Updates**: Changes to vault require server restart to reflect in list operations
- **Link Resolution**: Basic wikilink resolution (no support for aliases yet)
- **Batch Size**: Batch operations limited to 50 notes per operation

## Roadmap

- [x] Write operations (create, update, delete notes)
- [x] Backlinks and forward links support
- [x] Daily notes integration
- [x] Template system
- [x] Graph data resources
- [x] Google Calendar integration with bidirectional linking
- [x] Batch operations with async I/O optimization
- [ ] Real-time vault monitoring
- [ ] Canvas file support improvements
- [ ] Attachment handling
- [ ] Advanced link resolution (aliases, headings)
- [ ] Caching for improved performance

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass (`make test-all`)
5. Run quality checks (`make quality`)
6. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [Model Context Protocol](https://modelcontextprotocol.io)
- Designed for [Obsidian](https://obsidian.md)
- Inspired by the knowledge management community
