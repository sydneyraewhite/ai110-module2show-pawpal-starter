"""Edge-case suite for the PawPal+ scheduler.

Two kinds of tests live here:

* Tests that assert *correct* behavior and pass today.
* Tests marked ``xfail(strict=True)`` that pin down genuine bugs. They are
  expected to fail now; the ``strict=True`` means that if someone fixes the
  underlying bug the test will XPASS and the suite will go red, prompting you
  to remove the marker. In other words, these double as a bug tracker.

A handful of tests deliberately assert the *current* (arguably wrong) behavior
of design limitations (e.g. exact-timestamp-only conflicts). They are named
``..._current_behavior`` so it is obvious they document a limitation rather
than endorse it.
"""

from datetime import datetime, timedelta

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture
def owner() -> Owner:
    o = Owner(owner_id="owner-1", name="Ada", email="ada@example.com")
    o.add_pet(Pet(pet_id="pet-1", name="Milo", species="dog", age=3))
    o.add_pet(Pet(pet_id="pet-2", name="Nori", species="cat", age=2))
    return o


@pytest.fixture
def scheduler(owner: Owner) -> Scheduler:
    s = Scheduler()
    s.register_owner(owner)
    return s


def make_task(task_id: str, hour: int, minute: int = 0, priority: int = 1, **kw) -> Task:
    return Task(
        task_id=task_id,
        task_type=kw.pop("task_type", "feed"),
        due_datetime=datetime(2026, 7, 6, hour, minute),
        priority=priority,
        **kw,
    )


# --------------------------------------------------------------------------- #
# Baseline sanity (ported from the original unittest suite)
# --------------------------------------------------------------------------- #
def test_owner_pet_relationship_is_established() -> None:
    owner = Owner(owner_id="owner-1", name="Ada", email="ada@example.com")
    pet = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
    owner.add_pet(pet)
    assert pet in owner.pets
    assert pet.owner is owner


def test_add_task_pushes_onto_heap(scheduler: Scheduler, owner: Owner) -> None:
    task = make_task("t1", 8)
    scheduler.add_task(owner.owner_id, "pet-1", task)
    assert task in owner.get_pet("pet-1").tasks
    assert task.pet is owner.get_pet("pet-1")
    assert len(scheduler.task_heap) == 1


# --------------------------------------------------------------------------- #
# 1. Conflict detection only matches EXACT timestamps (no duration model)
# --------------------------------------------------------------------------- #
def test_exact_same_time_is_a_conflict(scheduler: Scheduler, owner: Owner) -> None:
    scheduler.add_task(owner.owner_id, "pet-1", make_task("a", 8))
    # Same time on the *other* pet -> genuine clash.
    assert scheduler.check_conflict(make_task("b", 8), owner) is True


def test_overlapping_but_not_identical_times_not_detected_current_behavior(
    scheduler: Scheduler, owner: Owner
) -> None:
    """A 60-min task at 08:00 and a task at 08:30 overlap in real life, but the
    scheduler has no duration field, so only exact-timestamp equality counts.

    This documents the limitation; fixing it requires a duration/end-time on
    Task plus interval-overlap logic in check_conflict/resolve_conflict.
    """
    scheduler.add_task(owner.owner_id, "pet-1", make_task("a", 8, 0))
    assert scheduler.check_conflict(make_task("b", 8, 30), owner) is False


def test_resolve_conflict_moves_lower_priority_task(scheduler: Scheduler, owner: Owner) -> None:
    scheduler.add_task(owner.owner_id, "pet-1", make_task("keep", 8, priority=1))
    # Lower priority (higher number) newcomer at the same time should be shifted.
    scheduler.add_task(owner.owner_id, "pet-2", make_task("move", 8, priority=3))
    moved = owner.get_pet("pet-2").tasks[0]
    assert moved.due_datetime == datetime(2026, 7, 6, 8, 15)


