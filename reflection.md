# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

The initial design centers on four classes with clearly separated responsibilities:
Owner acts as the top-level user entity. It holds the owner's identity information and maintains a list of Pet objects. Its only job is to manage the relationship between a user and their animals. It does not know anything about scheduling.
Pet represents a single animal. It stores species, age, and personal details, and owns a list of Task objects. It exposes a get_due_today() helper so the UI layer can quickly filter relevant tasks without touching the scheduler.
Task is the core data unit. It stores what needs to happen (task_type), when it needs to happen (due_datetime), how urgent it is (priority), and whether it repeats (is_recurring, recur_interval). It implements __lt__ so tasks can be compared and sorted natively, and next_occurrence() so recurring tasks can generate their own follow-up.
Scheduler is the algorithmic brain of the system. It holds a registry of owners and a min-heap (task_heap) for priority-ordered task retrieval. It is responsible for all cross-cutting logic: conflict detection, recurring task generation, sorting, and filtering to today's agenda. It depends on Owner and Task but never stores pet-specific details directly. It delegates to them.


The three core actions a user should be able to perform are:

Add a pet — The user provides their owner account and a pet's name, species, and age. The system creates a Pet object and registers it under the Owner, making it available for task assignment going forward.
Schedule a task — The user selects a pet, picks a task type (feeding, walk, medication, or vet appointment), sets a due date and time, assigns a priority level, and optionally marks it as recurring with an interval. The Scheduler validates the time slot for conflicts, then inserts the task into the heap and attaches it to the Pet.
View today's tasks — The user requests their daily agenda. The Scheduler pulls all tasks across all pets due within today's date window, sorts them by priority using the heap, and returns a clean ordered list — overdue items flagged, recurring items ready to generate their next occurrence.


**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes, the design changed significantly during implementation. One change I made was adding back-references to make relationships bidirectional.
The original UML had one-way ownership: Owner held a list of Pet, and Pet held a list of Task, but neither Pet nor Task knew where they came from. During implementation, this created a risk of inconsistent state. The Scheduler would have had to pass IDs around manually to figure out which pet or owner a task belonged to. The fix was to add explicit back-references: Pet.owner and Task.pet, so every object in the graph knows its parent. Adding or removing objects now automatically maintains both directions of the relationship.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

My scheduler considers five constraints:

1. **Time** — every task has a `due_datetime`, and this is the primary axis the scheduler organizes around. Two tasks conflict when they fall on the exact same time slot.
2. **Priority** — each task carries a numeric priority where a lower number means higher importance. Priority decides who yields when two tasks collide: the less important task is the one that gets moved.
3. **Owner preferred time window** — an owner can declare the hours they're generally available (for example, 8:00–20:00), and the scheduler will not push a task outside that window.
4. **Per-task allowed time window** — an individual task can have its own tighter window (for example, medication that must happen in the morning), which is respected on top of the owner's window.
5. **Blackout periods** — a task can define spans of time when it must never be scheduled (for example, while the owner is at work).

I decided which mattered most by splitting them into **hard** and **soft** constraints. Time windows and blackout periods are *hard*: the scheduler will fail a task (return a conflict rather than force a bad slot) before it ever violates them, because scheduling a walk at 3 a.m. or during a blackout is simply wrong. Priority is a *soft*, relative rule — it never blocks scheduling, it only decides which task yields in a tie. Time itself is the neutral axis everything else operates on. This ordering means the scheduler always produces a *valid* schedule (never breaking a hard rule) even if that means leaving a hard conflict unresolved for a human to handle.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

One deliberate tradeoff my scheduler makes is using **greedy, local conflict resolution instead of globally optimal scheduling**. When two tasks land on the same time slot, `resolve_conflict()` picks the lower-priority task and pushes it *forward* in fixed 15-minute increments until it finds the first free slot that still satisfies the owner's preferred time window, the task's own allowed window, and any blackout periods. It moves **one** task, only ever **forward**, and stops at the **first** slot that works — it never searches for the arrangement that would minimize total disruption across the whole day.

This means the scheduler can occasionally give up on a conflict it could theoretically solve. For example, it won't pull an earlier task *backward* to make room, and it won't reshuffle two other tasks to open a better slot — so it may report an unresolved conflict even when a smarter global solver would have found a valid layout.

Why that tradeoff is reasonable for this scenario: PawPal is a home pet-care app — a single owner juggling a handful of daily tasks across a few pets, not an airline or an operating room with hundreds of interdependent constraints. At that scale, three things matter more than mathematical optimality:

