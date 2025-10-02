# Batch Operations Guide

Complete guide to using batch operations for editing multiple notes atomically in Obsidian MCP.

## Table of Contents

- [Overview](#overview)
- [Available Tools](#available-tools)
- [Safety Features](#safety-features)
- [Usage Examples](#usage-examples)
- [Backup & Recovery](#backup--recovery)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Batch operations allow you to edit multiple notes in a single atomic operation with automatic backup and rollback. This is much more reliable than editing notes one-by-one.

### Why Use Batch Operations?

**Single Note Edits (Sequential):**

```
❌ Edit note 1 → ✓ Success
❌ Edit note 2 → ✓ Success
❌ Edit note 3 → ✗ FAILS
Result: Notes 1 & 2 changed, note 3 unchanged (inconsistent state)
```

**Batch Operations (Atomic):**

```
✅ Batch edit notes 1, 2, 3
   - Creates backup first
   - Attempts all edits
   - If ANY fail → Automatically rolls back ALL changes
Result: Either all notes updated or none (consistent state)
```

### Key Benefits

1. **Atomic** - All-or-nothing updates
2. **Safe** - Automatic backup before changes
3. **Fast** - Single MCP call instead of many
4. **Recoverable** - Manual rollback anytime
5. **Dry-run** - Preview changes before applying

### Batch Size Limits

**Maximum batch size: 50 notes per operation**

This limit prevents server timeouts and ensures responsive performance. For larger updates:

- Split into multiple batches of 50 or fewer
- Process sequentially (each batch is still atomic)
- Monitor logs to track progress

### Performance

Batch operations run in the background for better performance:

- Multiple files are processed at the same time
- Backup and restore of 50 files typically completes in under 1 second
- You can continue using other tools while batch operations run
- The 50-note limit ensures operations complete reliably

## Available Tools

### `batch_update_notes`

Update multiple notes atomically.

**Parameters:**

- `updates` (list[dict]): List of `{path, content}` objects
- `dry_run` (bool): Preview changes without applying (default: false)
- `confirm` (bool): Must be true to apply (default: false)

**Example:**

```json
{
  "updates": [
    { "path": "note1.md", "content": "New content for note 1" },
    { "path": "Projects/note2.md", "content": "Updated content" }
  ],
  "dry_run": false,
  "confirm": true
}
```

### `batch_append_notes`

Append content to multiple notes atomically.

**Parameters:**

- `appends` (list[dict]): List of `{path, content}` objects
- `confirm` (bool): Must be true to apply

**Example:**

```json
{
  "appends": [
    { "path": "Daily/2025-01-15.md", "content": "\n## New Section\n..." },
    { "path": "Daily/2025-01-16.md", "content": "\n## New Section\n..." }
  ],
  "confirm": true
}
```

### `restore_batch_backup`

Restore notes from a batch backup (undo operation).

**Parameters:**

- `backup_id` (string): Backup timestamp (e.g., "20250115_143025")

**Example:**

```json
{
  "backup_id": "20250115_143025"
}
```

### `list_batch_backups`

List available batch backups.

**Parameters:**

- `limit` (number): Max backups to show (default: 10)

## Safety Features

### 1. Automatic Backup

Every batch operation creates a timestamped backup **before** making any changes:

```
.batch_backups/
├── 20250115_143025/    # Backup from Jan 15, 2:30pm
│   ├── note1.md
│   └── Projects/note2.md
└── 20250115_153512/    # Backup from Jan 15, 3:35pm
    ├── Daily/2025-01-15.md
    └── Daily/2025-01-16.md
```

### 2. Automatic Rollback

If **any** update fails, **all** changes are automatically rolled back:

```
1. Create backup
2. Update note 1 → ✓ Success
3. Update note 2 → ✓ Success
4. Update note 3 → ✗ FAILS
5. Restore from backup (undo notes 1 & 2)
6. Return error with details
```

### 3. Confirmation Required

All batch operations require `confirm=true` to prevent accidents:

```python
# Without confirm
batch_update_notes(updates=[...])
→ Error: Requires explicit confirmation

# With confirm
batch_update_notes(updates=[...], confirm=True)
→ Proceeds with update
```

### 4. Dry-Run Preview

Preview changes before applying (batch_update_notes only):

```python
batch_update_notes(updates=[...], dry_run=True)
→ Shows preview of what will change

batch_update_notes(updates=[...], dry_run=False, confirm=True)
→ Applies changes
```

### 5. Backup Preservation

Backups are kept even after successful updates for manual recovery.

## Usage Examples

### Example 1: Tag Cleanup Across Vault

**Scenario:** Change `#old-tag` to `#new-tag` in all notes.

**Workflow:**

```
You: "Find all notes with #old-tag"

Claude:
1. Searches vault
2. Finds 47 notes with #old-tag

You: "Replace #old-tag with #new-tag in all of them"

Claude:
1. Prepares batch update with 47 notes
2. Calls batch_update_notes with dry_run=True
3. Shows preview of changes
4. Asks: "Should I proceed?"

You: "Yes"

Claude:
5. Calls batch_update_notes with confirm=True
6. Creates backup: 20250115_143025
7. Updates all 47 notes
8. Returns success message
```

**Result:**

- All 47 notes updated atomically
- Backup preserved at `.batch_backups/20250115_143025/`
- Can rollback anytime if needed

### Example 2: Add Frontmatter to Multiple Notes

**Scenario:** Add `status: published` to all notes in Projects folder.

**Workflow:**

```
You: "Add status: published to frontmatter of all notes in Projects/"

Claude:
1. Lists notes in Projects/
2. Finds 23 notes
3. Prepares batch update adding frontmatter
4. Previews changes (dry_run)
5. Gets confirmation
6. Updates all atomically

Result: ✅ Successfully updated 23 notes
Backup: .batch_backups/20250115_150030/
```

### Example 3: Append Daily Summary

**Scenario:** Add daily summary template to all notes this week.

**Workflow:**

```
You: "Add a daily summary section to all daily notes this week"

Claude:
1. Lists daily notes for this week (7 notes)
2. Prepares append operation
3. Asks for confirmation

You: "Yes"

Claude:
4. Uses batch_append_notes
5. Appends summary template to all 7 notes
6. Creates backup

Result: ✅ Appended to 7 notes
Backup: .batch_backups/20250115_160500/
```

### Example 4: Rollback After Mistake

**Scenario:** Batch update went wrong, need to undo.

**Workflow:**

```
You: "That wasn't right, undo the batch update"

Claude:
1. Lists recent backups
2. Shows most recent: 20250115_160500 (7 notes)

You: "Restore that backup"

Claude:
3. Calls restore_batch_backup("20250115_160500")
4. Restores all 7 notes

Result: ✅ Restored 7 notes from backup
All changes undone successfully
```

### Example 5: Complex Multi-Step Update

**Scenario:** Standardize frontmatter across research notes.

**Workflow:**

```
You: "Standardize all research notes: add type: research and status: in-progress"

Claude:
1. Searches for notes in Research/ folder
2. Finds 34 notes
3. Reads each note to preserve existing frontmatter
4. Prepares batch update adding new fields
5. Shows dry-run preview

You: "Looks good, apply it"

Claude:
6. Creates backup
7. Updates all 34 notes with new frontmatter
8. Success!

Result: All research notes now have consistent frontmatter
```

## Backup & Recovery

### Automatic Backup Management

**When backups are created:**

- Every batch operation creates a backup first
- Backup ID is timestamp: `YYYYMMDD_HHMMSS`
- Stored in `.batch_backups/` directory
- Excluded from git (in .gitignore)

**What's backed up:**

- Original note content
- Original frontmatter
- File structure preserved

**Backup storage:**

```
vault/
├── .batch_backups/          # Hidden backup directory
│   ├── 20250115_143025/    # Backup ID (timestamp)
│   │   ├── note1.md
│   │   └── Projects/
│   │       └── note2.md
│   └── 20250115_160500/
│       └── Daily/
│           ├── 2025-01-15.md
│           └── 2025-01-16.md
```

### Manual Recovery

**List available backups:**

```
Tool: list_batch_backups
Result:
  20250115_160500 - 7 notes - 0.15 MB - Created: 2025-01-15 16:05:00
  20250115_143025 - 47 notes - 1.2 MB - Created: 2025-01-15 14:30:25
```

**Restore from backup:**

```
Tool: restore_batch_backup
Parameters: {"backup_id": "20250115_143025"}
Result: ✅ Restored 47 notes
```

### Backup Cleanup

Backups are kept indefinitely by default. To clean up old backups:

**Future enhancement (not yet implemented):**

```python
cleanup_old_backups(days_old=7)
# Removes backups older than 7 days
```

**Manual cleanup:**

```bash
# From vault directory
rm -rf .batch_backups/20250115_*
```

## Best Practices

### 1. Always Use Dry-Run First

For batch_update_notes, preview changes before applying:

```python
# Step 1: Preview
batch_update_notes(updates=[...], dry_run=True)
# Review output

# Step 2: Apply
batch_update_notes(updates=[...], dry_run=False, confirm=True)
```

### 2. Start Small

Test batch operations on a few notes before scaling:

```
Bad:  Update 500 notes immediately
Good: Update 3 notes, verify, then scale to 500
```

### 3. Meaningful Backup Names

While backup IDs are auto-generated, use descriptive update messages:

```python
# Good: Claude will create backup_id + log message
"Updating 47 notes to change tag #old-tag → #new-tag"

# Result logged as:
# backup_id: 20250115_143025
# action: Tag replacement old-tag → new-tag
# notes: 47
```

### 4. Regular Backup Review

Periodically review and clean old backups:

```
Tool: list_batch_backups
Review: Keep recent/important, remove old/unnecessary
```

### 5. Combine with Search

Use search tools to find notes, then batch update:

```
1. search_notes(query="old-tag", limit=100)
2. batch_update_notes with results
```

### 6. Version Control Integration

If vault is in git, batch operations work well with commits:

```bash
# After batch operation
git add .
git commit -m "Batch update: Tag cleanup old-tag → new-tag (47 notes)"
```

## Troubleshooting

### Issue: Batch Size Exceeds Maximum

**Symptoms:**

```
Error: Batch size (75) exceeds maximum (50).
Split into smaller batches to avoid server timeouts.
```

**Solution:**

- Split your updates into batches of 50 or fewer notes
- Process multiple batches sequentially
- Each batch remains atomic

**Example:**

```python
# Instead of updating 100 notes at once:
batch1 = notes[0:50]   # First 50
batch2 = notes[50:100] # Last 50

# Process each batch separately
```

### Issue: Operation Takes Longer Than Expected

**Symptoms:**

- Batch operation seems slow
- Processing more than 50 notes

**Solution:**

1. **Check batch size** - Maximum is 50 notes per batch. Split larger operations into multiple batches of 50 or fewer
2. **For very large updates** - Process in smaller batches of 10-20 notes at a time
3. **Enable logging for troubleshooting** - Add to .env:
   ```
   OBSIDIAN_MCP_LOG_FILE=/tmp/obsidian-mcp.log
   ```
4. **Monitor progress** - Tail the log file:
   ```bash
   tail -f /tmp/obsidian-mcp.log
   ```

### Issue: Batch Update Failed Midway

**Symptoms:**

- Some notes updated, some failed
- Error message shown

**Solution:**

- Automatic rollback already happened
- All notes restored from backup
- Check error message for cause
- Fix issue and retry

**Example:**

```
Result: ❌ Batch update failed - all changes rolled back

Failed updates:
- note3.md: Permission denied
- note5.md: Invalid frontmatter

Backup preserved: .batch_backups/20250115_143025/
```

**Next steps:**

1. Fix permission on note3.md
2. Fix frontmatter in note5.md
3. Retry batch operation

### Issue: Backup Not Found

**Symptoms:**

```
Error: Backup not found: 20250115_143025
```

**Solution:**

1. List available backups: `list_batch_backups`
2. Verify backup ID is correct
3. Check `.batch_backups/` directory exists

### Issue: Out of Disk Space

**Symptoms:**

- Backup creation fails
- Error about disk space

**Solution:**

1. Clean up old backups manually
2. Remove unnecessary `.batch_backups/` directories
3. Retry operation

### Issue: Need to Restore Partial Backup

**Symptoms:**

- Want only some notes from backup, not all

**Solution:**

- Manual restoration:

  ```bash
  cp .batch_backups/20250115_143025/note1.md note1.md
  ```

- Or restore all, then re-update others:
  ```
  1. restore_batch_backup("20250115_143025")
  2. batch_update_notes for notes you want to change
  ```

### Issue: Backup After Successful Update

**Symptoms:**

- Want to create backup of current state
- No batch operation planned

**Solution:**

- Currently requires a batch operation
- Workaround: Use batch_update_notes with empty updates to create backup
- Better: Use git commit or manual backup

## Advanced Usage

### Combining Operations

You can chain multiple batch operations:

```python
# 1. Update frontmatter across vault
batch_update_notes([...])  # Creates backup_1

# 2. Append summary to updated notes
batch_append_notes([...])  # Creates backup_2

# 3. If something wrong, restore either backup
restore_batch_backup(backup_1)  # or
restore_batch_backup(backup_2)
```

### Selective Rollback

If only some notes need rollback:

```bash
# Restore specific notes from backup
cp .batch_backups/20250115_143025/note1.md ./note1.md
cp .batch_backups/20250115_143025/note2.md ./note2.md
```

### Backup Verification

Before important batch operation, verify backup system:

```python
# Test backup/restore cycle
1. batch_update_notes([{"path": "test.md", "content": "test"}], confirm=True)
2. Note backup_id
3. restore_batch_backup(backup_id)
4. Verify test.md restored
```

### Integration with Git

For version-controlled vaults:

```bash
# Before batch operation
git commit -am "Before batch update"

# Run batch operation
# (Creates .batch_backups/20250115_143025/)

# Verify changes
git diff

# If happy, commit
git commit -am "Batch update: Tag cleanup"

# If not happy, git reset or restore backup
git reset --hard HEAD
# or
restore_batch_backup("20250115_143025")
```

## FAQ

### Can I batch update frontmatter only?

Not directly yet. Use `batch_update_notes` with full content:

```python
1. Read each note to get content
2. Modify frontmatter
3. batch_update_notes with updated content+frontmatter
```

Future: `batch_update_frontmatter` tool (coming soon)

### How many notes can I update at once?

**Maximum: 50 notes per batch operation**

This limit ensures:

- Operations complete quickly (typically under 1 second)
- Reliable performance without timeouts
- Server remains responsive

For larger updates, split into multiple batches of 50 notes. Each batch is still atomic and creates its own backup.

### Are backups compressed?

No, backups are full file copies. Future enhancement may add compression.

### Can I schedule automatic backup cleanup?

Not yet. Currently manual only. Future: scheduled cleanup or retention policy.

### Do batch operations work offline?

Yes! All operations are local:

- No network required
- Works entirely within vault
- Backups stored locally

### What happens if MCP server crashes during batch operation?

- Backup already created ✓
- Partial updates may occur
- No automatic rollback (server crashed)
- Manual recovery:
  ```
  1. Check .batch_backups/ for latest backup
  2. restore_batch_backup(latest_backup_id)
  ```

### Can I use batch operations with templates?

Yes! Combine with `create_from_template`:

```python
1. create_from_template for multiple notes
2. batch_update_notes to modify all at once
```

## Need Help?

- **Documentation:** See `README.md` and `docs/EXAMPLES.md`
- **Calendar Integration:** See `docs/CALENDAR.md`
- **Issues:** Report at GitHub repository
- **Examples:** Check `docs/EXAMPLES.md` for more workflows

## Related Documentation

- [Calendar Integration Guide](CALENDAR.md) - Calendar-specific batch operations
- [Workflow Examples](EXAMPLES.md) - More real-world examples
- [Main README](../README.md) - Complete tool reference
