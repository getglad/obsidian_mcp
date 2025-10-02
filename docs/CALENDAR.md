# Google Calendar Integration Guide

Complete guide to using Google Calendar with Obsidian MCP Server.

## Table of Contents

- [Quick Start](#quick-start)
- [Understanding Calendar Scoping](#understanding-calendar-scoping)
- [Setup Guide](#setup-guide)
- [Using Calendar Tools](#using-calendar-tools)
- [Workflows](#workflows)
- [Security Model](#security-model)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## Quick Start

### 1. Enable Google Calendar API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Calendar API**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Configure OAuth consent screen if prompted
6. Select **Application type**: Desktop app
7. Download the credentials as `credentials.json`

### 2. Configure Your Calendar

```bash
# Copy credentials
cp ~/Downloads/credentials.json /path/to/obsidian_mcp/

# Add to .env file
echo "GOOGLE_CALENDAR_CREDENTIALS_PATH=/path/to/obsidian_mcp/credentials.json" >> .env
echo "GOOGLE_CALENDAR_ID=primary" >> .env
echo "OBSIDIAN_VAULT_URL_BASE=obsidian://open?vault=YourVaultName&file=" >> .env
```

Replace `YourVaultName` with your actual Obsidian vault name (found in Obsidian Settings → About).

### 3. First Authorization

When you first use a calendar tool:

1. Browser will open for Google OAuth
2. Grant calendar access permissions
3. Token saved to `.credentials/token.json` automatically

Done! You can now create calendar events linked to your notes.

## Understanding Calendar Scoping

### What is Calendar Scoping?

Calendar scoping means **all calendar operations only affect one specific calendar** that you configure, even though OAuth grants access to all your calendars.

### How It Works

```
┌─────────────────────────────────────────┐
│  OAuth Authorization (Google)           │
│  ✓ Access to ALL your calendars         │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│  Application-Level Scoping (MCP Server) │
│  ✓ Operations ONLY on configured        │
│    calendar (GOOGLE_CALENDAR_ID)        │
└─────────────────────────────────────────┘
```

**Example:**

- You have calendars: Personal, Work, Family
- You set `GOOGLE_CALENDAR_ID=work@group.calendar.google.com`
- All MCP operations only touch your Work calendar
- Personal and Family calendars are never affected

### Why This Design?

**Google API Limitation:** OAuth scopes cannot be limited to individual calendars.

**MCP Server Protection:** Every operation explicitly passes the configured `calendar_id` to ensure safety.

## Setup Guide

### Finding Your Calendar ID

#### For Primary Calendar:

```bash
GOOGLE_CALENDAR_ID=primary
```

#### For Other Calendars:

1. Go to [Google Calendar](https://calendar.google.com)
2. Click the settings gear (⚙️) → **Settings**
3. In the left sidebar, select the calendar you want to use
4. Scroll down to **Integrate calendar** section
5. Copy the **Calendar ID**

   - Example: `work@group.calendar.google.com`
   - Or: `abc123def456@group.calendar.google.com`

6. Add to your `.env` file:

```bash
GOOGLE_CALENDAR_ID=work@group.calendar.google.com
```

### Multiple Calendar Strategy

**Option 1: Different MCP Servers**

```json
{
  "mcpServers": {
    "obsidian-work": {
      "command": "/path/to/.venv/bin/obsidian-mcp",
      "env": {
        "OBSIDIAN_VAULT_PATH": "/path/to/vault",
        "GOOGLE_CALENDAR_ID": "work@group.calendar.google.com"
      }
    },
    "obsidian-personal": {
      "command": "/path/to/.venv/bin/obsidian-mcp",
      "env": {
        "OBSIDIAN_VAULT_PATH": "/path/to/vault",
        "GOOGLE_CALENDAR_ID": "primary"
      }
    }
  }
}
```

**Option 2: Change .env and Restart**

- Edit `.env` to switch calendars
- Restart Claude Desktop
- Simpler but requires manual switching

### Obsidian URL Configuration

The `OBSIDIAN_VAULT_URL_BASE` creates deep links from calendar events to notes.

**Find Your Vault Name:**

1. Open Obsidian
2. Go to Settings (⚙️) → About
3. Look for your vault name

**Configure:**

```bash
# Format: obsidian://open?vault=VAULT_NAME&file=
OBSIDIAN_VAULT_URL_BASE=obsidian://open?vault=MyVault&file=
```

**Important:** Match the exact vault name including spaces and capitalization.

## Using Calendar Tools

### Available Tools

1. **`create_calendar_event`** - Create event linked to note
2. **`list_calendar_events`** - List upcoming events
3. **`get_calendar_event`** - Get specific event details
4. **`search_calendar_events`** - Search by text or date range
5. **`update_calendar_event`** - Move/modify events
6. **`delete_calendar_event`** - Delete events

### Create Calendar Event

```
Tool: create_calendar_event
Parameters:
- note_path: "Projects/Meeting.md"
- title: "Team Standup"
- date: "2025-01-15"
- time: "14:00"
- duration_minutes: 30
- description: "Weekly team sync"
- confirm: true  # Required!
```

**What Happens:**

1. Event created in Google Calendar
2. Note frontmatter updated with event details:
   ```yaml
   ---
   calendar_event_id: "abc123..."
   calendar_event_link: "https://www.google.com/calendar/event?eid=..."
   calendar_event_date: "2025-01-15"
   calendar_event_time: "14:00"
   ---
   ```
3. Event description includes `obsidian://` link to note

### List Upcoming Events

```
Tool: list_calendar_events
Parameters:
- max_results: 10
- days_ahead: 7
```

Shows which events have linked notes.

### Search Events

```
Tool: search_calendar_events
Parameters:
- query: "standup"
- date_from: "2025-01-01"
- date_to: "2025-01-31"
- max_results: 20
```

### Update/Move Event

```
Tool: update_calendar_event
Parameters:
- event_id: "abc123..."
- date: "2025-01-16"  # New date
- time: "15:00"       # New time
- title: "Team Standup (Rescheduled)"  # Optional
- confirm: true  # Required!
```

**Note:** Preserves obsidian:// link and updates note frontmatter automatically.

### Delete Event

```
Tool: delete_calendar_event
Parameters:
- event_id: "abc123..."
- update_note: true  # Remove event data from note
- confirm: true  # Required!
```

### Confirmation Requirement

All create/update/delete operations require `confirm: true` for safety.

**How it works:**

1. Claude calls tool with `confirm: false` (default)
2. Tool returns error: "requires explicit confirmation"
3. Claude asks you: "Should I proceed?"
4. You say "yes"
5. Claude retries with `confirm: true`
6. Operation succeeds

This prevents accidental calendar modifications.

## Workflows

### Workflow 1: Meeting Prep with Calendar Event

```
You: "Create a note for tomorrow's standup at 2pm"

Claude:
1. Creates note "Daily Notes/2025-01-15 Standup.md"
2. Asks: "Should I create a calendar event?"
3. You: "Yes"
4. Creates calendar event linked to note
5. Event appears in Google Calendar with deep link
```

### Workflow 2: Reschedule Meeting

```
You: "Move tomorrow's standup to 3pm"

Claude:
1. Searches for "standup" events tomorrow
2. Finds event
3. Asks: "Should I update this event?"
4. You: "Yes"
5. Updates calendar event
6. Updates note frontmatter with new time
```

### Workflow 3: Daily Planning

```
You: "Show me my events for this week"

Claude:
1. Lists all events for next 7 days
2. Shows which have linked notes (📝)
3. You can click obsidian:// links in calendar to open notes
```

### Workflow 4: Event Review and Cleanup

```
You: "Find all standup meetings this month"

Claude:
1. Searches calendar for "standup"
2. Shows all matching events
3. You can selectively delete or update them
```

## Security Model

### OAuth Scope

**Scope:** `https://www.googleapis.com/auth/calendar.events`

**What it grants:**

- ✅ Read/write events in ALL your calendars
- ❌ Cannot modify calendar settings
- ❌ Cannot share calendars
- ❌ Cannot delete calendars

**Why this scope?**

- Google doesn't offer per-calendar event scopes
- This is the most restrictive scope for event operations
- Better than `.calendar` (full calendar access)

### Application-Level Scoping

**All calendar operations are restricted to your configured calendar only.**

Even though OAuth grants access to all calendars, the MCP server only operates on the calendar specified in your `GOOGLE_CALENDAR_ID` setting. Events in other calendars cannot be read, modified, or deleted through this server.

### Token Security

**Token file:** `.credentials/token.json`

- Auto-created on first authorization
- Permissions: `600` (owner read/write only)
- Gitignored automatically
- Contains refresh token for auto-renewal

**Credentials file:** `credentials.json`

- Your OAuth2 client credentials from Google
- Gitignored automatically
- Keep this secure!

### Best Practices

1. **Use dedicated calendar** for Obsidian events (e.g., "Obsidian" or "Notes")
2. **Don't share credentials.json** - it's tied to your Google Cloud project
3. **Revoke access** if token compromised: [Google Account Permissions](https://myaccount.google.com/permissions)
4. **Regular audits** - Review calendar events periodically
5. **Separate MCP servers** for work/personal if needed

## Troubleshooting

### Calendar Not Authorized

**Symptoms:**

- "Calendar credentials not found" error
- No browser opens for OAuth

**Solutions:**

1. Check `GOOGLE_CALENDAR_CREDENTIALS_PATH` is set correctly
2. Verify `credentials.json` exists at that path
3. Ensure file has read permissions
4. Try deleting `.credentials/token.json` and re-authorizing

### Wrong Calendar Modified

**Symptoms:**

- Events appear in wrong calendar
- Can't find created events

**Solutions:**

1. Verify `GOOGLE_CALENDAR_ID` in `.env`:
   ```bash
   cat .env | grep GOOGLE_CALENDAR_ID
   ```
2. Check calendar ID is correct (see [Finding Calendar ID](#finding-your-calendar-id))
3. Restart MCP server after changing `.env`
4. Verify calendar exists and is accessible in Google Calendar

### Can't Find Calendar ID

**Solution:**

1. Go to [Google Calendar](https://calendar.google.com)
2. Settings (⚙️) → Settings
3. Left sidebar: Click your calendar name
4. Scroll to "Integrate calendar"
5. Copy Calendar ID

**If still not found:**

- Try using `primary` for your main calendar
- Check if calendar is shared with you (shared calendars have different IDs)
- Ensure calendar isn't deleted or hidden

### Permission Denied

**Symptoms:**

- "Insufficient permission" errors
- Can't create/update events

**Solutions:**

1. Re-authorize with correct scope:
   ```bash
   rm .credentials/token.json
   # Use calendar tool again to re-authorize
   ```
2. Check OAuth consent screen has `calendar.events` scope
3. Verify you have edit permissions on the calendar

### Events Not Syncing

**Symptoms:**

- Changes don't appear in Google Calendar
- Delays in sync

**Solutions:**

1. Check internet connection
2. Try refreshing Google Calendar
3. Verify token hasn't expired:
   ```bash
   ls -la .credentials/token.json
   ```
4. Re-authorize if token is old (>7 days without use)

### Obsidian Links Not Working

**Symptoms:**

- Clicking calendar event link doesn't open note
- "Could not open vault" error

**Solutions:**

1. Verify `OBSIDIAN_VAULT_URL_BASE` matches exact vault name
2. Check Obsidian is installed and vault is open
3. Try opening a note manually with obsidian:// URL
4. Ensure vault name has no typos or wrong capitalization

## FAQ

### Can I use multiple calendars?

Yes, via two approaches:

1. **Multiple MCP servers** (recommended) - See [Multiple Calendar Strategy](#multiple-calendar-strategy)
2. **Switch GOOGLE_CALENDAR_ID** in `.env` and restart Claude Desktop

### Is my calendar data safe?

Yes:

- OAuth token stored locally with restricted permissions
- App-level scoping prevents wrong calendar access
- Credentials never sent to Anthropic
- All operations are logged locally

### Can I limit to read-only?

Not currently, but you can:

1. Only use `list`, `get`, `search` tools
2. Never approve create/update/delete operations
3. File a feature request for read-only mode

### How do I revoke access?

1. Go to [Google Account Permissions](https://myaccount.google.com/permissions)
2. Find your OAuth app name
3. Click "Remove access"
4. Delete `.credentials/token.json` locally

### What if I delete credentials.json?

Download a new one from Google Cloud Console:

1. Go to your project
2. APIs & Services → Credentials
3. Download OAuth client credentials
4. Update `GOOGLE_CALENDAR_CREDENTIALS_PATH`

### Can I use a shared calendar?

Yes! Just use the shared calendar's ID:

1. Find shared calendar ID (see [Finding Calendar ID](#finding-your-calendar-id))
2. Set `GOOGLE_CALENDAR_ID` to that ID
3. Ensure you have edit permissions on the shared calendar

### How do I switch between calendars quickly?

**Option 1:** Use separate MCP servers (one per calendar)
**Option 2:** Create shell script to swap `.env` and restart:

```bash
#!/bin/bash
# switch-calendar.sh
if [ "$1" == "work" ]; then
  export GOOGLE_CALENDAR_ID="work@group.calendar.google.com"
elif [ "$1" == "personal" ]; then
  export GOOGLE_CALENDAR_ID="primary"
fi
# Restart Claude Desktop
killall "Claude"
open -a "Claude"
```

### Does this work with Google Workspace?

Yes! Workspace calendars work the same way:

1. Use your `@yourcompany.com` Google account
2. Find calendar ID from Workspace calendar
3. Configure as normal

### What happens if I change vault names?

Update `OBSIDIAN_VAULT_URL_BASE` to match new vault name, otherwise obsidian:// links won't work.

### Can I see which notes have calendar events?

Search your vault for notes with `calendar_event_id` frontmatter:

```
Tool: search_by_property
Parameters:
- property: "calendar_event_id"
```

## Need More Help?

- **GitHub Issues:** Report bugs or request features
- **README:** Main documentation
- **EXAMPLES.md:** More workflow examples
- **Google Calendar API Docs:** [Calendar API Reference](https://developers.google.com/calendar/api)
