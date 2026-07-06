import unittest
from datetime import datetime

from pawpal_system import Owner, Pet, Task


class CoreImplementationTests(unittest.TestCase):
    def test_owner_get_all_tasks_returns_tasks_from_all_pets(self) -> None:
        owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com")
        pet_one = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
        pet_two = Pet(pet_id="pet-2", name="Nori", species="cat", age=2)
        owner.add_pet(pet_one)
        owner.add_pet(pet_two)

        task_one = Task(task_id="t1", task_type="walk", description="Morning walk", due_datetime=datetime(2026, 7, 7, 8, 0), priority=2)
        task_two = Task(task_id="t2", task_type="feed", description="Dinner", due_datetime=datetime(2026, 7, 7, 18, 0), priority=1)
        pet_one.add_task(task_one)
        pet_two.add_task(task_two)

        all_tasks = owner.get_all_tasks()

        self.assertEqual({task.task_id for task in all_tasks}, {"t1", "t2"})

    def test_pet_get_pending_tasks_filters_completed_items(self) -> None:
        pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
        pending = Task(task_id="t1", task_type="walk", description="Walk", due_datetime=datetime(2026, 7, 7, 8, 0), priority=2)
        completed = Task(task_id="t2", task_type="feed", description="Feed", due_datetime=datetime(2026, 7, 7, 18, 0), priority=1)
        completed.mark_complete()
        pet.add_task(pending)
        pet.add_task(completed)

        pending_tasks = pet.get_pending_tasks()

        self.assertEqual([task.task_id for task in pending_tasks], ["t1"])


if __name__ == "__main__":
    unittest.main()
