# Ralph

Based on the tweet https://x.com/ryancarson/status/2008548371712135632

Add claude code `dev-browser` skill https://github.com/SawyerHood/dev-browser

```bash
/plugin marketplace add sawyerhood/dev-browser
/plugin install dev-browser@sawyerhood/dev-browser
```

note: Using this skill i Ralph loops may not be suitable for some projects. Using dev-browser skill may require to spin up a dev server (a.k.a. long running task) that will prevent Ralph loops from progressig smoothly

## How It Works

A bash loop that:

- Pipes a prompt into your AI agent
- Agent picks the next story from prd.json
- Agent implements it
- Agent runs typecheck + tests
- Agent commits if passing
- Agent marks story done
- Agent logs learnings
- Loop repeats until done

Memory persists only through:

- Git commits
- `progress.txt` (learnings)
- `prd.json` (task status)

## File Structure

```
scripts/ralph/
├── ralph.sh
├── prompt.md
├── prd.json
└── progress.txt
```

## ralph.sh

The loop:

```bash
#!/bin/bash
set -e

MAX_ITERATIONS=${1:-10}
SCRIPT_DIR="$(cd "$(dirname \
  "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting Ralph"

for i in $(seq 1 $MAX_ITERATIONS); do
echo "═══ Iteration $i ═══"

OUTPUT=$(cat "$SCRIPT_DIR/prompt.md" \
 | amp --dangerously-allow-all 2>&1 \
 | tee /dev/stderr) || true

if echo "$OUTPUT" | \
 grep -q "<promise>COMPLETE</promise>"
then
echo "✅ Done!"
exit 0
fi

sleep 2
done

echo "⚠️ Max iterations reached"
exit 1
```

Make executable:

```bash
chmod +x scripts/ralph/ralph.sh
```

## prompt.md

Instructions for each iteration:

```markdown
# Ralph Agent Instructions

## Your Task

1. Read `scripts/ralph/prd.json`
2. Read `scripts/ralph/progress.txt`
   (check Codebase Patterns first)
3. Check you're on the correct branch
4. Pick highest priority story
   where `passes: false`
5. Implement that ONE story
6. Run typecheck and tests
7. Update AGENTS.md files with learnings
8. Commit: `feat: [ID] - [Title]`
9. Update prd.json: `passes: true`
10. Append learnings to progress.txt

## Progress Format

APPEND to progress.txt:

## [Date] - [Story ID]

- What was implemented
- Files changed
- **Learnings:**
  - Patterns discovered
  - Gotchas encountered

---

## Codebase Patterns

Add reusable patterns to the TOP
of progress.txt:

## Codebase Patterns

- Migrations: Use IF NOT EXISTS
- React: useRef<Timeout | null>(null)

## Stop Condition

If ALL stories pass, reply:
<promise>COMPLETE</promise>

Otherwise end normally.
```

## prd.json

Your task list:

```json
{
  "branchName": "ralph/feature",
  "userStories": [
    {
      "id": "US-001",
      "title": "Add login form",
      "acceptanceCriteria": [
        "Email/password fields",
        "Validates email format",
        "typecheck passes"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

Key fields:

- `branchName` — branch to use
- `priority` — lower = first
- `passes` — set true when done

## progress.txt

Start with context:

```markdown
# Ralph Progress Log

Started: 2024-01-15

## Codebase Patterns

- Migrations: IF NOT EXISTS
- Types: Export from actions.ts

## Key Files

- db/schema.ts
- app/auth/actions.ts

---
```

Ralph appends after each story. Patterns accumulate across iterations.

## Running Ralph

```bash
./scripts/ralph/ralph.sh 25
```

Runs up to 25 iterations. Ralph will:

- Create the feature branch
- Complete stories one by one
- Commit after each
- Stop when all pass

## Critical Success Factors

### 1. Small Stories

Must fit in one context window.

```
❌ Too big:
"Build entire auth system"

✅ Right size:
"Add login form"
"Add email validation"
"Add auth server action"
```

### 2. Feedback Loops

Ralph needs fast feedback:

- `npm run typecheck`
- `npm test`

Without these, broken code compounds.

### 3. Explicit Criteria

```
❌ Vague:
"Users can log in"

✅ Explicit:
- Email/password fields
- Validates email format
- Shows error on failure
- typecheck passes
- Verify at localhost:$PORT/login (PORT defaults to 3000)
```

### 4. Learnings Compound

By story 10, Ralph knows patterns from stories 1-9.

Two places for learnings:

- `progress.txt` — session memory for Ralph iterations
- `AGENTS.md` — permanent docs for humans and future agents

Before committing, Ralph updates AGENTS.md files in directories with edited files if it discovered reusable patterns (gotchas, conventions, dependencies).

### 5. AGENTS.md Updates

Ralph updates AGENTS.md when it learns something worth preserving:

```
✅ Good additions:
- "When modifying X, also update Y"
- "This module uses pattern Z"
- "Tests require dev server running"

❌ Don't add:
- Story-specific details
- Temporary notes
- Info already in progress.txt
```

### 6. Browser Testing

For UI changes, use the dev-browser skill by @sawyerhood. Load it with `Load the dev-browser skill`, then:

```bash
# Start the browser server
~/.config/amp/skills/dev-browser/server.sh &
```

## Common Gotchas

### Idempotent migrations

```sql
ADD COLUMN IF NOT EXISTS email TEXT;
```

### Interactive prompts

```bash
echo -e "\n\n\n" | npm run db:generate
```

### Schema changes

After editing schema, check:

- Server actions
- UI components
- API routes

### Fixing related files is OK

If typecheck requires other changes, make them. Not scope creep.

## Monitoring

```bash
# Story status
cat scripts/ralph/prd.json | jq '.userStories[] | {id, passes}'

# Learnings
cat scripts/ralph/progress.txt

# Commits
git log --oneline -10
```

## Real Results

We built an evaluation system:

- 13 user stories
- ~15 iterations
- 2-5 min each
- ~1 hour total

Learnings compound. By story 10, Ralph knew our patterns.

## When NOT to Use

- Exploratory work
- Major refactors without criteria
- Security-critical code
- Anything needing human review