def test_resolve_conflict_gives_up_at_end_of_window_and_add_task_raises(
    scheduler: Scheduler, owner: Owner
) -> None:
    owner.preferred_time_window = (8, 8)  # only 08:00 is legal
    scheduler.add_task(owner.owner_id, "pet-1", make_task("first", 8, priority=1))
    with pytest.raises(ValueError):
        scheduler.add_task(owner.owner_id, "pet-2", make_task("second", 8, priority=3))


# --------------------------------------------------------------------------- #
# 2. Recurring tasks
# --------------------------------------------------------------------------- #
def test_complete_spawns_next_occurrence(scheduler: Scheduler, owner: Owner) -> None:
    scheduler.add_task(
        owner.owner_id, "pet-1",
        make_task("t", 8, is_recurring=True, recur_interval=timedelta(days=1)),
    )
    nxt = scheduler.complete_task(owner.owner_id, "pet-1", "t")
    assert nxt is not None
    assert nxt.due_datetime == datetime(2026, 7, 7, 8, 0)
    assert nxt.completed is False


def test_monthly_frequency_is_unsupported_and_returns_none() -> None:
    """Only 'daily'/'weekly' are understood; anything else silently no-ops."""
    t = make_task("m", 9, frequency="monthly")
    assert t.next_occurrence() is None


def test_frequency_only_task_spawns_via_complete_but_not_generate(
    scheduler: Scheduler, owner: Owner
) -> None:
    """Inconsistency: complete_task spawns any task whose next_occurrence() is
    non-None (frequency OR recur_interval), but generate_recurring_tasks gates
    on is_recurring. A frequency='daily', is_recurring=False task is treated
    differently by the two paths."""
    t = make_task("f", 9, frequency="daily", is_recurring=False)
    scheduler.add_task(owner.owner_id, "pet-1", t)

    # generate_recurring_tasks ignores it (is_recurring is False)...
    scheduler.generate_recurring_tasks()
    assert len(owner.get_pet("pet-1").tasks) == 1

    # ...but completing it does spawn a follow-up.
    assert scheduler.complete_task(owner.owner_id, "pet-1", "f") is not None
    assert len(owner.get_pet("pet-1").tasks) == 2


def test_generate_recurring_tasks_grows_unboundedly_current_behavior(
    scheduler: Scheduler, owner: Owner
) -> None:
    """generate_recurring_tasks has no horizon or upper bound: every call spawns
    another occurrence from every existing recurring task, so the task count
    keeps growing with each pass. A bounded implementation would generate up to
    some date/count limit and stop; this documents that it does not."""
    scheduler.add_task(
        owner.owner_id, "pet-1",
        make_task("t", 8, is_recurring=True, recur_interval=timedelta(days=1)),
    )
    counts = []
    for _ in range(3):
        scheduler.generate_recurring_tasks()
        counts.append(len(owner.get_pet("pet-1").tasks))
    # Strictly increasing across calls -> never converges to a fixed schedule.
    assert counts[0] < counts[1] < counts[2]


def test_spawned_recurring_task_should_not_create_silent_conflict(
    scheduler: Scheduler, owner: Owner
) -> None:
    """complete_task routes the spawned next occurrence through conflict
    resolution, so a recurring task that would land on an existing task's time
    is rescheduled instead of silently colliding."""
    # Existing task on pet-2 at 2026-07-07 08:00.
    scheduler.add_task(owner.owner_id, "pet-2", make_task("existing", 8) )
    owner.get_pet("pet-2").tasks[0].due_datetime = datetime(2026, 7, 7, 8, 0)

    # Daily recurring task on pet-1; completing it spawns 2026-07-07 08:00.
    scheduler.add_task(
        owner.owner_id, "pet-1",
        make_task("rec", 8, is_recurring=True, recur_interval=timedelta(days=1)),
    )
    scheduler.complete_task(owner.owner_id, "pet-1", "rec")

    # The spawn was rescheduled off the collision instead of stacking on it.
    assert scheduler.has_conflicts(owner.owner_id) is False


