from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional


def _clamp_into_window(dt: datetime, window: Optional[tuple[int, int]]) -> datetime:
    """Snap dt's time-of-day into an inclusive (start_hour, end_hour) window.

    Only non-overnight windows (start <= end) are clamped; when dt falls before
    the start or after the end hour it is moved to the window's start hour on
    the same day. Overnight windows and None are returned unchanged.
    """
    if window is None:
        return dt
    start_h, end_h = window
    if start_h > end_h:
        return dt
    past_end = dt.hour > end_h or (dt.hour == end_h and dt.minute > 0)
    if dt.hour < start_h or past_end:
        return dt.replace(hour=start_h, minute=0, second=0, microsecond=0)
    return dt


@dataclass
class Task:
    task_id: str
    task_type: str
    due_datetime: datetime
    priority: int
    description: str = ""
    is_recurring: bool = False
    recur_interval: Optional[timedelta] = None
    completed: bool = False
    notes: str = ""
    frequency: Optional[str] = None
    pet: Optional["Pet"] = field(default=None, repr=False, compare=False)
    # per-task allowed scheduling window (start_hour, end_hour) inclusive
    allowed_time_window: Optional[tuple[int, int]] = None
    # list of blackout periods where this task cannot be scheduled: (start_dt, end_dt)
    blackout_periods: List[tuple[datetime, datetime]] = field(default_factory=list)

    def __lt__(self, other: "Task") -> bool:
        """Compare tasks by priority, due time, then id."""
        if self.priority != other.priority:
            return self.priority < other.priority
        if self.due_datetime != other.due_datetime:
            return self.due_datetime < other.due_datetime
        return self.task_id < other.task_id

    def next_occurrence(self) -> Optional["Task"]:
        """Return the next occurrence for a recurring/daily/weekly task, or None.

        The interval is taken from `recur_interval` when set; otherwise it is
        derived from `frequency` ("daily" or "weekly"). Returns None when no
        interval can be determined.
        """
        delta = self.recur_interval
        if delta is None and self.frequency is not None:
            freq = self.frequency.lower()
            if freq == "daily":
                delta = timedelta(days=1)
            elif freq == "weekly":
                delta = timedelta(weeks=1)

        if delta is None:
            return None

        next_due = _clamp_into_window(self.due_datetime + delta, self.allowed_time_window)
        return Task(
            task_id=f"{self.task_id}-next",
            task_type=self.task_type,
            due_datetime=next_due,
            priority=self.priority,
            description=self.description,
            is_recurring=self.is_recurring,
            recur_interval=self.recur_interval,
            completed=False,
            notes=self.notes,
            frequency=self.frequency,
            allowed_time_window=self.allowed_time_window,
            blackout_periods=list(self.blackout_periods),
        )

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.completed = True

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        """Return True if the task is overdue and not completed."""
        current_time = now or datetime.now()
        return not self.completed and self.due_datetime < current_time


@dataclass
class Pet:
    pet_id: str
    name: str
    species: str
    age: int
    breed: str = ""
    notes: str = ""
    tasks: List[Task] = field(default_factory=list)
    owner: Optional["Owner"] = field(default=None, repr=False, compare=False)

    def add_task(self, task: Task) -> None:
        """Attach a Task to this Pet and set its back-reference."""
        if task not in self.tasks:
            self.tasks.append(task)
            task.pet = self

    def remove_task(self, task_id: str) -> None:
        """Remove a Task by id and clear its back-reference if present."""
        task_to_remove = next((task for task in self.tasks if task.task_id == task_id), None)
        if task_to_remove is not None:
            self.tasks.remove(task_to_remove)
            task_to_remove.pet = None

    def get_due_today(self) -> List[Task]:
        """Return tasks due today for this pet."""
        today = datetime.now().date()
        return [task for task in self.tasks if task.due_datetime.date() == today]

    def get_pending_tasks(self) -> List[Task]:
        """Return tasks that are not yet completed."""
        return [task for task in self.tasks if not task.completed]

    def get_tasks_by_type(self, task_type: str) -> List[Task]:
        """Return tasks filtered by their task_type."""
        return [task for task in self.tasks if task.task_type == task_type]


