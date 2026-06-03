---
name: youtrack-to-toggl
description: Sync YouTrack tickets where you are Taker to Toggl Track projects. Use this skill whenever the user wants to sync YouTrack issues to Toggl, pull tickets into Toggl for time tracking, update Toggl projects from YouTrack, or archive completed issues. Triggers on phrases like "sync youtrack to toggl", "pull my tickets", "update toggl projects", "sync taker issues".
---

# YouTrack → Toggl Sync

Syncs YouTrack issues (where the user is Taker) to Toggl projects.
- Unresolved → active Toggl project (create or restore)
- Resolved → archive Toggl project (active=false)
- Mapping persisted at `~/.youtrack-toggl-mapping.json`

## Required env vars

| Var | Description |
|-----|-------------|
| `YOUTRACK_BASE_URL` | e.g. `https://youtrack.example.com` |
| `YOUTRACK_TOKEN` or `YOUTRACK_LSDEVTOOLS_TOKEN` | Permanent token |
| `TOGGL_TOKEN` | From toggl.com Profile Settings → API Token |
| `YOUTRACK_TAKER_FIELD` | (optional) Custom field name, default: `Taker` |

## Steps

1. Verify all required env vars are set. For any missing, tell the user exactly which one and where to get it. Do not proceed until all are set.
2. Run the sync:
   ```bash
   python3 ~/.claude/skills/toggl-youtrack-connector/src/sync-to-toggl.py
   ```
3. Report the summary line (created/archived/restored/unchanged counts).
4. If errors occur:
   - `403 YouTrack` → token lacks read permission or wrong base URL
   - `403 Toggl` → TOGGL_TOKEN is wrong — regenerate at toggl.com Profile
   - `0 issues found` → check YOUTRACK_TAKER_FIELD value; try `Assignee` as fallback
   - `YOUTRACK_BASE_URL not set` → set the env var to the YouTrack instance root URL

## Notes

- Safe to re-run: idempotent. Already-correct projects are skipped.
- Archived Toggl projects are restored if the YT issue is reopened.
- Project names in Toggl: `[ISSUE-ID] Issue summary` (truncated at 255 chars).

## Special tickets

Four YouTrack tickets act as catch-all buckets for unmatched Toggl entries (used by `toggl-to-youtrack`):

| Key | Scope |
|-----|-------|
| **BAU** (Business as usual) | Keeping existing systems running: prod bug fixes, releases, security/compliance, crawling, bookmaker maintenance. Meetings: component team groomings, retros, release reviews, quarterly reports. |
| **Overhead** | Company-wide/team-level non-productive activities: Smart Fridays, Flash Talks, 1:1s, all-hands, onboarding, admin, hiring. |
| **Upskilling** | Personal study, conferences, workshops, AI Ambassadors, internal AI workshops. |
| **Time Off** | Vacation, illness, doctor visits. State holidays and weekends not needed. |

Their YouTrack IDs are cached in `~/.youtrack-toggl-mapping.json` under `special_tickets.bau`, `.overhead`, `.upskilling`, `.time_off`.

## Rotating service ticket

Each month a new FSWEB ticket tagged `#service-ticket` is created; the previous month's is resolved.

The sync automatically:
- Finds the single open `project: FSWEB tag: service-ticket #Unresolved` issue
- Creates its Toggl project (or restores if archived)
- When rotation detected (cached ID differs from current open ticket) → archives the old Toggl project

Cached under `special_tickets.service_ticket` as `{"yt_id": "FSWEB-XXXXX", "toggl_project_id": 123456}`.

No manual action needed on rotation — next sync handles it.
