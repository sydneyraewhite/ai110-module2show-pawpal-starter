import unittest
from datetime import datetime, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


class ConflictResolutionTests(unittest.TestCase):
    def test_higher_priority_new_task_moves_existing(self):
        owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com")
        pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
        owner.add_pet(pet)

        scheduler = Scheduler()
        scheduler.register_owner(owner)

        existing = Task(
            task_id="t1",
            task_type="walk",
            due_datetime=datetime(2026, 7, 6, 8, 0),
            priority=3,
        )

        pet.add_task(existing)
        scheduler.task_heap.append(existing)

        new_task = Task(
            task_id="t2",
            task_type="feeding",
            due_datetime=datetime(2026, 7, 6, 8, 0),
            priority=2,  # higher priority
        )

        scheduler.add_task(owner.owner_id, pet.pet_id, new_task)

        times = sorted(t.due_datetime for t in pet.tasks)
        self.assertEqual(times[0], datetime(2026, 7, 6, 8, 0))
        self.assertEqual(times[1], datetime(2026, 7, 6, 8, 15))

    def test_lower_priority_new_task_is_moved(self):
        owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com")
        pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
        owner.add_pet(pet)

        scheduler = Scheduler()
        scheduler.register_owner(owner)

        existing = Task(
            task_id="t1",
            task_type="walk",
            due_datetime=datetime(2026, 7, 6, 9, 0),
            priority=1,
        )

        pet.add_task(existing)
        scheduler.task_heap.append(existing)

        new_task = Task(
            task_id="t2",
            task_type="feeding",
            due_datetime=datetime(2026, 7, 6, 9, 0),
            priority=5,  # lower priority
        )

        scheduler.add_task(owner.owner_id, pet.pet_id, new_task)

        # existing should remain at 9:00, new task should move to 9:15
        times = {t.task_id: t.due_datetime for t in pet.tasks}
        self.assertEqual(times["t1"], datetime(2026, 7, 6, 9, 0))
        self.assertEqual(times["t2"], datetime(2026, 7, 6, 9, 15))


if __name__ == "__main__":
    unittest.main()
