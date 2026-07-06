import unittest
from datetime import datetime, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


class PawPalSystemTests(unittest.TestCase):
    def test_owner_pet_relationship_is_established(self) -> None:
        owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com")
        pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)

        owner.add_pet(pet)

        self.assertIn(pet, owner.pets)
        self.assertIs(pet.owner, owner)

    def test_scheduler_adds_task_and_generates_recurring_follow_up(self) -> None:
        owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com")
        pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
        owner.add_pet(pet)

        scheduler = Scheduler()
        scheduler.register_owner(owner)

        task = Task(
            task_id="task-1",
            task_type="feeding",
            due_datetime=datetime(2026, 7, 5, 8, 0),
            priority=2,
            is_recurring=True,
            recur_interval=timedelta(days=1),
        )

        scheduler.add_task(owner.owner_id, pet.pet_id, task)

        self.assertIn(task, pet.tasks)
        self.assertIs(task.pet, pet)
        self.assertEqual(len(scheduler.task_heap), 1)

        scheduler.generate_recurring_tasks()

        self.assertEqual(len(pet.tasks), 2)
        self.assertTrue(any(other.task_id != task.task_id for other in pet.tasks))


if __name__ == "__main__":
    unittest.main()
