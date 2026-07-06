# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
# e.g.:
# Daily plan for Biscuit (Golden Retriever):
#   08:00 — Morning walk (30 min) [priority: high]
#   09:00 — Feeding (10 min) [priority: high]
#   ...
```

## 🧪 Testing PawPal+

Run the full test suite from the project root:

```bash
python -m pytest
```

### What the tests cover

The suite exercises the core scheduling behaviors and their edge cases:

- **Sorting correctness** — tasks come back in chronological order (`sort_by_time`), and `"HH:MM"` strings sort correctly even when not zero-padded (`sort_time_strings`). Also pins down that `get_upcoming_tasks` (time-then-priority) and `Task.__lt__`/the heap (priority-then-time) intentionally use different sort keys.
- **Recurrence logic** — completing a daily task spawns the next day's occurrence; `"weekly"`/`recur_interval` variants; unsupported frequencies (e.g. `"monthly"`) return `None`; and recurring spawns respect conflict resolution and their allowed time window.
- **Conflict detection** — same-time clashes are flagged (`check_conflict`, `find_conflicts`, `has_conflicts`), lower-priority tasks are shifted by `resolve_conflict`, and completed tasks are excluded.
- **Time windows** — inclusive start/end boundaries, minutes past the end hour, and overnight windows that wrap past midnight (e.g. `(22, 6)`).
- **Boundaries & safety** — empty schedules, unknown owners, all-completed schedules, and the overdue cutoff at exactly "now".

A few tests are named `..._current_behavior`: these document known limitations (e.g. conflicts match exact timestamps only because there is no task-duration model, and recurring generation has no horizon) rather than endorsing them.

### Sample test run

```text
============================= test session starts ==============================
platform darwin -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/sydneywhite/Documents/GitHub/ai110-module2show-pawpal-starter
plugins: anyio-4.13.0
collected 48 items

tests/test_conflict_resolution.py ..                                     [  4%]
tests/test_core_implementation.py ..                                     [  8%]
tests/test_pawpal.py ....                                                [ 16%]
tests/test_pawpal_system.py ....................................         [ 91%]
tests/test_task_windows_and_events.py ..                                 [ 95%]
tests/test_time_windows.py ..                                            [100%]

============================== 48 passed in 0.04s ==============================
```

### Confidence level

**Reliability: ★★★★☆ (4/5)**

All 48 tests pass, covering sorting, recurrence, conflict detection, and time-window logic — including edge cases and three previously-latent bugs (overnight windows, and recurring spawns bypassing conflict/window checks) that are now fixed and regression-tested. The remaining star is withheld because of known, documented design gaps that are not yet addressed: conflict detection is exact-timestamp-only (no task-duration/overlap model), `generate_recurring_tasks` has no generation horizon (unbounded growth), and `sort_time_strings` does not validate that values are real clock times.


## 📐 Smarter Scheduling

The scheduling logic lives in the `Scheduler` and `Task` classes in [`pawpal_system.py`](pawpal_system.py). This section documents each feature and the method that implements it.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_by_time()`, `Scheduler.sort_time_strings()` | Chronological order by `due_datetime`; string variant handles `"HH:MM"` values |
| Filtering | `Scheduler.filter_tasks()` | Filter by completion status and/or pet name |
| Conflict detection | `Scheduler.check_conflict()`, `Scheduler.find_conflicts()`, `Scheduler.has_conflicts()`, `Scheduler.conflict_warnings()`, `Scheduler.resolve_conflict()` | Detect, report, and auto-resolve same-time clashes |
| Recurring tasks | `Task.next_occurrence()`, `Scheduler.complete_task()`, `Scheduler.generate_recurring_tasks()` | Daily/weekly tasks spawn their next occurrence |

### Sorting behavior

- **`Scheduler.sort_by_time(tasks)`** returns a list of `Task` objects sorted chronologically by their `due_datetime`. It leaves the input list unchanged (returns a new list).
- **`Scheduler.sort_time_strings(times)`** sorts a list of `"HH:MM"` time strings using an `(hour, minute)` integer key, so it stays correct even when values aren't zero-padded (e.g. `"8:30"` sorts before `"14:05"`).
- Related: **`Scheduler.get_upcoming_tasks()`** sorts pending tasks by `(due_datetime, priority)` and returns the next few.

### Filtering behavior

- **`Scheduler.filter_tasks(tasks, completed=None, pet_name=None)`** filters by completion status, pet name, or both. Each filter is optional — passing `completed=False` returns only pending tasks, `pet_name="Milo"` returns only that pet's tasks, and combining them narrows to both. Passing neither returns the list unchanged.

### Conflict detection logic

- **`Scheduler.check_conflict(task, owner)`** tests whether a single incoming task collides with an existing pending task at the same `due_datetime`. Used by `add_task()` before insertion.
- **`Scheduler.find_conflicts(owner_id)`** scans the whole schedule and returns groups of tasks that share the exact same time — across the same pet *or* different pets.
- **`Scheduler.has_conflicts(owner_id)`** is a boolean convenience wrapper over `find_conflicts()`.
- **`Scheduler.conflict_warnings(owner_id)`** returns human-readable warning strings instead of raising, so callers can surface a warning and keep running.
- **`Scheduler.resolve_conflict(task, owner)`** auto-resolves a clash by shifting the lower-priority task forward in fixed increments until it finds a free slot, while respecting owner/task time windows and blackout periods.

### Recurring task logic

- **`Task.next_occurrence()`** returns a fresh `Task` for the next occurrence, deriving the interval from `recur_interval` or from the `frequency` field (`"daily"` → +1 day, `"weekly"` → +7 days).
- **`Scheduler.complete_task(owner_id, pet_id, task_id)`** marks a task complete and, for recurring tasks, automatically creates the next occurrence, attaches it to the pet, and logs the event.
- **`Scheduler.generate_recurring_tasks()`** sweeps all recurring tasks and generates their next occurrences in bulk.

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->