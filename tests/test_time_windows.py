import unittest
from datetime import datetime, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


class TimeWindowTests(unittest.TestCase):
    def test_resolution_respects_time_window_failure(self):
        owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com", preferred_time_window=(8, 17))
        pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
        owner.add_pet(pet)

        scheduler = Scheduler()
        scheduler.register_owner(owner)

        existing = Task(
            task_id="t1",
            task_type="walk",
            due_datetime=datetime(2026, 7, 6, 16, 50),
            priority=3,
        )

        pet.add_task(existing)
        scheduler.task_heap.append(existing)

        new_task = Task(
            task_id="t2",
            task_type="feeding",
            due_datetime=datetime(2026, 7, 6, 16, 50),
            priority=2,  # higher priority
        )

        with self.assertRaises(ValueError):
            scheduler.add_task(owner.owner_id, pet.pet_id, new_task)

    def test_resolution_within_time_window_succeeds(self):
        owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com", preferred_time_window=(8, 18))
        pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
        owner.add_pet(pet)

        scheduler = Scheduler()
        scheduler.register_owner(owner)

        existing = Task(
            task_id="t1",
            task_type="walk",
            due_datetime=datetime(2026, 7, 6, 16, 50),
            priority=3,
        )

        pet.add_task(existing)
        scheduler.task_heap.append(existing)

        new_task = Task(
            task_id="t2",
            task_type="feeding",
            due_datetime=datetime(2026, 7, 6, 16, 50),
            priority=2,  # higher priority
        )

        scheduler.add_task(owner.owner_id, pet.pet_id, new_task)

        times = sorted(t.due_datetime for t in pet.tasks)
        self.assertEqual(times[0], datetime(2026, 7, 6, 16, 50))
        self.assertEqual(times[1], datetime(2026, 7, 6, 17, 5))


if __name__ == "__main__":
    unittest.main()