1. Predictability and explainability. "Your 8:00 walk was bumped to 8:15 because it's lower priority than Milo's medication" is something a pet owner immediately understands. Every shift is recorded as an `auto_reschedule` event, so the behavior is auditable. A global optimizer's output ("the solver rearranged four tasks") is harder to trust and reason about.
2. Simplicity and correctness. The greedy approach is a short, testable loop with clear stopping conditions. A full constraint-satisfaction solver would be far more code and far more failure surface — hard to justify for a dozen tasks a day.
3. Graceful degradation. When greedy resolution can't place a task, the system doesn't crash or silently drop it — it reports the conflict (via `conflict_warnings()`) and leaves the human to make the final call. For personal scheduling, keeping a human in the loop on the hard cases is safer than trusting an automated solver to always get it right.


---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

I used an AI coding assistant across every phase of the build: brainstorming the class design, implementing the scheduling algorithms, refactoring, generating tests, and writing documentation. The features I found most effective were:

- **Codebase-aware editing.** Because the assistant could read `pawpal_system.py` directly, its suggestions used my real attributes and method names (`due_datetime`, `filter_tasks`, `resolve_conflict`) instead of generic examples. This made it fast to add a method and immediately wire it into `main.py` and the Streamlit UI.
- **Conceptual "how do I" questions before writing code.** Some of my most useful prompts weren't "write this for me" but "how do you use a lambda as a sort key for `HH:MM` strings?" or "how do you use `timedelta` to calculate today + 1 day accurately?" Getting the concept first meant I understood the code I was accepting.
- **Running and verifying in-loop.** The assistant ran `main.py` and the test suite after changes and pasted the real output, so I could see sorting, filtering, and conflict warnings actually working rather than trusting that they would.
- **Proactive review.** It flagged issues I hadn't asked about — a real bug in `resolve_conflict` where the retry loop never advanced to the next time slot, duplicate method definitions, and a contradiction between my UML notes and the final code.

The most helpful prompts were **small, specific, and scoped to one feature at a time** ("add a method that filters by completion status or pet name," "surface conflicts in `main.py`"), which kept each change reviewable.

**Staying organized with separate sessions.** I used separate chat sessions for different phases of the work — design, core implementation, the scheduling algorithms, and documentation. This kept each session's context focused on one concern, so the assistant's suggestions stayed relevant to the task at hand instead of drifting. It also gave me natural checkpoints: I could finish and verify one phase, commit it, and start the next session with a clean slate rather than one giant thread where earlier decisions muddied later ones. When something from an earlier phase mattered, my own code and commit history — not a sprawling chat log — were the source of truth.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

One example where I modified an AI suggestion to keep my design clean: when I added conflict detection, the assistant offered to extend it into a full **duration/overlap model** — treating two tasks as conflicting whenever their time ranges overlapped, which would have required adding a `duration` field to `Task` and interval-overlap logic. I chose to keep conflict detection **exact-timestamp-only** instead. For a home pet-care app that schedules a handful of tasks a day, the simpler "same time slot" rule is easy to reason about, easy to test, and matches the tradeoff I document in section 2b; the overlap model would have added real complexity for a problem I don't actually have yet. I made the same call on several other offered extras (date-stamped recurring IDs, an either/or filter mode, cleaning up unrelated code) — accepting them only when they served the design, not just because the AI proposed them.

How I verified suggestions before trusting them:

- **Read the code, didn't just paste it.** For the `resolve_conflict` refactor, I checked that the described bug (the loop re-testing the same slot) was real before accepting the fix.
- **Ran the tests and the demo.** Every accepted change was confirmed against `python3 main.py` output and the `unittest` suite, and the risky path (a task skipping past occupied slots) got a dedicated regression test.
- **Cross-checked claims against my own model.** When the assistant summarized "how the classes interact" for my UML, I compared it against what I knew I had built and caught where my earlier design notes no longer matched the code.

**What I learned about being the "lead architect."** Working with a powerful AI tool made it clear that the scarce skill is not writing code — it's *judgment*. The assistant could produce a correct method in seconds, but it would just as readily add scope, extra fields, or "nice to have" features that would have bloated the design. My job was to hold the vision: decide what the system should and shouldn't do, say no to reasonable-sounding suggestions that didn't fit, and own the tradeoffs (like exact-time vs. overlap conflicts) rather than defaulting to whatever was offered. The AI is an extremely fast implementer and a useful reviewer, but the architecture, the constraints, and the "is this actually simpler?" question stayed with me — and the quality of the result depended far more on the specificity of my direction and my willingness to verify than on the raw capability of the tool.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

The suite has 48 tests spread across several files, grouped by the behavior they protect:

