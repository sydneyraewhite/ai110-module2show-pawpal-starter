import streamlit as st
from pawpal_system import Owner, Pet, Task, Scheduler
from datetime import datetime, timedelta
from typing import Optional
import uuid


# Session-state helpers for storing Owner/Pet objects
def _init_owners_store() -> None:
    """Ensure the `owners` mapping exists in `st.session_state`."""
    st.session_state.setdefault("owners", {})


def ensure_owner(owner: Owner) -> Owner:
    """Return an existing Owner if present, otherwise store and return `owner`.

    Uses `owner.owner_id` as the canonical key in `st.session_state['owners']`.
    """
    _init_owners_store()
    owners = st.session_state["owners"]
    existing = owners.get(owner.owner_id)
    if existing is not None:
        return existing
    owners[owner.owner_id] = owner
    st.session_state["owners"] = owners
    return owner


def get_owner(owner_id: str) -> Optional[Owner]:
    """Retrieve an Owner by id from session state, or None if not present."""
    _init_owners_store()
    return st.session_state["owners"].get(owner_id)


def create_owner(name: str, email: str, owner_id: Optional[str] = None) -> Owner:
    """Create a new Owner (or return existing) and store it in session state.

    If `owner_id` is omitted a UUID4 string will be generated.
    """
    _init_owners_store()
    owner_id = owner_id or str(uuid.uuid4())
    existing = get_owner(owner_id)
    if existing is not None:
        return existing
    owner = Owner(owner_id=owner_id, name=name, email=email)
    st.session_state["owners"][owner.owner_id] = owner
    return owner


def remove_owner(owner_id: str) -> None:
    """Remove an Owner from session state if present."""
    _init_owners_store()
    st.session_state["owners"].pop(owner_id, None)


def ensure_pet_for_owner(owner: Owner, pet: Pet) -> Pet:
    """Attach a Pet to an Owner in session state, returning the stored Pet.

    Uses `pet.pet_id` to check for existing pets on the `owner` instance.
    """
    existing = owner.get_pet(pet.pet_id)
    if existing is not None:
        return existing
    owner.add_pet(pet)
    return pet


def get_scheduler() -> Scheduler:
    """Return a session-scoped Scheduler instance."""
    if "scheduler" not in st.session_state:
        st.session_state["scheduler"] = Scheduler()
    return st.session_state["scheduler"]


st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Quick Demo Inputs (UI only)")
owner_name = st.text_input("Owner name", value="Jordan")
pet_name = st.text_input("Pet name", value="Mochi")
species = st.selectbox("Species", ["dog", "cat", "other"])

# Add pet UI wired to Owner/Pet helpers
if st.button("Add pet"):
    owner_key = owner_name.strip().lower().replace(" ", "_") or None
    owner = create_owner(name=owner_name, email=f"{owner_key}@example.com", owner_id=owner_key)
    pet_id = f"{owner.owner_id}-{pet_name.strip().lower().replace(' ', '_')}"
    pet = Pet(pet_id=pet_id, name=pet_name, species=species, age=0)
    ensure_owner(owner)
    ensure_pet_for_owner(owner, pet)
    scheduler = get_scheduler()
    scheduler.register_owner(owner)
    st.success(f"Added pet {pet.name} (id={pet.pet_id}) to owner {owner.name} (id={owner.owner_id})")

st.markdown("### Tasks")
st.caption("Add a few tasks. In your final version, these should feed into your scheduler.")

if "tasks" not in st.session_state:
    st.session_state.tasks = []

col1, col2, col3 = st.columns(3)
with col1:
    task_title = st.text_input("Task title", value="Morning walk")
with col2:
    duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
with col3:
    priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

if st.button("Add task"):
    # wire Add task to your backend classes
    owner_key = owner_name.strip().lower().replace(" ", "_") or None
    owner = create_owner(name=owner_name, email=f"{owner_key}@example.com", owner_id=owner_key)
    pet_id = f"{owner.owner_id}-{pet_name.strip().lower().replace(' ', '_')}"
    pet = owner.get_pet(pet_id)
    if pet is None:
        pet = Pet(pet_id=pet_id, name=pet_name, species=species, age=0)
        ensure_pet_for_owner(owner, pet)

    # map priority label to numeric (lower = higher importance)
    priority_map = {"high": 1, "medium": 2, "low": 3}
    pnum = priority_map.get(priority, 3)

    due = datetime.now()
    task_id = f"{pet.pet_id}-{int(due.timestamp())}"
    task = Task(task_id=task_id, task_type=task_title, due_datetime=due, priority=pnum, description="")

    scheduler = get_scheduler()
    scheduler.register_owner(owner)
    try:
        scheduler.add_task(owner.owner_id, pet.pet_id, task)
        st.success(f"Scheduled task '{task_title}' for {pet.name} at {due.isoformat()}")
        st.session_state.tasks.append({"title": task_title, "duration_minutes": int(duration), "priority": priority})
    except ValueError as exc:
        st.error(f"Could not schedule task: {exc}")

