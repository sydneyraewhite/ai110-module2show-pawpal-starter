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

1. **Predictability and explainability.** "Your 8:00 walk was bumped to 8:15 because it's lower priority than Milo's medication" is something a pet owner immediately understands. Every shift is recorded as an `auto_reschedule` event, so the behavior is auditable. A global optimizer's output ("the solver rearranged four tasks") is harder to trust and reason about.
2. **Simplicity and correctness.** The greedy approach is a short, testable loop with clear stopping conditions. A full constraint-satisfaction solver would be far more code and far more failure surface — hard to justify for a dozen tasks a day.
3. **Graceful degradation.** When greedy resolution can't place a task, the system doesn't crash or silently drop it — it reports the conflict (via `conflict_warnings()`) and leaves the human to make the final call. For personal scheduling, keeping a human in the loop on the hard cases is safer than trusting an automated solver to always get it right.

In short, I traded *optimality* for *simplicity, transparency, and safe failure* — the right priority for a small-scale, human-facing pet-care tool.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