def test_spawned_recurring_task_should_respect_allowed_window(
    scheduler: Scheduler, owner: Owner
) -> None:
    """next_occurrence clamps the spawned time into the task's allowed window,
    so a daily task whose naive next occurrence would fall outside the window is
    snapped to the window start rather than scheduled out of bounds."""
    t = make_task(
        "rec", 8, is_recurring=True, recur_interval=timedelta(days=1),
        allowed_time_window=(9, 17),  # 08:00 occurrences are outside this
    )
    owner.get_pet("pet-1").add_task(t)
    nxt = t.next_occurrence()
    assert Scheduler._within_window(nxt.due_datetime, nxt.allowed_time_window) is True
    # Snapped to the window start hour on the next day.
    assert nxt.due_datetime == datetime(2026, 7, 7, 9, 0)


# --------------------------------------------------------------------------- #
# 3. Sorting
# --------------------------------------------------------------------------- #
def test_upcoming_and_overdue_use_different_sort_keys_current_behavior(
    scheduler: Scheduler, owner: Owner
) -> None:
    """__lt__ (used by get_overdue/get_tasks_for_today and the heap) sorts by
    priority-then-time, while get_upcoming_tasks sorts by time-then-priority.
    Same data, different order depending on the accessor."""
    early_low = make_task("early_low", 8, priority=3)   # early, low priority
    late_high = make_task("late_high", 18, priority=1)  # late, high priority
    owner.get_pet("pet-1").add_task(early_low)
    owner.get_pet("pet-1").add_task(late_high)

    upcoming = scheduler.get_upcoming_tasks(owner.owner_id)
    assert [t.task_id for t in upcoming] == ["early_low", "late_high"]  # time first

    ordered = sorted([early_low, late_high])  # __lt__: priority first
    assert [t.task_id for t in ordered] == ["late_high", "early_low"]


def test_sort_by_time_is_chronological(scheduler: Scheduler) -> None:
    tasks = [make_task("c", 12), make_task("a", 7), make_task("b", 9)]
    assert [t.task_id for t in scheduler.sort_by_time(tasks)] == ["a", "b", "c"]


def test_sort_time_strings_handles_non_zero_padded(scheduler: Scheduler) -> None:
    assert scheduler.sort_time_strings(["8:30", "10:05", "8:05"]) == ["8:05", "8:30", "10:05"]


@pytest.mark.parametrize("bad", ["", "8"])
def test_sort_time_strings_raises_on_unparseable_input_current_behavior(
    scheduler: Scheduler, bad: str
) -> None:
    """Strings without a valid 'HH:MM' shape blow up (empty -> ValueError on
    int(''), '8' -> IndexError on the missing ':' split). The parser is
    trusting rather than validating."""
    with pytest.raises((ValueError, IndexError)):
        scheduler.sort_time_strings([bad, "09:00"])


@pytest.mark.parametrize("bad", ["25:00", "08:60"])
def test_sort_time_strings_accepts_out_of_range_values_current_behavior(
    scheduler: Scheduler, bad: str
) -> None:
    """Out-of-range hours/minutes ('25:00', '08:60') parse to ints without
    complaint and sort by numeric value -- no clock-range validation."""
    result = scheduler.sort_time_strings([bad, "09:00"])
    assert bad in result and len(result) == 2


# --------------------------------------------------------------------------- #
# 4. Time windows
# --------------------------------------------------------------------------- #
def test_within_window_inclusive_start_and_on_the_hour_end(scheduler: Scheduler) -> None:
    assert Scheduler._within_window(datetime(2026, 7, 6, 8, 0), (8, 17)) is True
    assert Scheduler._within_window(datetime(2026, 7, 6, 17, 0), (8, 17)) is True


def test_within_window_excludes_minutes_past_end_hour_current_behavior(scheduler: Scheduler) -> None:
    """Window (8, 17) allows 17:00 exactly but rejects 17:30. Whether that is
    intended is a design call; this pins the boundary behavior."""
    assert Scheduler._within_window(datetime(2026, 7, 6, 17, 30), (8, 17)) is False


