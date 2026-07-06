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

    def test_find_next_available_slot_skips_occupied_and_respects_window(self):
        owner = Owner(
            owner_id="o1", name="Alex", email="a@x.com",
            preferred_time_window=(8, 17),
        )
        pet = Pet(pet_id="p1", name="Milo", species="dog", age=3)
        owner.add_pet(pet)
        scheduler = Scheduler()
        scheduler.register_owner(owner)

        from datetime import timedelta
        scheduler.add_task(owner.owner_id, pet.pet_id, Task(
            task_id="a", task_type="feed",
            due_datetime=datetime(2026, 7, 6, 9, 0), priority=1))
        scheduler.add_task(owner.owner_id, pet.pet_id, Task(
            task_id="b", task_type="walk",
            due_datetime=datetime(2026, 7, 6, 9, 15), priority=1))

        # 09:00 and 09:15 are taken -> next free 15-min slot is 09:30
        slot = scheduler.find_next_available_slot(
            owner.owner_id, datetime(2026, 7, 6, 9, 0), step=timedelta(minutes=15))
        self.assertEqual(slot, datetime(2026, 7, 6, 9, 30))

        # A free time is returned unchanged
        free = scheduler.find_next_available_slot(
            owner.owner_id, datetime(2026, 7, 6, 14, 0))
        self.assertEqual(free, datetime(2026, 7, 6, 14, 0))

        # A time before the preferred window rolls forward to the window start
        early = scheduler.find_next_available_slot(
            owner.owner_id, datetime(2026, 7, 6, 6, 0), step=timedelta(hours=1))
        self.assertEqual(early.hour, 8)

    def test_json_persistence_round_trip(self):
        import os
        import tempfile
        from datetime import timedelta

        owner = Owner(owner_id="o1", name="Alex", email="a@x.com",
                      preferred_time_window=(8, 17))
        pet = Pet(pet_id="p1", name="Milo", species="dog", age=3, breed="Lab")
        owner.add_pet(pet)
        scheduler = Scheduler()
        scheduler.register_owner(owner)
        scheduler.add_task(owner.owner_id, pet.pet_id, Task(
            task_id="t1", task_type="feed",
            due_datetime=datetime(2026, 7, 6, 9, 0), priority=1,
            is_recurring=True, recur_interval=timedelta(days=1), frequency="daily",
            allowed_time_window=(6, 12)))

        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            scheduler.save_to_json(path)
            restored = Scheduler()
            self.assertTrue(restored.load_from_json(path))

            task = restored.owners[0].pets[0].tasks[0]
            self.assertEqual(task.due_datetime, datetime(2026, 7, 6, 9, 0))
            self.assertEqual(task.recur_interval, timedelta(days=1))
            self.assertEqual(task.allowed_time_window, (6, 12))
            self.assertEqual(restored.owners[0].preferred_time_window, (8, 17))
            # back-references and heap are rebuilt on load
            self.assertIs(task.pet, restored.owners[0].pets[0])
            self.assertEqual(len(restored.task_heap), 1)
        finally:
            os.remove(path)

        # Missing file leaves state unchanged and reports False
        self.assertFalse(Scheduler().load_from_json(path))

    def test_sort_by_priority_orders_by_level_then_time(self):
        scheduler = Scheduler()

        def make(tid, pri, hour):
            return Task(task_id=tid, task_type="x",
                        due_datetime=datetime(2026, 7, 6, hour, 0), priority=pri)

        low_early = make("low", 3, 6)
        high_late = make("high", 1, 18)
        high_early = make("high2", 1, 7)
        med = make("med", 2, 9)

        ordered = scheduler.sort_by_priority([low_early, high_late, high_early, med])
        # High (both, earliest first), then Medium, then Low
        self.assertEqual([t.task_id for t in ordered], ["high2", "high", "med", "low"])

    def test_priority_label_maps_numbers_to_names(self):
        from pawpal_system import Priority

        def task(pri):
            return Task(task_id="t", task_type="x",
                        due_datetime=datetime(2026, 7, 6, 9, 0), priority=pri)

        self.assertEqual(task(1).priority_label, "High")
        self.assertEqual(task(2).priority_label, "Medium")
        self.assertEqual(task(3).priority_label, "Low")
        self.assertEqual(task(Priority.HIGH).priority_label, "High")
        self.assertEqual(task(9).priority_label, "9")  # out-of-range falls back

    def test_reschedule_weekly_skips_blackout_week(self):
        scheduler = Scheduler()
        task = Task(
            task_id="w", task_type="bath",
            due_datetime=datetime(2026, 7, 6, 9, 0), priority=2,
            frequency="weekly", allowed_time_window=(8, 17),
            blackout_periods=[(datetime(2026, 7, 13, 0, 0), datetime(2026, 7, 13, 23, 59))],
        )
        # +1 week (07-13) is blacked out, so it should skip to 07-20 at the same time
        self.assertEqual(scheduler.reschedule_weekly(task), datetime(2026, 7, 20, 9, 0))

    def test_reschedule_weekly_returns_none_when_all_weeks_blocked(self):
        scheduler = Scheduler()
        task = Task(
            task_id="w", task_type="bath",
            due_datetime=datetime(2026, 7, 6, 9, 0), priority=2,
            frequency="weekly", allowed_time_window=(8, 17),
            blackout_periods=[(datetime(2026, 7, 7, 0, 0), datetime(2026, 12, 31, 23, 59))],
        )
        self.assertIsNone(scheduler.reschedule_weekly(task, max_weeks=8))

    def test_within_window_boundaries(self):
        self.assertTrue(Scheduler._within_window(datetime(2026, 7, 6, 9, 0), (8, 17)))
        self.assertTrue(Scheduler._within_window(datetime(2026, 7, 6, 17, 0), (8, 17)))
        self.assertFalse(Scheduler._within_window(datetime(2026, 7, 6, 17, 15), (8, 17)))
        self.assertFalse(Scheduler._within_window(datetime(2026, 7, 6, 7, 59), (8, 17)))
        self.assertTrue(Scheduler._within_window(datetime(2026, 7, 6, 3, 0), None))


if __name__ == "__main__":
    unittest.main()
