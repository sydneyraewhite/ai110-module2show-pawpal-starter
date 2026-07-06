from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional


@dataclass
class Task:
    task_id: str
    task_type: str
    due_datetime: datetime
    priority: int
    is_recurring: bool = False
    recur_interval: Optional[timedelta] = None
    completed: bool = False
    notes: str = ""
    pet: Optional["Pet"] = field(default=None, repr=False, compare=False)
    # per-task allowed scheduling window (start_hour, end_hour) inclusive
    allowed_time_window: Optional[tuple[int, int]] = None
    # list of blackout periods where this task cannot be scheduled: (start_dt, end_dt)
    blackout_periods: List[tuple[datetime, datetime]] = field(default_factory=list)

    def __lt__(self, other: "Task") -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        if self.due_datetime != other.due_datetime:
            return self.due_datetime < other.due_datetime
        return self.task_id < other.task_id

    def next_occurrence(self) -> Optional["Task"]:
        if not self.is_recurring or self.recur_interval is None:
            return None

        return Task(
            task_id=f"{self.task_id}-next",
            task_type=self.task_type,
            due_datetime=self.due_datetime + self.recur_interval,
            priority=self.priority,
            is_recurring=self.is_recurring,
            recur_interval=self.recur_interval,
            completed=False,
            notes=self.notes,
        )

    def mark_complete(self) -> None:
        self.completed = True


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
        if task not in self.tasks:
            self.tasks.append(task)
            task.pet = self

    def remove_task(self, task_id: str) -> None:
        task_to_remove = next((task for task in self.tasks if task.task_id == task_id), None)
        if task_to_remove is not None:
            self.tasks.remove(task_to_remove)
            task_to_remove.pet = None

    def get_due_today(self) -> List[Task]:
        today = datetime.now().date()
        return [task for task in self.tasks if task.due_datetime.date() == today]


@dataclass
class Owner:
    owner_id: str
    name: str
    email: str
    pets: List[Pet] = field(default_factory=list)
    # preferred_time_window is (start_hour, end_hour) in 24h format; inclusive
    preferred_time_window: Optional[tuple[int, int]] = None

    def add_pet(self, pet: Pet) -> None:
        if pet not in self.pets:
            self.pets.append(pet)
            pet.owner = self

    def remove_pet(self, pet_id: str) -> None:
        pet_to_remove = next((pet for pet in self.pets if pet.pet_id == pet_id), None)
        if pet_to_remove is not None:
            self.pets.remove(pet_to_remove)
            pet_to_remove.owner = None

    def get_pet(self, pet_id: str) -> Optional[Pet]:
        return next((pet for pet in self.pets if pet.pet_id == pet_id), None)


class Scheduler:
    def __init__(self) -> None:
        self.owners: List[Owner] = []
        self.task_heap: List[Task] = []
        self.event_log: List[dict] = []

    def register_owner(self, owner: Owner) -> None:
        if owner not in self.owners:
            self.owners.append(owner)

    def add_task(self, owner_id: str, pet_id: str, task: Task) -> None:
        owner = self._find_owner(owner_id)
        if owner is None:
            raise ValueError(f"Owner {owner_id} not found")

        pet = owner.get_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet {pet_id} not found for owner {owner_id}")

        # Try to resolve conflicts automatically; if unable, raise.
        if self.check_conflict(task, owner):
            resolved = self.resolve_conflict(task, owner)
            if not resolved:
                raise ValueError("Task conflicts with an existing scheduled task and could not be resolved")

        pet.add_task(task)
        heapq.heappush(self.task_heap, task)

    def remove_task(self, owner_id: str, pet_id: str, task_id: str) -> None:
        owner = self._find_owner(owner_id)
        if owner is None:
            return

        pet = owner.get_pet(pet_id)
        if pet is None:
            return

        pet.remove_task(task_id)

    def get_tasks_for_today(self, owner_id: str) -> List[Task]:
        owner = self._find_owner(owner_id)
        if owner is None:
            return []

        today = datetime.now().date()
        tasks: List[Task] = []
        for pet in owner.pets:
            tasks.extend(task for task in pet.tasks if task.due_datetime.date() == today)

        tasks.sort(key=lambda task: task)
        return tasks

    def check_conflict(self, task: Task, owner: Optional[Owner] = None) -> bool:
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

    def resolve_conflict(self, task: Task, owner: Owner, max_attempts: int = 10, delta: timedelta = timedelta(minutes=15)) -> bool:
        """Resolve a conflict by moving the lower-priority task forward by `delta` until no collision.

        Returns True if resolved, False otherwise.
        """
        # find tasks that collide with the requested time
        conflicting = []
        for pet in owner.pets:
            for existing in pet.tasks:
                if existing.completed:
                    continue
                if existing.due_datetime == task.due_datetime:
                    conflicting.append(existing)

        if not conflicting:
            return True

        for existing in conflicting:
            # Determine which task should be moved.
            # Lower numeric priority value means higher importance.
            move_existing = existing.priority > task.priority
            if existing.priority == task.priority:
                # tie -> move the new task
                move_existing = False

            target = existing if move_existing else task

            attempts = 0
            while attempts < max_attempts:
                old_dt = target.due_datetime
                new_dt = old_dt + delta

                # respect owner's preferred time window if set
                if owner.preferred_time_window is not None:
                    start_h, end_h = owner.preferred_time_window
                    h = new_dt.hour
                    m = new_dt.minute
                    if h < start_h or h > end_h or (h == end_h and m > 0):
                        return False

                # respect target task's allowed_time_window if set
                if target.allowed_time_window is not None:
                    start_h, end_h = target.allowed_time_window
                    h = new_dt.hour
                    m = new_dt.minute
                    if h < start_h or h > end_h or (h == end_h and m > 0):
                        return False

                # respect task blackout periods
                in_blackout = False
                for (bstart, bend) in target.blackout_periods:
                    if bstart <= new_dt <= bend:
                        in_blackout = True
                        break
                if in_blackout:
                    return False

                # check for collision at new slot
                conflict_still = False
                for pet2 in owner.pets:
                    for other in pet2.tasks:
                        if other is target or other.completed:
                            continue
                        if other.due_datetime == new_dt:
                            conflict_still = True
                            break
                    if conflict_still:
                        break

                attempts += 1
                if not conflict_still:
                    # apply the move
                    target.due_datetime = new_dt
                    # if we moved an existing task, the heap needs reordering
                    if move_existing:
                        heapq.heapify(self.task_heap)

                    # log the automatic resolution event
                    self.event_log.append({
                        "type": "auto_reschedule",
                        "task_id": target.task_id,
                        "from": old_dt.isoformat(),
                        "to": new_dt.isoformat(),
                        "moved_existing": move_existing,
                    })
                    return True

            # couldn't resolve this conflict
            return False

    def generate_recurring_tasks(self) -> None:
        for owner in self.owners:
            for pet in owner.pets:
                for task in list(pet.tasks):
                    if task.is_recurring and not task.completed:
                        next_task = task.next_occurrence()
                        if next_task is not None:
                            pet.add_task(next_task)
                            heapq.heappush(self.task_heap, next_task)

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

    def _find_owner(self, owner_id: str) -> Optional[Owner]:
        return next((owner for owner in self.owners if owner.owner_id == owner_id), None)
