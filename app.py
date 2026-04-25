import streamlit as st
from pawpal_system import Owner, Pet, Task, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")

# ── Session state init ─────────────────────────────────────────────────────────
if "owner" not in st.session_state:
    st.session_state.owner = None

if "current_pet" not in st.session_state:
    st.session_state.current_pet = None

if "scheduler" not in st.session_state:
    st.session_state.scheduler = None

# ── Section 1: Owner setup ─────────────────────────────────────────────────────
st.header("1. Owner Info")

with st.form("owner_form"):
    owner_name        = st.text_input("Owner name", value="Jordan")
    available_minutes = st.number_input("Available time today (minutes)", min_value=10, max_value=480, value=90)
    submitted = st.form_submit_button("Save owner")

if submitted:
    st.session_state.owner     = Owner(name=owner_name, available_minutes=available_minutes)
    st.session_state.current_pet = None
    st.session_state.scheduler   = None
    st.success(f"Owner '{owner_name}' saved — {available_minutes} min available today.")

owner: Owner = st.session_state.owner

if owner is None:
    st.info("Fill in owner info above to get started.")
    st.stop()

# ── Section 2: Add a Pet ───────────────────────────────────────────────────────
st.header("2. Add a Pet")

with st.form("pet_form"):
    pet_name = st.text_input("Pet name", value="Mochi")
    species  = st.selectbox("Species", ["dog", "cat", "other"])
    age      = st.number_input("Age", min_value=0, max_value=30, value=3)
    pet_submitted = st.form_submit_button("Add pet")

if pet_submitted:
    new_pet = Pet(name=pet_name, species=species, age=age)
    owner.add_pet(new_pet)
    st.session_state.current_pet = new_pet
    st.success(f"Added {new_pet.name} ({new_pet.species}, age {new_pet.age}).")

if owner.pets:
    st.write("**Registered pets:**")
    pet_rows = [
        {"Name": p.name, "Species": p.species, "Age": p.age,
         "Total tasks": len(p.tasks), "Pending": len(p.get_pending_tasks())}
        for p in owner.pets
    ]
    st.table(pet_rows)
else:
    st.info("No pets added yet.")

# ── Section 3: Add Tasks to a Pet ─────────────────────────────────────────────
st.header("3. Add Tasks")

if not owner.pets:
    st.warning("Add a pet first before adding tasks.")
else:
    pet_names     = [p.name for p in owner.pets]
    selected_name = st.selectbox("Select pet to add task to", pet_names)
    selected_pet  = next(p for p in owner.pets if p.name == selected_name)

    with st.form("task_form"):
        task_title     = st.text_input("Task title", value="Morning walk")
        duration       = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        priority       = st.selectbox("Priority", ["low", "medium", "high"], index=2)
        task_type      = st.selectbox("Task type", ["walk", "feeding", "meds", "grooming", "enrichment", "other"])
        scheduled_time = st.text_input("Scheduled time (HH:MM, optional)", value="")
        recurrence     = st.selectbox("Recurrence", ["none", "daily", "weekly"])
        task_submitted = st.form_submit_button("Add task")

    if task_submitted:
        new_task = Task(
            title=task_title,
            duration_minutes=int(duration),
            priority=priority,
            task_type=task_type,
            scheduled_time=scheduled_time.strip(),
            recurrence="" if recurrence == "none" else recurrence,
        )
        selected_pet.add_task(new_task)
        st.success(f"Task '{task_title}' added to {selected_pet.name}.")

    # Show tasks sorted by scheduled time using the new method
    if selected_pet.tasks:
        st.write(f"**Tasks for {selected_pet.name} — sorted by time:**")
        sorted_tasks = selected_pet.get_tasks_sorted_by_time()
        task_rows = [
            {
                "Time":       t.scheduled_time or "—",
                "Task":       t.title,
                "Duration":   f"{t.duration_minutes} min",
                "Priority":   t.priority.capitalize(),
                "Type":       t.task_type,
                "Recurrence": t.recurrence or "none",
                "Status":     "Done" if t.completed else "Pending",
            }
            for t in sorted_tasks
        ]
        st.table(task_rows)

        # Pending vs completed summary
        n_pending   = len(selected_pet.get_pending_tasks())
        n_completed = len(selected_pet.get_completed_tasks())
        col1, col2 = st.columns(2)
        col1.metric("Pending tasks",   n_pending)
        col2.metric("Completed tasks", n_completed)
    else:
        st.info(f"No tasks for {selected_pet.name} yet.")

# ── Section 4: Generate Schedule ──────────────────────────────────────────────
st.header("4. Today's Schedule")

if st.button("Generate schedule"):
    scheduler = Scheduler(owner)
    scheduler.generate_plan()
    st.session_state.scheduler = scheduler

if st.session_state.scheduler:
    scheduler: Scheduler = st.session_state.scheduler

    # ── Conflict warnings — shown before the plan so the owner sees them first ──
    conflicts = scheduler.detect_conflicts()
    if conflicts:
        st.warning(
            f"**Scheduling conflict{'s' if len(conflicts) > 1 else ''} detected "
            f"({len(conflicts)} time slot{'s' if len(conflicts) > 1 else ''})** — "
            "two or more tasks are assigned to the same time. "
            "Edit task times in Section 3 to resolve."
        )
        for slot, entries in conflicts:
            pet_task_lines = " · ".join(f"{pet}: {task.title}" for pet, task in entries)
            st.error(f"**{slot}** → {pet_task_lines}")
    else:
        st.success("No scheduling conflicts — all tasks have unique time slots.")

    st.divider()

    # ── Scheduled tasks table ──────────────────────────────────────────────────
    plan = scheduler._plan
    if plan:
        st.write("**Scheduled tasks:**")
        plan_rows = [
            {
                "#":          i + 1,
                "Task":       t.title,
                "Duration":   f"{t.duration_minutes} min",
                "Priority":   t.priority.capitalize(),
                "Type":       t.task_type,
                "Time":       t.scheduled_time or "—",
            }
            for i, t in enumerate(plan)
        ]
        st.table(plan_rows)
    else:
        st.info("No tasks fit within the available time budget.")

    # ── Skipped tasks ──────────────────────────────────────────────────────────
    skipped = scheduler._skipped
    if skipped:
        st.warning(f"**{len(skipped)} task(s) skipped** — not enough time remaining:")
        for task in skipped:
            st.write(f"- {task.title} ({task.duration_minutes} min, {task.priority} priority)")

    # ── Time budget summary ────────────────────────────────────────────────────
    time_used      = owner.available_minutes - scheduler._remaining_minutes
    time_remaining = scheduler._remaining_minutes
    col1, col2, col3 = st.columns(3)
    col1.metric("Time budget",    f"{owner.available_minutes} min")
    col2.metric("Time scheduled", f"{time_used} min")
    col3.metric("Time remaining", f"{time_remaining} min")