owner_key = owner_name.strip().lower().replace(" ", "_") or None
owner_obj = get_owner(owner_key)
if owner_obj is not None:
    scheduler = get_scheduler()
    scheduler.register_owner(owner_obj)

    st.markdown(f"### 📋 Tasks for {owner_obj.name}")

    all_tasks = owner_obj.get_all_tasks()
    conflicts = scheduler.conflict_warnings(owner_obj.owner_id)

    # At-a-glance summary metrics
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("Total", len(all_tasks))
    mcol2.metric("Pending", len(scheduler.filter_tasks(all_tasks, completed=False)))
    mcol3.metric("Completed", len(scheduler.filter_tasks(all_tasks, completed=True)))
    mcol4.metric("Conflicts", len(conflicts))

    # Filter controls wired to Scheduler.filter_tasks
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        status_filter = st.selectbox("Status", ["All", "Pending", "Completed"])
    with fcol2:
        pet_options = ["All pets"] + [pet.name for pet in owner_obj.pets]
        pet_filter = st.selectbox("Pet", pet_options)

    completed_arg = {"All": None, "Pending": False, "Completed": True}[status_filter]
    pet_name_arg = None if pet_filter == "All pets" else pet_filter

    # Filter, then sort chronologically using the Scheduler's own methods
    filtered = scheduler.filter_tasks(
        all_tasks, completed=completed_arg, pet_name=pet_name_arg
    )
    ordered = scheduler.sort_by_time(filtered)

    priority_labels = {1: "🔴 High", 2: "🟡 Medium", 3: "🟢 Low"}

    if ordered:
        st.caption(f"Showing {len(ordered)} of {len(all_tasks)} tasks, sorted by time.")
        st.table(
            [
                {
                    "Time": t.due_datetime.strftime("%b %d, %H:%M"),
                    "Pet": t.pet.name if t.pet else "—",
                    "Task": t.task_type,
                    "Priority": priority_labels.get(t.priority, str(t.priority)),
                    "Status": "✅ Done" if t.completed else "⏳ Pending",
                }
                for t in ordered
            ]
        )
    else:
        st.info("No tasks match the current filters.")

    # Surface same-time clashes as non-blocking warnings
    if conflicts:
        for warning in conflicts:
            st.warning(f"⚠️ {warning}")
    elif all_tasks:
        st.success("✅ No scheduling conflicts detected.")
elif st.session_state.tasks:
    st.write("Current tasks (unsaved):")
    st.table(st.session_state.tasks)
else:
    st.info("No tasks yet. Add one above.")

st.divider()

st.subheader("Build Schedule")
st.caption("Generates an ordered plan of upcoming tasks using your Scheduler.")

if st.button("Generate schedule"):
    owner_key = owner_name.strip().lower().replace(" ", "_") or None
    owner_obj = get_owner(owner_key)
    if owner_obj is None:
        st.info("Add a pet and some tasks first.")
    else:
        scheduler = get_scheduler()
        scheduler.register_owner(owner_obj)

        # Ordered by time, then priority; completed tasks are excluded
        upcoming = scheduler.get_upcoming_tasks(owner_obj.owner_id, limit=10)
        priority_labels = {1: "🔴 High", 2: "🟡 Medium", 3: "🟢 Low"}
        if upcoming:
            st.success(f"📅 Generated a plan with {len(upcoming)} upcoming task(s).")
            st.table(
                [
                    {
                        "Time": t.due_datetime.strftime("%b %d, %H:%M"),
                        "Pet": t.pet.name if t.pet else "—",
                        "Task": t.task_type,
                        "Priority": priority_labels.get(t.priority, str(t.priority)),
                    }
                    for t in upcoming
                ]
            )
        else:
            st.info("No pending tasks to schedule.")

        # Report any scheduling conflicts without blocking the plan
        warnings = scheduler.conflict_warnings(owner_obj.owner_id)
        if warnings:
            for warning in warnings:
                st.warning(f"⚠️ {warning}")
        else:
            st.success("✅ No scheduling conflicts detected.")