@dataclass
class Owner:
    owner_id: str
    name: str
    email: str
    pets: List[Pet] = field(default_factory=list)
    # preferred_time_window is (start_hour, end_hour) in 24h format; inclusive
    preferred_time_window: Optional[tuple[int, int]] = None

    def add_pet(self, pet: Pet) -> None:
        """Add a Pet to this Owner and set the pet's owner reference."""
        if pet not in self.pets:
            self.pets.append(pet)
            pet.owner = self

    def remove_pet(self, pet_id: str) -> None:
        """Remove a Pet by id and clear its owner reference."""
        pet_to_remove = next((pet for pet in self.pets if pet.pet_id == pet_id), None)
        if pet_to_remove is not None:
            self.pets.remove(pet_to_remove)
            pet_to_remove.owner = None

    def get_pet(self, pet_id: str) -> Optional[Pet]:
        """Retrieve a Pet by id, or None if not found."""
        return next((pet for pet in self.pets if pet.pet_id == pet_id), None)

    def get_all_tasks(self) -> List[Task]:
        """Return all tasks belonging to this owner's pets."""
        all_tasks: List[Task] = []
        for pet in self.pets:
            all_tasks.extend(pet.tasks)
        return all_tasks

    def get_tasks_for_today(self) -> List[Task]:
        """Return all tasks due today across the owner's pets."""
        today = datetime.now().date()
        return [task for task in self.get_all_tasks() if task.due_datetime.date() == today]

    def get_all_tasks(self) -> List[Task]:
        tasks: List[Task] = []
        for pet in self.pets:
            tasks.extend(pet.tasks)
        return tasks

    def get_all_pending_tasks(self) -> List[Task]:
        """Return all pending (not completed) tasks for the owner."""
        return [task for task in self.get_all_tasks() if not task.completed]


