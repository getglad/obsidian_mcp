# Quick Start Guide

## Installation Complete! ✅

All dependencies are installed and tests are passing.

## Test Your Installation

```bash
# Verify installation
.venv/bin/python -c "from obsidian_mcp import __version__; print(__version__)"
# Output: 0.1.0

# See available commands
make help
```

## Try It Out

### 1. Set Up Environment

Create a `.env` file with your vault path:

```bash
# Copy the example
cp .env.example .env

# Edit .env and set your vault path
nano .env
```

Your `.env` should look like:
```bash
OBSIDIAN_VAULT_PATH=/Users/yourname/Documents/ObsidianVault
```

### 2. Run the MCP Server

```bash
# Activate virtual environment
source .venv/bin/activate

# Start the server
obsidian-mcp

# Or run directly
.venv/bin/obsidian-mcp
```

### 3. Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "/path/to/obsidian_mcp/.venv/bin/obsidian-mcp",
      "env": {
        "OBSIDIAN_VAULT_PATH": "/path/to/your/vault"
      }
    }
  }
}
```

**Note:** Replace `/path/to/obsidian_mcp/` with your actual installation path before restarting Claude Desktop.

## Optional: Google Calendar Integration

### Quick Setup (2 Steps)

1. **Get Google Calendar credentials:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Enable Calendar API → Create OAuth credentials (Desktop app)
   - Download `credentials.json`

2. **Configure:**
   ```bash
   # Add to .env
   echo "GOOGLE_CALENDAR_CREDENTIALS_PATH=/path/to/credentials.json" >> .env
   echo "GOOGLE_CALENDAR_ID=primary" >> .env
   echo "OBSIDIAN_VAULT_URL_BASE=obsidian://open?vault=YourVaultName&file=" >> .env
   ```

3. **Test:**
   - Use any calendar tool in Claude Desktop
   - Browser opens for OAuth authorization
   - Grant permissions
   - Done! Calendar events can now link to notes

**Need calendar scoping?** See [docs/CALENDAR.md](docs/CALENDAR.md#understanding-calendar-scoping) for:
- Limiting to specific calendars
- Multiple calendar strategies
- Security model details

## Development Workflow

### Make Changes

```bash
# Edit code in src/obsidian_mcp/

# Format and lint
make quality

# Run tests
make test-all
```

### Before Committing

```bash
# Run full validation
make quality test-all
```

## Test Results

✅ **34/34 tests passing**
✅ **All quality checks passing**
- Code formatted with Ruff
- No linting issues
- Type checking passed with mypy
- 64% test coverage

## Coverage Report

View detailed coverage:
```bash
open htmlcov/index.html
```

## Next Steps

1. **Test with your vault**: Point to a real Obsidian vault and try it
2. **Add write operations**: Implement create/update/delete (Phase 2)
3. **Add backlinks**: Implement link graph support
4. **Optimize search**: Add caching for large vaults

## Need Help?

- Run tests: `make test-all`
- Check coverage: View `htmlcov/index.html`
- Read docs: Check `README.md` and `scratch/claude/`
