# Calendar Integration Examples

Real-world workflows and examples for using Google Calendar with Obsidian MCP.

## Table of Contents

- [Meeting Management](#meeting-management)
- [Daily Planning](#daily-planning)
- [Event Organization](#event-organization)
- [Advanced Workflows](#advanced-workflows)

## Meeting Management

### Example 1: Create Meeting Note with Calendar Event

**Scenario:** You have a meeting tomorrow at 2pm and want to prep notes.

**Conversation:**
```
You: "Create a meeting note for tomorrow's product review at 2pm, 1 hour long"

Claude:
1. What should I title the note?

You: "Product Review - Q1 Features"

Claude:
2. Creates note at "Meetings/2025-01-16 Product Review.md"
3. Should I create a calendar event for this meeting?

You: "Yes"

Claude:
4. Creates calendar event:
   - Title: "Product Review - Q1 Features"
   - Date: 2025-01-16
   - Time: 14:00
   - Duration: 60 minutes
   - Description includes obsidian:// link to note
5. Updates note frontmatter with calendar event details

Result:
✅ Note created with meeting agenda template
✅ Calendar event created and linked
✅ Click event in Google Calendar → Opens note in Obsidian
```

**Note Content:**
```markdown
---
calendar_event_id: "abc123def456"
calendar_event_link: "https://www.google.com/calendar/event?eid=..."
calendar_event_date: "2025-01-16"
calendar_event_time: "14:00"
---

# Product Review - Q1 Features

## Agenda
-

## Notes
-

## Action Items
-
```

### Example 2: Reschedule Meeting

**Scenario:** Product review needs to move to 3pm.

**Conversation:**
```
You: "Move tomorrow's product review to 3pm"

Claude:
1. Searching for product review events tomorrow...
2. Found event: "Product Review - Q1 Features" at 2:00pm
3. Should I update this event to 3:00pm?

You: "Yes"

Claude:
4. Updates calendar event to 3:00pm
5. Updates note frontmatter:
   calendar_event_time: "15:00"

Result:
✅ Calendar event rescheduled
✅ Note frontmatter updated
✅ All links still work
```

### Example 3: Add Meeting Details Later

**Scenario:** You created a note but forgot to add calendar event.

**Conversation:**
```
You: "Add a calendar event for the Product Review note tomorrow at 2pm"

Claude:
1. Creates calendar event linked to existing note
2. Updates note frontmatter with event details

Result:
✅ Existing note now has calendar event
✅ No duplicate notes created
```

## Daily Planning

### Example 4: Morning Planning Routine

**Scenario:** Start your day by reviewing calendar.

**Conversation:**
```
You: "Show me my calendar for today"

Claude:
📅 Events for 2025-01-15:

1. **Team Standup**
   Time: 09:00 - 09:30
   📝 Linked to note

2. **Product Review - Q1 Features**
   Time: 14:00 - 15:00
   📝 Linked to note

3. **Client Call - Acme Corp**
   Time: 16:00 - 16:30

You: "Create a note for the Acme Corp call"

Claude:
1. Creates "Meetings/2025-01-15 Acme Corp Call.md"
2. Should I link this to the calendar event?

You: "Yes, and move it to 4:30pm instead"

Claude:
3. Links note to existing event
4. Updates event to 16:30

Result:
✅ All meetings for today have notes
✅ Can prep for each meeting
```

### Example 5: Week Planning

**Scenario:** Plan your week on Monday morning.

**Conversation:**
```
You: "Show me all my meetings this week"

Claude:
Found 12 events this week:

**Monday (Today):**
- 09:00 Team Standup 📝
- 14:00 Product Review 📝

**Tuesday:**
- 10:00 1:1 with Sarah
- 15:00 Sprint Planning 📝

**Wednesday:**
...

You: "Create notes for all meetings that don't have them"

Claude:
1. Creates note for "1:1 with Sarah"
2. Should I link it to the calendar event?

You: "Yes, do this for all of them"

Claude:
3. Creates and links notes for:
   - 1:1 with Sarah
   - Design Review
   - Board Meeting

Result:
✅ All weekly meetings have linked notes
✅ Ready to prep for the week
```

## Event Organization

### Example 6: Search and Organize Events

**Scenario:** You want to find all standup meetings this month.

**Conversation:**
```
You: "Find all standup meetings in January"

Claude:
Searching calendar for "standup" in January 2025...

Found 20 events:
1. Team Standup - Jan 2, 09:00 📝
2. Team Standup - Jan 3, 09:00 📝
3. Team Standup - Jan 4, 09:00
...

You: "Which ones don't have notes?"

Claude:
Events without linked notes:
- Jan 4, 09:00
- Jan 5, 09:00
- Jan 11, 09:00
...

You: "Create a single note template for daily standups"

Claude:
1. Creates "Templates/Daily Standup.md"
2. You can reference this for future standups
```

### Example 7: Batch Event Management

**Scenario:** Weekly 1:1s need to be rescheduled due to conflict.

**Conversation:**
```
You: "Find all 1:1 with Sarah events this month"

Claude:
Found 4 events:
1. Jan 9, 10:00 📝
2. Jan 16, 10:00 📝
3. Jan 23, 10:00 📝
4. Jan 30, 10:00 📝

You: "Move them all to 11am"

Claude:
1. Updates Jan 9 to 11:00 - Should I proceed?

You: "Yes, do all of them"

Claude:
2. Updates all 4 events to 11:00
3. Updates all linked note frontmatter

Result:
✅ All 1:1s rescheduled
✅ All notes updated
✅ Consistent weekly schedule
```

## Advanced Workflows

### Example 8: Multi-Calendar Meeting Coordination

**Scenario:** You use separate calendars for work and personal.

**Setup:** Two MCP servers configured:
```json
{
  "mcpServers": {
    "obsidian-work": {
      "env": {
        "GOOGLE_CALENDAR_ID": "work@company.com"
      }
    },
    "obsidian-personal": {
      "env": {
        "GOOGLE_CALENDAR_ID": "primary"
      }
    }
  }
}
```

**Conversation:**
```
You: "Add a work meeting tomorrow at 2pm for product review"

Claude (using obsidian-work):
1. Creates event in work@company.com calendar
2. Links to work vault notes

You: "Add a personal appointment tomorrow at 4pm for dentist"

Claude (using obsidian-personal):
1. Creates event in primary calendar
2. Links to personal vault notes

Result:
✅ Work and personal calendars separate
✅ Each has appropriate vault context
✅ No mixing of work/personal events
```

### Example 9: Recurring Event Management

**Scenario:** Weekly team meeting note template.

**Conversation:**
```
You: "Create a template for weekly team meetings"

Claude:
1. Creates "Templates/Team Meeting.md" with structure
2. Each week's meeting can use this template

You: "Create this week's team meeting note using the template"

Claude:
1. Creates "Meetings/2025-01-20 Team Meeting.md"
2. Copies template content
3. Should I create a calendar event?

You: "Yes, Mondays at 9am, 30 minutes"

Claude:
3. Creates calendar event for next Monday 9am

Next week:
You: "Create next week's team meeting note"

Claude:
1. Creates "Meetings/2025-01-27 Team Meeting.md"
2. Uses template
3. Automatically creates calendar event (pattern learned)

Result:
✅ Consistent meeting notes structure
✅ Automatic calendar sync
✅ Historical record of all meetings
```

### Example 10: Event-Driven Note Updates

**Scenario:** Meeting was productive, update note with outcomes.

**Conversation:**
```
You: "Show me today's product review event"

Claude:
Product Review - Q1 Features
Time: 14:00 - 15:00
Linked note: Meetings/2025-01-15 Product Review.md

You: "Update the note with action items:
- Sarah: Implement feature A
- John: Design mockups
- Me: Write specs"

Claude:
1. Updates note in Action Items section
2. Note still linked to calendar event

You: "Also change the event title to 'Product Review - Feature A Approved'"

Claude:
3. Updates calendar event title
4. Preserves obsidian:// link in description

Result:
✅ Meeting notes captured
✅ Calendar reflects outcome
✅ Link integrity maintained
```

### Example 11: Review Past Meetings

**Scenario:** Quarterly review of all product meetings.

**Conversation:**
```
You: "Find all product review meetings in Q4 2024"

Claude:
Searching for "product review" from Oct 1 - Dec 31, 2024...

Found 13 events:
1. Oct 3 - Product Review - Kickoff 📝
2. Oct 10 - Product Review - Sprint 1 📝
3. Oct 17 - Product Review - Sprint 2 📝
...

You: "Create a summary note linking to all of them"

Claude:
1. Creates "Summaries/Q4 2024 Product Reviews.md"
2. Lists all meetings with links:
   - [[2024-10-03 Product Review|Oct 3 - Kickoff]]
   - [[2024-10-10 Product Review|Oct 10 - Sprint 1]]
   ...
3. Includes calendar event links

Result:
✅ Quarterly review documented
✅ All meeting notes linked
✅ Easy navigation to past discussions
```

### Example 12: Smart Event Reminders

**Scenario:** Get reminded about upcoming events with prep notes.

**Conversation:**
```
You: "What's my next meeting?"

Claude:
Your next meeting is in 30 minutes:
Product Review - Feature A Approved
Time: 14:00 - 15:00
📝 Note: Meetings/2025-01-15 Product Review.md

You: "Show me the note"

Claude:
[Displays note content with agenda and action items]

You: "Add a reminder: review the mockups before the meeting"

Claude:
1. Adds to note under Prep section:
   - [ ] Review mockups before meeting

Result:
✅ Pre-meeting preparation
✅ Context for upcoming events
✅ Actionable reminders
```

## Best Practices

### Template Strategy

Create templates for recurring meeting types:
- `Templates/1-1.md` - One-on-one meetings
- `Templates/Team Meeting.md` - Team standups/meetings
- `Templates/Client Call.md` - Client meetings
- `Templates/Review.md` - Review sessions

### Naming Convention

Consistent note naming helps organization:
- `YYYY-MM-DD Event Name.md` - Date-first for chronological sorting
- `Category/YYYY-MM-DD Event.md` - Organized by category
- Use folders: `Meetings/`, `Calls/`, `Reviews/`

### Workflow Automation

1. **Morning routine:** List today's events, create missing notes
2. **Weekly planning:** Review week, create all meeting notes
3. **Evening review:** Update event titles to reflect outcomes
4. **Monthly archive:** Summarize key meetings with links

### Calendar Hygiene

1. **Delete or update** events when plans change
2. **Use confirm=true** to prevent accidental changes
3. **Review linked notes** before deleting events
4. **Keep calendar ID** secure and documented

## Troubleshooting Workflows

### Workflow: Event Created in Wrong Calendar

```
Problem: Created event in personal calendar instead of work

Solution:
1. Delete event from wrong calendar:
   Tool: delete_calendar_event
   - event_id: "abc123"
   - confirm: true

2. Switch to correct calendar:
   Edit .env: GOOGLE_CALENDAR_ID=work@company.com
   Restart Claude Desktop

3. Create event in correct calendar:
   Tool: create_calendar_event
   - Same parameters as before
   - confirm: true
```

### Workflow: Lost Calendar Link in Note

```
Problem: Note has calendar_event_id but event was deleted

Solution:
1. Check if event exists:
   Tool: get_calendar_event
   - event_id: "abc123"

2. If not found, clean up note frontmatter:
   Remove calendar_event_* fields manually

3. Create new event if needed:
   Tool: create_calendar_event
   - Link to existing note
```

### Workflow: Multiple Notes for Same Event

```
Problem: Accidentally created two notes for same meeting

Solution:
1. Identify which note to keep (check content quality)

2. Update calendar event to link to correct note:
   Tool: update_calendar_event
   - event_id: "abc123"
   - Keep correct note path in description

3. Delete or merge duplicate note manually

4. Update frontmatter in kept note if needed
```

## Need More Examples?

- Check `docs/CALENDAR.md` for full documentation
- See `README.md` for tool reference
- Ask for specific workflow examples in GitHub issues
