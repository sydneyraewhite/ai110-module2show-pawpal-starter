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

        if self.check_conflict(task, owner):
            raise ValueError("Task conflicts with an existing scheduled task")

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
