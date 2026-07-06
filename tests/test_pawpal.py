import unittest
from datetime import datetime

from pawpal_system import Owner, Pet, Scheduler, Task


class PawPalSimpleTests(unittest.TestCase):
    def test_task_completion_marks_completed(self):
        task = Task(
            task_id="t-complete",
            task_type="feed",
            due_datetime=datetime(2026, 7, 7, 9, 0),
            priority=1,
        )
        self.assertFalse(task.completed)
        task.mark_complete()
        self.assertTrue(task.completed)

    def test_adding_task_increases_pet_count(self):
        pet = Pet(pet_id="pet-100", name="Biscuit", species="dog", age=4)
        initial_count = len(pet.tasks)
        task = Task(
            task_id="t-add",
            task_type="walk",
            due_datetime=datetime(2026, 7, 7, 10, 0),
            priority=2,
        )
        pet.add_task(task)
        self.assertEqual(len(pet.tasks), initial_count + 1)

    def test_resolve_conflict_advances_past_occupied_slots(self):
        # 08:00 and 08:15 are taken; a new 08:00 task must skip to 08:30.
        owner = Owner(owner_id="o1", name="Alex", email="a@x.com")
        pet = Pet(pet_id="p1", name="Milo", species="dog", age=3)
        owner.add_pet(pet)
        scheduler = Scheduler()
        scheduler.register_owner(owner)

        scheduler.add_task(owner.owner_id, pet.pet_id, Task(
            task_id="first", task_type="feed",
            due_datetime=datetime(2026, 7, 6, 8, 0), priority=1))
        scheduler.add_task(owner.owner_id, pet.pet_id, Task(
            task_id="second", task_type="walk",
            due_datetime=datetime(2026, 7, 6, 8, 15), priority=1))

        # Lower-priority task collides with 08:00; it should be shifted, not the others.
        newcomer = Task(
            task_id="newcomer", task_type="play",
            due_datetime=datetime(2026, 7, 6, 8, 0), priority=5)
        scheduler.add_task(owner.owner_id, pet.pet_id, newcomer)

        self.assertEqual(newcomer.due_datetime, datetime(2026, 7, 6, 8, 30))

    def test_within_window_boundaries(self):
        self.assertTrue(Scheduler._within_window(datetime(2026, 7, 6, 9, 0), (8, 17)))
        self.assertTrue(Scheduler._within_window(datetime(2026, 7, 6, 17, 0), (8, 17)))
        self.assertFalse(Scheduler._within_window(datetime(2026, 7, 6, 17, 15), (8, 17)))
        self.assertFalse(Scheduler._within_window(datetime(2026, 7, 6, 7, 59), (8, 17)))
        self.assertTrue(Scheduler._within_window(datetime(2026, 7, 6, 3, 0), None))


if __name__ == "__main__":
    unittest.main()
