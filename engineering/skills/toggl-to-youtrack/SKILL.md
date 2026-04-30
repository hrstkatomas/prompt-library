---
name: toggl-to-youtrack
description: Sync tracked time from Toggl Track into YouTrack work items. Use this skill whenever the user wants to log hours to YouTrack, submit tracked time, sync Toggl entries to YouTrack, post time to a ticket, or record work items. Triggers on phrases like "sync toggl to youtrack", "log my hours", "post time entries", "submit tracked time", "sync time to youtrack". Also use when the user says things like "log my day", "submit this week's hours", or "sync my time".
---

# Toggl → YouTrack Sync

Reads Toggl time entries for a date range and posts them as work items on the matching YouTrack issues.
- Matches via mapping file built by `youtrack-to-toggl`
- Deduplication: already-synced entry IDs stored in mapping — never double-posts
- Skips running entries (duration < 0) and entries < 1 minute
- Entries without a mapped YouTrack ticket get classified by description and routed to special tickets

## Required env vars

Same as `youtrack-to-toggl`: `YOUTRACK_BASE_URL`, `YOUTRACK_TOKEN` (or `YOUTRACK_LSDEVTOOLS_TOKEN`), `TOGGL_TOKEN`.

## Steps

1. Check mapping file exists at `~/.youtrack-toggl-mapping.json`. If missing, run `youtrack-to-toggl` first.
2. Ask user for date range if not provided. Default is last 7 days.
3. Run the main sync for mapped entries:
   ```bash
   SCRIPT=~/.claude/skills/toggl-youtrack-connector/src/sync-to-youtrack.py

   # Last 7 days (default)
   python3 $SCRIPT

   # Custom number of days
   python3 $SCRIPT --days 14

   # Explicit range
   python3 $SCRIPT --since 2024-01-15 --until 2024-01-31
   ```
4. Handle unmatched entries (see below).
5. Report synced/classified/failed counts. For failures, show the error message.

## Handling unmatched entries

After the main sync, find all Toggl entries in the date range that have `duration > 0`, are NOT in `synced_entries`, and either have no `project_id` or their project isn't in the mapping. These are unmatched entries.

Fetch them:
```bash
# Use %2B for + in timezone offset — curl doesn't URL-encode query params in the URL string,
# so a literal + is interpreted as a space by the API, causing "error parsing date".
START="${START_DATE}T00:00:00%2B00:00"
END="${END_DATE}T23:59:59%2B00:00"
curl -s -H "Authorization: Basic $(echo -n "${TOGGL_TOKEN}:api_token" | base64)" \
  "https://api.track.toggl.com/api/v9/me/time_entries?start_date=${START}&end_date=${END}" | jq .
```

For each unmatched entry, read its `description` and classify it:

### Classification rules

**Overhead** — company-wide and team-level organizational activities  
Keywords (case-insensitive): `smart friday`, `smart thursday`, `flash talk`, `1:1`, `all-hands`, `all hands`, `company event`, `team update`, `onboarding`, `admin`, `hiring`, `interview`, `standup`, `stand-up`, `retrospective`, `retro`, `sprint planning`, `sprint review`, `planning`, `team meeting`, `kickoff`, `kick-off`  
→ Route to user's **overhead** ticket.

**Upskilling** — personal learning, conferences, training  
Keywords: `study`, `conference`, `workshop`, `ai ambassador`, `ai workshop`, `training`, `learning`, `course`, `tutorial`, `reading`, `book club`, `knowledge sharing`, `upskill`  
→ Route to user's **upskilling** ticket.

**Time off** — absence from work  
Keywords: `vacation`, `sick`, `illness`, `doctor`, `time off`, `holiday`, `leave`, `pto`, `day off`, `free day`, `dentist`  
→ Route to user's **time off** ticket.

**Best guess** — if none of the above keywords match, use judgment:
- Does the description name a known project, team, or product area? Find the closest mapped YouTrack issue.
- Does it sound like overhead work (meetings, coordination, reviewing)? Use overhead.
- When genuinely ambiguous, default to overhead and explain why.

Always state the classification reason in the output so the user can verify.

## Finding special tickets

Check the mapping file for cached special ticket IDs under the `special_tickets` key:
```json
{
  "special_tickets": {
    "overhead": "PROJ-123",
    "upskilling": "PROJ-456",
    "time_off": "PROJ-789"
  }
}
```

If not cached, search YouTrack. Try these queries in order until one returns a result:

```bash
# Strip trailing slash to avoid double-slash in URL (YOUTRACK_BASE_URL may end with /)
YT_BASE="${YOUTRACK_BASE_URL%/}"

# Overhead
curl -s -H "Authorization: Bearer $YOUTRACK_TOKEN" -H "Accept: application/json" \
  "${YT_BASE}/api/issues?query=for:+me+Overhead&fields=id,idReadable,summary&\$top=5" | jq .

# Upskilling
curl -s -H "Authorization: Bearer $YOUTRACK_TOKEN" -H "Accept: application/json" \
  "${YT_BASE}/api/issues?query=for:+me+Upskilling&fields=id,idReadable,summary&\$top=5" | jq .

# Time off
curl -s -H "Authorization: Bearer $YOUTRACK_TOKEN" -H "Accept: application/json" \
  "${YT_BASE}/api/issues?query=for:+me+%22Time+off%22&fields=id,idReadable,summary&\$top=5" | jq .
```

If a ticket is not found via search, ask the user to provide the YouTrack issue ID manually. Once found, save all three IDs to `special_tickets` in the mapping file so future runs don't need to search again.

## Posting unmatched entries

Post each unmatched entry to its classified ticket using the YouTrack API, then add its ID to `synced_entries` in the mapping file:

```bash
YT_BASE="${YOUTRACK_BASE_URL%/}"
curl -s -X POST \
  -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  "${YT_BASE}/api/issues/${ISSUE_ID}/timeTracking/workItems" \
  -d "{
    \"date\": ${TIMESTAMP_MS},
    \"duration\": {\"minutes\": ${MINUTES}},
    \"text\": \"Toggl #${ENTRY_ID}: ${DESCRIPTION} [auto-classified: ${REASON}]\"
  }"
```

Save mapping after all entries are processed (not after each one) — unless a failure occurs mid-way, in which case save what succeeded so re-runs don't double-post.

## Output format

```
Fetching Toggl entries: 2024-01-15 → 2024-01-22
  18 total, 12 mapped, 6 unmatched

Mapped sync:
  PROJ-101 +90m "Fix login bug" ... done
  ...
  12 synced, 0 failed

Unmatched entries (classified):
  PROJ-200 (overhead)   +45m "Smart Friday" — keyword: smart friday
  PROJ-200 (overhead)   +30m "1:1 with manager" — keyword: 1:1
  PROJ-201 (upskilling) +60m "AI Ambassador session" — keyword: ai ambassador
  PROJ-202 (time off)   +480m "sick day" — keyword: sick
  PROJ-100 (best guess) +30m "PR review for auth module" — no keyword match; sounds like dev work, routed to closest active project
  PROJ-200 (overhead)   +15m "random admin stuff" — no keyword match; ambiguous, defaulted to overhead

  6 classified, 0 failed

Total: 18 synced
```

## Common errors

- `Mapping file not found` → run youtrack-to-toggl first
- `404 from YouTrack` → issue ID not found (deleted/moved); remove from mapping if stale
- `403 from YouTrack` → token lacks time tracking write permission
- `0 to sync` → all entries already synced, or no entries match tracked projects
- Special ticket not found via search → ask user to provide the YouTrack issue ID manually; save it to `special_tickets` in mapping once confirmed