def test_overnight_window_accepts_late_night_time() -> None:
    """A (22, 6) window means 22:00-06:00 across midnight."""
    assert Scheduler._within_window(datetime(2026, 7, 6, 23, 0), (22, 6)) is True


@pytest.mark.parametrize(
    "hour, minute, expected",
    [
        (22, 0, True),   # at start
        (23, 30, True),  # late night
        (0, 0, True),    # midnight
        (6, 0, True),    # at end, on the hour
        (6, 30, False),  # past the inclusive end hour
        (7, 0, False),   # after end
        (12, 0, False),  # midday, clearly outside
        (21, 59, False), # just before start
    ],
)
def test_overnight_window_boundaries(hour: int, minute: int, expected: bool) -> None:
    dt = datetime(2026, 7, 6, hour, minute)
    assert Scheduler._within_window(dt, (22, 6)) is expected


# --------------------------------------------------------------------------- #
# 5. Two code paths desync heap / conflict state
# --------------------------------------------------------------------------- #
def test_direct_pet_add_task_bypasses_conflict_resolution(scheduler: Scheduler, owner: Owner) -> None:
    """Adding through Scheduler.add_task auto-resolves clashes; adding directly
    to the Pet does not, so a real collision survives and the heap is not
    updated for it."""
    scheduler.add_task(owner.owner_id, "pet-1", make_task("via_sched", 8))
    owner.get_pet("pet-2").add_task(make_task("direct", 8))  # bypass

    assert scheduler.has_conflicts(owner.owner_id) is True
    # The directly-added task never made it onto the scheduler's heap.
    heap_ids = {t.task_id for t in scheduler.task_heap}
    assert "direct" not in heap_ids


# --------------------------------------------------------------------------- #
# 6. Empty / single / all-completed / overdue boundaries
# --------------------------------------------------------------------------- #
def test_accessors_on_empty_schedule(scheduler: Scheduler, owner: Owner) -> None:
    assert scheduler.get_tasks_for_today(owner.owner_id) == []
    assert scheduler.get_upcoming_tasks(owner.owner_id) == []
    assert scheduler.get_overdue_tasks(owner.owner_id) == []
    assert scheduler.find_conflicts(owner.owner_id) == []


def test_unknown_owner_returns_empty_not_error(scheduler: Scheduler) -> None:
    assert scheduler.get_upcoming_tasks("nobody") == []
    assert scheduler.get_overdue_tasks("nobody") == []


def test_all_completed_tasks_excluded_from_pending_and_conflicts(
    scheduler: Scheduler, owner: Owner
) -> None:
    scheduler.add_task(owner.owner_id, "pet-1", make_task("a", 8))
    owner.get_pet("pet-2").add_task(make_task("b", 8))  # same time -> conflict
    assert scheduler.has_conflicts(owner.owner_id) is True

    for t in owner.get_all_tasks():
        t.mark_complete()
    # Completed tasks are ignored by conflict detection and upcoming lists.
    assert scheduler.has_conflicts(owner.owner_id) is False
    assert scheduler.get_upcoming_tasks(owner.owner_id) == []


def test_is_overdue_boundary(scheduler: Scheduler) -> None:
    now = datetime(2026, 7, 6, 12, 0)
    just_past = make_task("past", 11, 59)
    exactly_now = make_task("now", 12, 0)
    future = make_task("future", 12, 1)
    assert just_past.is_overdue(now) is True
    # Exactly "now" is not strictly past, so not overdue.
    assert exactly_now.is_overdue(now) is False
    assert future.is_overdue(now) is False


def test_completed_task_is_never_overdue(scheduler: Scheduler) -> None:
    t = make_task("t", 8)
    t.mark_complete()
    assert t.is_overdue(datetime(2026, 7, 6, 23, 0)) is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
