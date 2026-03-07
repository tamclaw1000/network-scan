---
name: obsidian-task-manager
description: Manage Obsidian project tasks end-to-end with consistent metadata, badge formatting, URL snapshot summaries, YouTube transcript summaries, and index maintenance. Use when creating, updating, renaming, summarizing, or closing tasks under tasks/projects/* and when keeping both per-project index.md and tasks/projects/PROJECTS.md in sync.
---

# Obsidian Task Manager

Use this workflow for task files in:
- `tasks/projects/<project>/`
- `tasks/projects/<project>/index.md`
- `tasks/projects/PROJECTS.md`

## Create Task

1. Generate filename: `YYYY-MM-DD-<slug>-<id>.md`.
2. Write front matter with required fields:
   - `id`
   - `project`
   - `project_badge`
   - `title`
   - `task_badge`
   - `task_type`
   - `priority`
   - `priority_badge`
   - `status`
   - `status_badge`
   - `due`
   - `tags`
   - `recurrence`
   - `created_at`
   - `updated_at`
3. Add body backlinks:
   - project index: `[[index|...]]`
   - projects master: `[[../PROJECTS|...]]`
4. Add primary checklist item for completion.
5. Add badge-rendered title line in this order:
   - `[project_badge] [task_badge] [priority_badge] [status_badge] Title`

## Badge Rules (Mandatory)

### Order
1. `project_badge`
2. `task_badge`
3. `priority_badge`
4. `status_badge`

### Priority mapping
- `high` → `▲`
- `medium` → `■`
- `low` → `▼`

### Status mapping
- `open` → `◻️`
- `pending` → `🕗`
- `done` → `☑️`
- `dropped` → `✖️`

### Project rule
Keep `project_badge` fixed per project and reuse it for all tasks in that project.

### Task rule
Choose `task_badge` by task theme (examples: `🔐`, `💾`, `🎤`, `🎲`, `🍕`).

## URL Snapshot Rule (Mandatory)

When a URL is provided:
1. Fetch the URL contents.
2. Add a snapshot section with:
   - source URL
   - fetch timestamp
   - concise summary
   - key points
   - actionable takeaways

### YouTube Rule (Mandatory)

When URL is YouTube:
1. Extract transcript when available.
2. Add concise video summary.
3. Add practical takeaways.

## Update Task

1. Update `updated_at` on every edit.
2. Keep checklist state aligned with `status`.
3. Recalculate `priority_badge` when `priority` changes.
4. Recalculate `status_badge` when `status` changes.
5. On completion:
   - set `status: done`
   - set `status_badge: "☑️"`
   - set `completed_at` if schema includes it.

## Rename Task

1. Move file to new slugged filename.
2. Update front matter `title`.
3. Preserve `id`.
4. Preserve historical timestamps unless explicitly requested.
5. Update links in both index files.

## Index Maintenance (Mandatory)

On create/rename/move/close:
1. Update `tasks/projects/<project>/index.md`.
2. Update `tasks/projects/PROJECTS.md`.
3. Prevent duplicates in both files.
4. Keep link target equal to current filename.

## Safety

1. Do not silently overwrite existing task content.
2. Prefer additive edits and explicit state transitions.
3. Do not perform destructive external actions unless explicitly requested.

## Completion Report Format

Report:
- files changed
- key metadata changes
- badge updates
- index updates
- unresolved assumptions
