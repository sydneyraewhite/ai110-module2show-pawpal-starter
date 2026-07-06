import unittest
from datetime import datetime, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


class TaskWindowAndEventTests(unittest.TestCase):
    def test_event_logged_on_auto_reschedule(self):
        owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com")
        pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
        owner.add_pet(pet)

        scheduler = Scheduler()
        scheduler.register_owner(owner)

        existing = Task(
            task_id="t1",
            task_type="walk",
            due_datetime=datetime(2026, 7, 7, 8, 0),
            priority=3,
        )

        pet.add_task(existing)
        scheduler.task_heap.append(existing)

        new_task = Task(
            task_id="t2",
            task_type="feeding",
            due_datetime=datetime(2026, 7, 7, 8, 0),
            priority=2,  # higher priority
        )

        scheduler.add_task(owner.owner_id, pet.pet_id, new_task)

        # ensure an event was logged for the moved task
        events = scheduler.event_log
        self.assertTrue(any(e.get("type") == "auto_reschedule" and e.get("task_id") == "t1" for e in events))

    def test_task_blackout_prevents_shift(self):
        owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com", preferred_time_window=(8, 18))
        pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
        owner.add_pet(pet)

        scheduler = Scheduler()
        scheduler.register_owner(owner)

        existing = Task(
            task_id="t1",
            task_type="walk",
            due_datetime=datetime(2026, 7, 7, 16, 50),
            priority=3,
            allowed_time_window=(8, 17),
            blackout_periods=[(datetime(2026,7,7,17,0), datetime(2026,7,7,17,30))],
        )

        pet.add_task(existing)
        scheduler.task_heap.append(existing)

        new_task = Task(
            task_id="t2",
            task_type="feeding",
            due_datetime=datetime(2026, 7, 7, 16, 50),
            priority=2,  # higher priority
        )

        with self.assertRaises(ValueError):
            scheduler.add_task(owner.owner_id, pet.pet_id, new_task)


if __name__ == "__main__":
    unittest.main()
