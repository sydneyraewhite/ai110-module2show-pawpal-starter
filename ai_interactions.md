# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agent Workflow (SF7)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I used Claude (Claude Code) as an agent to extend the PawPal+ scheduler beyond the basics and keep the whole project in sync. Across the session I asked it to implement several multi-step features autonomously — sorting, filtering, conflict detection with warnings, daily/weekly recurrence, and a third capability ("next available slot") — and then propagate each change into the demo script, tests, and documentation.

**What did the agent do?**

For each feature it worked end-to-end rather than just writing a single function:

- **Edited `pawpal_system.py`** to add the methods (`sort_by_time`, `sort_time_strings`, `filter_tasks`, `find_conflicts`, `has_conflicts`, `conflict_warnings`, `complete_task`, `find_next_available_slot`) and refactored `resolve_conflict`.
- **Wired each feature into `main.py`** so the behavior could be seen in the terminal, and into the Streamlit UI (`app.py`) using `st.metric`, `st.table`, and `st.warning`/`st.success`.
- **Wrote and ran tests** in `tests/`, then ran `python3 main.py` and the test suite (`pytest` / `unittest`) after changes and pasted the real output back so I could confirm the behavior.
- **Kept docs in sync** — updated `README.md` (Features list, Smarter Scheduling table, Demo Walkthrough), generated a Mermaid UML diagram (`diagrams/uml_final.mmd`) and rendered it to a PNG via `npx @mermaid-js/mermaid-cli`, and drafted the `reflection.md` sections.
- **Handled git** — committed with a descriptive message and pushed to `main`.

**What did you have to verify or fix manually?**

The agent was strong at implementation but needed real oversight:

- **It caught, but I had to approve, behavior changes.** During the `resolve_conflict` refactor it found a real bug (the retry loop never advanced to the next time slot) and proposed a fix that *changed behavior*. I reviewed that the bug was real and that a regression test covered the new behavior before accepting it.
- **A git command mismatch.** I asked it to push directly to `main`, but I was on a feature branch, so the literal commands I gave would have stranded my work. The agent flagged this and asked how to proceed instead of running them blindly — I chose the merge-and-push path.
- **Scope control.** It repeatedly offered extra features (duration/overlap conflicts, date-stamped IDs, a date picker). I had to decide which to accept; I declined most to keep the design simple.
- **Things it flagged for me to fix later.** It pointed out duplicate method definitions (`get_all_tasks`, `get_overdue_tasks` defined twice) and docstrings placed after guard clauses so Python doesn't register them — real issues I still need to clean up.
- **Reflection content is a draft.** The `reflection.md` text it wrote is accurate to the session but needs to be put in my own voice, and it couldn't verify claims about my use of separate chat sessions.

---

## Prompt Comparison (SF11)

> Compare two different prompts (or two different models) on the same task.

### The task

Complex algorithmic task: **rescheduling a weekly recurring task around blackout periods.**

> Prompt: "Given a weekly recurring `Task` with a `due_datetime`, an `allowed_time_window` (start_hour, end_hour), and a list of `blackout_periods` (start, end datetimes), write a function `reschedule_weekly(task, max_weeks=8)` that returns the next weekly occurrence (+7 days each step) that (a) does not fall inside any blackout period and (b) still lands inside the allowed time window. Return `None` if no valid slot is found within `max_weeks`."

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | Claude (Opus, via Claude Code) | _<second model — e.g. Gemini / ChatGPT / Copilot>_ |
| **Prompt** | The prompt above | Same prompt above |
| **Response summary** | Produced a bounded loop that steps +1 week at a time, clamps each candidate back into the allowed window, skips candidates inside a blackout, and returns `None` after `max_weeks` tries. Reused my existing `_clamp_into_window` / `_within_window` helpers instead of re-deriving window math. See code below. | _<paste a 1–2 sentence summary of the other model's answer>_ |
| **What was useful** | Bounded search (can't infinite-loop); reused existing project helpers so it stayed consistent with the codebase; correctly returned `None` instead of raising when no slot exists. | _<what the other model did well>_ |
| **Problems noticed** | Clamping changes the time-of-day when a candidate is out of window, which can silently move a task's time; it doesn't check for conflicts with *other* tasks (only blackouts/windows); assumes naive datetimes (no timezone/DST). | _<what the other model got wrong or missed>_ |
| **Decision** | Chosen as the basis — consistent with the existing `next_occurrence` + window helpers. | _<which one you'd keep>_ |

Claude's (Option A) solution:

```python
def reschedule_weekly(task, max_weeks=8):
    """Next weekly occurrence that avoids blackouts and stays in-window, or None."""
    candidate = task.due_datetime
    for _ in range(max_weeks):
        candidate = _clamp_into_window(candidate + timedelta(weeks=1), task.allowed_time_window)
        in_blackout = any(start <= candidate <= end for start, end in task.blackout_periods)
        if not in_blackout and _within_window(candidate, task.allowed_time_window):
            return candidate
    return None
```

**Which approach did you use in your final implementation and why?**

I used Claude's approach because it fit the existing design — it reuses the `_clamp_into_window` and `_within_window` helpers already in `pawpal_system.py` and mirrors the bounded-loop pattern of `resolve_conflict`, so the code stays consistent and testable. Its main weakness (window-clamping can shift the time-of-day) is a known, documented tradeoff rather than a bug. This solution was adopted into the codebase as `Scheduler.reschedule_weekly()` with tests.

> Note: Option B still needs to be run on a second model and filled in. This template was set up with Claude's real output in Option A; the second column should be completed with the other tool's actual response — not invented — for the comparison to be honest.
