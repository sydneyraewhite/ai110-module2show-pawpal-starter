from datetime import datetime, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


def main() -> None:
    owner = Owner(owner_id="owner-1", name="Alex", email="alex@example.com")

    pet_one = Pet(pet_id="pet-1", name="Milo", species="dog", age=3)
    pet_two = Pet(pet_id="pet-2", name="Nori", species="cat", age=2)

    owner.add_pet(pet_one)
    owner.add_pet(pet_two)

    scheduler = Scheduler()
    scheduler.register_owner(owner)

    # Deliberately out of chronological order to prove the sort works.
    tasks = [
        Task(
            task_id="task-1",
            task_type="medication",
            description="Vet medicine",
            due_datetime=datetime(2026, 7, 6, 18, 0),
            priority=3,
        ),
        Task(
            task_id="task-2",
            task_type="walk",
            description="Morning walk",
            due_datetime=datetime(2026, 7, 6, 8, 0),
            priority=2,
        ),
        Task(
            task_id="task-3",
            task_type="feed",
            description="Lunch feeding",
            due_datetime=datetime(2026, 7, 6, 12, 30),
            priority=1,
        ),
        Task(
            task_id="task-4",
            task_type="play",
            description="Evening playtime",
            due_datetime=datetime(2026, 7, 6, 16, 15),
            priority=2,
        ),
        Task(
            task_id="task-5",
            task_type="feed",
            description="Breakfast feeding",
            due_datetime=datetime(2026, 7, 6, 7, 0),
            priority=1,
        ),
    ]

    scheduler.add_task(owner.owner_id, pet_one.pet_id, tasks[0])
    scheduler.add_task(owner.owner_id, pet_two.pet_id, tasks[1])
    scheduler.add_task(owner.owner_id, pet_one.pet_id, tasks[2])
    scheduler.add_task(owner.owner_id, pet_two.pet_id, tasks[3])
    scheduler.add_task(owner.owner_id, pet_one.pet_id, tasks[4])

    # Introduce a deliberate clash: give Nori a 07:00 task at the same time as
    # Milo's 07:00 breakfast. Added directly to the pet to bypass add_task's
    # auto-resolution, so find_conflicts has a real collision to detect.
    pet_two.add_task(
        Task(
            task_id="task-6",
            task_type="feed",
            description="Breakfast feeding",
            due_datetime=datetime(2026, 7, 6, 7, 0),
            priority=1,
        )
    )

    # Mark one complete so the completion filter has something to separate.
    tasks[1].mark_complete()

    all_tasks = owner.get_all_tasks()

    def show(task: Task) -> str:
        pet_name = task.pet.name if task.pet else "Unknown"
        status = "done" if task.completed else "pending"
        return (
            f"- {task.due_datetime.strftime('%H:%M')} | {pet_name} | "
            f"{task.task_type} | {task.description} ({status})"
        )

    print("Insertion Order")
    print("===============")
    for task in all_tasks:
        print(show(task))

    print("\nSorted by Time")
    print("==============")
    for task in scheduler.sort_by_time(all_tasks):
        print(show(task))

    print("\nSorted by Priority (then time)")
    print("==============================")
    for task in scheduler.sort_by_priority(all_tasks):
        print(
            f"- {task.priority_label:<6} | {task.due_datetime.strftime('%H:%M')} | "
            f"{task.pet.name if task.pet else 'Unknown'} | {task.task_type}"
        )

    print("\nSorted Time Strings")
    print("===================")
    time_strings = [task.due_datetime.strftime("%H:%M") for task in all_tasks]
    print(scheduler.sort_time_strings(time_strings))

    print("\nPending Tasks Only")
    print("==================")
    for task in scheduler.sort_by_time(scheduler.filter_tasks(all_tasks, completed=False)):
        print(show(task))

    print("\nTasks for Milo")
    print("==============")
    for task in scheduler.sort_by_time(scheduler.filter_tasks(all_tasks, pet_name="Milo")):
        print(show(task))

    print("\nMilo's Pending Tasks")
    print("====================")
    for task in scheduler.sort_by_time(
        scheduler.filter_tasks(all_tasks, completed=False, pet_name="Milo")
    ):
        print(show(task))

    print("\nScheduling Conflicts")
    print("====================")
    warnings = scheduler.conflict_warnings(owner.owner_id)
    if warnings:
        for warning in warnings:
            print(warning)
    else:
        print("No conflicts detected.")

    print("\nNext Available Slot")
    print("===================")
    # 07:00 is double-booked; suggest the next free slot from 07:00 onward.
    for desired in (datetime(2026, 7, 6, 7, 0), datetime(2026, 7, 6, 14, 0)):
        slot = scheduler.find_next_available_slot(
            owner.owner_id, desired, step=timedelta(minutes=15)
        )
        found = slot.strftime("%H:%M") if slot else "none within 24h"
        print(f"- want {desired.strftime('%H:%M')} -> next free {found}")


if __name__ == "__main__":
    main()