class Scheduler:
    def __init__(self) -> None:
        self.owners: List[Owner] = []
        self.task_heap: List[Task] = []
        self.event_log: List[dict] = []

    def register_owner(self, owner: Owner) -> None:
        """Register an Owner with the Scheduler."""
        if owner not in self.owners:
            self.owners.append(owner)

    def add_task(self, owner_id: str, pet_id: str, task: Task) -> None:
        owner = self._find_owner(owner_id)
        if owner is None:
            raise ValueError(f"Owner {owner_id} not found")

        pet = owner.get_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet {pet_id} not found for owner {owner_id}")

        """Add a Task to the specified pet, auto-resolving conflicts when possible."""
        if self.check_conflict(task, owner):
            resolved = self.resolve_conflict(task, owner)
            if not resolved:
                raise ValueError("Task conflicts with an existing scheduled task and could not be resolved")

        pet.add_task(task)
        heapq.heappush(self.task_heap, task)
        self.event_log.append({
            "type": "task_added",
            "task_id": task.task_id,
            "pet_id": pet.pet_id,
            "owner_id": owner.owner_id,
            "due_datetime": task.due_datetime.isoformat(),
        })

    def remove_task(self, owner_id: str, pet_id: str, task_id: str) -> None:
        owner = self._find_owner(owner_id)
        if owner is None:
            return

        pet = owner.get_pet(pet_id)
        if pet is None:
            return

        """Remove a Task from the given owner's pet and log the event."""
        pet.remove_task(task_id)
        self.event_log.append({
            "type": "task_removed",
            "task_id": task_id,
            "pet_id": pet.pet_id,
            "owner_id": owner.owner_id,
        })

    def complete_task(self, owner_id: str, pet_id: str, task_id: str) -> Optional[Task]:
        """Mark a task complete, auto-spawning the next occurrence for recurring tasks.

        For "daily"/"weekly" (or otherwise recurring) tasks, a fresh instance is
        created for the next occurrence, attached to the pet, and pushed onto the
        heap. Returns the newly created Task, or None if nothing was spawned.
        """
        owner = self._find_owner(owner_id)
        if owner is None:
            return None

        pet = owner.get_pet(pet_id)
        if pet is None:
            return None

        task = next((t for t in pet.tasks if t.task_id == task_id), None)
        if task is None or task.completed:
            return None

        task.mark_complete()
        self.event_log.append({
            "type": "task_completed",
            "task_id": task.task_id,
            "pet_id": pet.pet_id,
            "owner_id": owner.owner_id,
        })

        next_task = task.next_occurrence()
        if next_task is not None:
            self._schedule_spawn(owner, pet, next_task)
            self.event_log.append({
                "type": "recurring_spawned",
                "task_id": next_task.task_id,
                "from_task_id": task.task_id,
                "pet_id": pet.pet_id,
                "owner_id": owner.owner_id,
                "due_datetime": next_task.due_datetime.isoformat(),
            })
        return next_task

    def get_tasks_for_today(self, owner_id: str) -> List[Task]:
        owner = self._find_owner(owner_id)
        if owner is None:
            return []

        """Return today's tasks for the specified owner, sorted by priority/time."""
        today = datetime.now().date()
        tasks: List[Task] = []
        for pet in owner.pets:
            tasks.extend(task for task in pet.tasks if task.due_datetime.date() == today)

        tasks.sort(key=lambda task: task)
        return tasks

    def get_upcoming_tasks(self, owner_id: str, limit: int = 5) -> List[Task]:
        owner = self._find_owner(owner_id)
        if owner is None:
            return []

        """Return the next `limit` pending tasks for the owner, ordered by time and priority."""
        tasks = [task for task in owner.get_all_tasks() if not task.completed]
        tasks.sort(key=lambda task: (task.due_datetime, task.priority))
        return tasks[:limit]

    def get_overdue_tasks(self, owner_id: str) -> List[Task]:
        owner = self._find_owner(owner_id)
        if owner is None:
            return []

        """Return all overdue tasks for the owner, sorted by priority/time."""
        now = datetime.now()
        overdue = [task for task in owner.get_all_tasks() if task.is_overdue(now)]
        overdue.sort(key=lambda task: task)
        return overdue

    def sort_by_time(self, tasks: List[Task]) -> List[Task]:
        """Return tasks sorted chronologically by their due_datetime."""
        return sorted(tasks, key=lambda task: task.due_datetime)

    def sort_time_strings(self, times: List[str]) -> List[str]:
        """Return "HH:MM" time strings sorted chronologically.

        Handles non-zero-padded values (e.g. "8:30") by comparing on an
        (hour, minute) integer tuple rather than by raw string order.
        """
        return sorted(times, key=lambda t: (int(t.split(":")[0]), int(t.split(":")[1])))

    def filter_tasks(
        self,
        tasks: List[Task],
        completed: Optional[bool] = None,
        pet_name: Optional[str] = None,
    ) -> List[Task]:
        """Filter tasks by completion status and/or pet name.

        Each filter is optional: when `completed` or `pet_name` is None that
        criterion is ignored, so passing neither returns all tasks unchanged.
        """
        result = tasks
        if completed is not None:
            result = [task for task in result if task.completed == completed]
        if pet_name is not None:
            result = [
                task for task in result
                if task.pet is not None and task.pet.name == pet_name
            ]
        return result

    def check_conflict(self, task: Task, owner: Optional[Owner] = None) -> bool:
        """Return True if `task` collides with an existing task at the same due time.

        Checks all of the owner's pending (non-completed) tasks. The owner is
        resolved from the task's back-reference when not passed explicitly;
        returns False when no owner can be determined.
        """
        owner = owner or (task.pet.owner if task.pet is not None else None)
        if owner is None:
            return False

        for pet in owner.pets:
            for existing_task in pet.tasks:
                if existing_task.completed:
                    continue
                if existing_task.due_datetime == task.due_datetime:
                    return True
        return False

    def find_conflicts(self, owner_id: str, include_completed: bool = False) -> List[List[Task]]:
        """Return groups of tasks scheduled at the same time for an owner.

        Each group holds two or more tasks that share the exact same
        due_datetime, whether they belong to the same pet or different pets.
        Groups are ordered chronologically. Completed tasks are ignored unless
        `include_completed` is True.
        """
        owner = self._find_owner(owner_id)
        if owner is None:
            return []

        by_time: dict[datetime, List[Task]] = {}
        for pet in owner.pets:
            for task in pet.tasks:
                if task.completed and not include_completed:
                    continue
                by_time.setdefault(task.due_datetime, []).append(task)

        conflicts = [group for group in by_time.values() if len(group) > 1]
        conflicts.sort(key=lambda group: group[0].due_datetime)
        return conflicts

    def has_conflicts(self, owner_id: str, include_completed: bool = False) -> bool:
        """Return True if any two tasks for the owner share the same due time."""
        return bool(self.find_conflicts(owner_id, include_completed))

    def conflict_warnings(self, owner_id: str, include_completed: bool = False) -> List[str]:
        """Return human-readable warnings for same-time clashes, without raising.

        A lightweight, non-crashing alternative to add_task's ValueError: callers
        can print these strings and keep running. Returns an empty list when the
        schedule is clean (or the owner is unknown).
        """
        warnings: List[str] = []
        for group in self.find_conflicts(owner_id, include_completed):
            when = group[0].due_datetime.strftime("%Y-%m-%d %H:%M")
            details = ", ".join(
                f"{task.task_id} [{task.pet.name if task.pet else 'Unknown'}]"
                for task in group
            )
            warnings.append(
                f"Warning: {len(group)} tasks scheduled at {when} - {details}"
            )
        return warnings

    @staticmethod
    def _within_window(dt: datetime, window: Optional[tuple[int, int]]) -> bool:
        """Return True if dt falls within an inclusive (start_hour, end_hour) window.

        Supports overnight windows where start_hour > end_hour (e.g. (22, 6)
        means 22:00 through 06:00 across midnight). Minutes past the end hour
        fall outside the inclusive end in both cases.
        """
        if window is None:
            return True
        start_h, end_h = window
        if dt.hour == end_h and dt.minute > 0:
            return False
        if start_h <= end_h:
            return start_h <= dt.hour <= end_h
        # Overnight: inside if at/after start OR at/before end.
        return dt.hour >= start_h or dt.hour <= end_h

    def resolve_conflict(self, task: Task, owner: Owner, max_attempts: int = 10, delta: timedelta = timedelta(minutes=15)) -> bool:
        """Shift the lower-priority task forward by `delta` until a free slot is found.

        Returns True if resolved, False otherwise.
        """
        existing = next(
            (t for pet in owner.pets for t in pet.tasks
             if not t.completed and t.due_datetime == task.due_datetime),
            None,
        )
        if existing is None:
            return True  # nothing collides

        # Lower numeric priority == more important; ties move the new task.
        move_existing = existing.priority > task.priority
        target = existing if move_existing else task

        # Occupied slots are fixed while we probe (only `target` moves) -> precompute once.
        occupied = {
            other.due_datetime
            for pet in owner.pets
            for other in pet.tasks
            if other is not target and not other.completed
        }

        candidate = target.due_datetime
        for _ in range(max_attempts):
            candidate += delta
            if not self._within_window(candidate, owner.preferred_time_window):
                return False
            if not self._within_window(candidate, target.allowed_time_window):
                return False
            if any(bstart <= candidate <= bend for bstart, bend in target.blackout_periods):
                return False
            if candidate not in occupied:
                old_dt = target.due_datetime
                target.due_datetime = candidate
                # if we moved an existing task, the heap needs reordering
                if move_existing:
                    heapq.heapify(self.task_heap)
                self.event_log.append({
                    "type": "auto_reschedule",
                    "task_id": target.task_id,
                    "from": old_dt.isoformat(),
                    "to": candidate.isoformat(),
                    "moved_existing": move_existing,
                })
                return True
        return False

    def generate_recurring_tasks(self) -> None:
        for owner in self.owners:
            for pet in owner.pets:
                for task in list(pet.tasks):
                    if task.is_recurring and not task.completed:
                        next_task = task.next_occurrence()
                        if next_task is not None:
                            self._schedule_spawn(owner, pet, next_task)

    def get_overdue_tasks(self, owner_id: str) -> List[Task]:
        owner = self._find_owner(owner_id)
        if owner is None:
            return []

        now = datetime.now()
        overdue: List[Task] = []
        for pet in owner.pets:
            overdue.extend(task for task in pet.tasks if not task.completed and task.due_datetime < now)
        overdue.sort(key=lambda task: task)
        return overdue

    def _schedule_spawn(self, owner: Owner, pet: Pet, next_task: Task) -> bool:
        """Attach a spawned recurring task, resolving same-time conflicts first.

        Unlike add_task this never raises: if no free slot can be found the task
        is still attached (best effort) and the failure is logged, so completing
        a task or running a recurrence pass never crashes. Returns True when the
        task was placed without an unresolved conflict.
        """
        resolved = True
        if self.check_conflict(next_task, owner):
            resolved = self.resolve_conflict(next_task, owner)
        pet.add_task(next_task)
        heapq.heappush(self.task_heap, next_task)
        if not resolved:
            self.event_log.append({
                "type": "recurring_conflict_unresolved",
                "task_id": next_task.task_id,
                "pet_id": pet.pet_id,
                "owner_id": owner.owner_id,
                "due_datetime": next_task.due_datetime.isoformat(),
            })
        return resolved

    def _find_owner(self, owner_id: str) -> Optional[Owner]:
        return next((owner for owner in self.owners if owner.owner_id == owner_id), None)