- **Sorting** — chronological order by `due_datetime`, and `sort_time_strings` correctly handling non-zero-padded values like `"8:30"`.
- **Filtering and queries** — pending queries excluding completed tasks, `get_all_tasks` aggregating across all of an owner's pets, and completed tasks being excluded from both pending lists and conflict checks.
- **Conflict detection** — tasks at the exact same time being flagged as a conflict, and (documented as current behavior) overlapping-but-not-identical times *not* being detected.
- **Conflict resolution** — lower-priority tasks being moved, higher-priority new tasks pushing an existing task instead, resolution respecting time windows (both success and failure), blackout periods preventing a shift, and the key regression test that resolution *advances past occupied slots* rather than retrying the same one.
- **Recurrence** — completing a task spawning its next occurrence, frequency-only tasks spawning via `complete_task`, unsupported frequencies (e.g. "monthly") returning `None`, and spawned tasks respecting windows/conflicts.
- **Time windows** — inclusive start/end hours, minutes past the end hour, and overnight windows that wrap past midnight.
- **Overdue and edge cases** — the overdue boundary, completed tasks never being overdue, unknown owners returning empty lists instead of raising, and accessors working on an empty schedule.
- **Relationships and logging** — owner↔pet back-references being established, and an `auto_reschedule` event being logged when a task is moved.

These tests were important because the scheduling logic is the part of the system most likely to break silently — a sort key, a boundary condition, or a conflict shift can be subtly wrong and still "look" fine in the UI. Writing tests around the exact behaviors (especially the priority-resolution and time-window edges) turned AI-generated code into code I could actually trust. Several tests deliberately document *current limitations* rather than asserting ideal behavior, so those gaps are recorded and won't surprise a future reader.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

**Confidence: high for the core, moderate for the edges.** All 48 tests pass and cover sorting, filtering, recurrence, conflict detection/resolution, and time-window logic — including three previously-latent bugs that are now fixed and regression-tested (the `resolve_conflict` loop that never advanced slots, overnight windows, and recurring spawns that bypassed conflict/window checks). I'm confident the everyday flows — add a task, sort the day, warn on a clash, spawn the next daily task — behave correctly.

My confidence is lower on the known design gaps, which the tests document but don't fix: conflict detection is exact-timestamp-only (no task-duration/overlap model), `generate_recurring_tasks` has no generation horizon and can grow unboundedly, and `sort_time_strings` doesn't validate that its inputs are real clock times.

Edge cases I would test next with more time:

- **Timezone-aware and DST datetimes** — everything currently assumes naive local `datetime`, so a spring-forward hour could misbehave.
- **Duration/overlap conflicts** — once a `duration` field exists, two tasks that overlap without starting at the same instant.
- **Multiple simultaneous conflicts** — three or more tasks colliding on one slot, and cascading shifts.
- **Bounded recurrence generation** — a horizon so recurring tasks don't grow without limit.
- **UI-level same-second inserts** — the Streamlit "Add task" flow uses `datetime.now()`, so two quick adds can collide; worth testing that path explicitly.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

I'm most satisfied with the **conflict-resolution logic** and the disciplined, incremental way it was built. Rather than one big scheduling function, the system grew method by method — `sort_by_time`, then `filter_tasks`, then the conflict family (`check_conflict` → `find_conflicts` → `conflict_warnings` → `resolve_conflict`), each added, wired into `main.py`, and verified before moving on. The result is a `Scheduler` with a clear separation of concerns: `Task` and `Pet` are clean data objects, and the `Scheduler` owns all the cross-cutting logic. I'm also proud that conflict handling has three deliberate tiers — strict (`add_task` raises), structured (`find_conflicts`), and lightweight (`conflict_warnings` never crashes) — so callers can choose how strict they need to be.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

A few things I'd redesign with another pass:

- **Model task duration.** The single biggest limitation is that conflicts are exact-timestamp-only. Adding a `duration` field and interval-overlap detection would make the scheduler realistic — a 30-minute walk and a feeding 10 minutes later genuinely conflict, but the system can't see that today.
- **Bound recurrence generation.** `generate_recurring_tasks` can grow without limit; I'd add a horizon (e.g. "generate occurrences through the next 7 days").
- **Clean up code duplication.** `Owner.get_all_tasks` and `Scheduler.get_overdue_tasks` are each defined twice (the second silently wins), and a few older Scheduler methods have docstrings placed after their guard clauses so Python doesn't register them. These are harmless but sloppy and should be tidied.
- **Validate inputs and handle timezones.** `sort_time_strings` should reject non-time strings, and the datetime handling should become timezone-aware.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

The most important thing I learned is that **with a powerful AI assistant, the bottleneck shifts from writing code to directing and verifying it.** The assistant could implement almost anything I asked in seconds — but the quality of the system depended on *my* decisions: keeping the scope tight, saying no to reasonable-sounding features that would have complicated the design, owning the tradeoffs, and confirming each change against tests and real output before trusting it. Being the "lead architect" meant treating the AI as a fast, capable collaborator while keeping the vision, the constraints, and the final judgment firmly with me.
