from __future__ import annotations

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

    def __lt__(self, other: "Task") -> bool:
        pass

    def next_occurrence(self) -> Optional["Task"]:
        pass

    def mark_complete(self) -> None:
        pass


@dataclass
class Pet:
    pet_id: str
    name: str
    species: str
    age: int
    breed: str = ""
    notes: str = ""
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        pass

    def remove_task(self, task_id: str) -> None:
        pass

    def get_due_today(self) -> List[Task]:
        pass


@dataclass
class Owner:
    owner_id: str
    name: str
    email: str
    pets: List[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        pass

    def remove_pet(self, pet_id: str) -> None:
        pass

    def get_pet(self, pet_id: str) -> Optional[Pet]:
        pass


class Scheduler:
    def __init__(self) -> None:
        self.owners: List[Owner] = []
        self.task_heap: List[Task] = []

    def register_owner(self, owner: Owner) -> None:
        pass

    def add_task(self, owner_id: str, pet_id: str, task: Task) -> None:
        pass

    def remove_task(self, owner_id: str, pet_id: str, task_id: str) -> None:
        pass

    def get_tasks_for_today(self, owner_id: str) -> List[Task]:
        pass

    def check_conflict(self, task: Task) -> bool:
        pass

    def generate_recurring_tasks(self) -> None:
        pass

    def get_overdue_tasks(self, owner_id: str) -> List[Task]:
        pass
