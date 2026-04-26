import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

from ai_recommender import _classify_age, generate_task_suggestions, retrieve_care_guidelines
from logger_config import setup_logging
from pawpal_system import Owner, Pet, Scheduler, Task

setup_logging()

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
    /* ── Global ── */
    .stApp { background-color: #FFF0F3; font-family: 'Nunito', sans-serif; }
    .main .block-container { padding-top: 1.5rem; }

    /* ── Typography ── */
    h1 { color: #C2185B !important; font-weight: 800 !important; }
    h2 { color: #AD1457 !important; font-weight: 700 !important;
         border-left: 4px solid #E91E8C; padding-left: 0.5rem; }
    h3 { color: #C2185B !important; font-weight: 700 !important; }
    p, label, .stMarkdown { font-family: 'Nunito', sans-serif !important; }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #E91E8C 0%, #FF6B9D 100%) !important;
        color: white !important; border: none !important;
        border-radius: 20px !important; font-weight: 700 !important;
        box-shadow: 0 3px 10px rgba(233,30,140,0.25) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(233,30,140,0.35) !important;
    }
    .stFormSubmitButton > button {
        background: linear-gradient(135deg, #E91E8C 0%, #FF6B9D 100%) !important;
        color: white !important; border: none !important;
        border-radius: 20px !important; font-weight: 700 !important;
        box-shadow: 0 3px 10px rgba(233,30,140,0.25) !important;
    }

    /* ── Inputs ── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        border: 1.5px solid #F8BBD0 !important;
        border-radius: 10px !important; background: white !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #E91E8C !important;
        box-shadow: 0 0 0 2px rgba(233,30,140,0.12) !important;
    }
    .stSelectbox > div > div {
        border: 1.5px solid #F8BBD0 !important;
        border-radius: 10px !important; background: white !important;
    }

    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background: white; border-radius: 14px;
        padding: 1rem 1.2rem;
        box-shadow: 0 2px 10px rgba(194,24,91,0.08);
        border: 1px solid #FFCDD2;
    }
    [data-testid="stMetricLabel"] { color: #AD1457 !important; font-weight: 600 !important; }
    [data-testid="stMetricValue"] { color: #C2185B !important; font-weight: 800 !important; }

    /* ── Expander ── */
    .streamlit-expanderHeader {
        background: white !important; border-radius: 10px !important;
        border: 1px solid #F8BBD0 !important;
        color: #AD1457 !important; font-weight: 700 !important;
    }

    /* ── Alerts ── */
    [data-testid="stAlert"] { border-radius: 12px !important; }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {
        border-radius: 12px !important; overflow: hidden;
        box-shadow: 0 2px 10px rgba(194,24,91,0.08);
    }

    /* ── Misc ── */
    hr { border-color: #FFCDD2 !important; }
    .stCaption { color: #AD1457 !important; }
    .stSpinner > div { border-top-color: #E91E8C !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style='text-align:center; padding: 1.2rem 0 0.2rem 0;'>
    <span style='font-size:2.8rem;'>🐾</span>
    <h1 style='color:#C2185B; font-size:2.6rem; font-weight:800; margin:0.1rem 0 0.2rem 0;
               border:none; padding:0;'>PawPal+</h1>
    <p style='color:#E91E8C; font-size:0.95rem; font-weight:600; margin:0; letter-spacing:0.4px;'>
        Smart pet care scheduling, powered by AI
    </p>
</div>
<hr style='border-color:#FFCDD2; margin: 1rem 0 1.5rem 0;'>
""", unsafe_allow_html=True)

# ── Session state init ─────────────────────────────────────────────────────────
if "owner" not in st.session_state:
    st.session_state.owner = None
if "current_pet" not in st.session_state:
    st.session_state.current_pet = None
if "scheduler" not in st.session_state:
    st.session_state.scheduler = None
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []
if "suggestions_pet" not in st.session_state:
    st.session_state.suggestions_pet = ""
if "suggestions_used_ai" not in st.session_state:
    st.session_state.suggestions_used_ai = False
if "retrieved_guidelines" not in st.session_state:
    st.session_state.retrieved_guidelines = []
if "editing_task_key" not in st.session_state:
    st.session_state.editing_task_key = None
if "dismissed_conflicts" not in st.session_state:
    st.session_state.dismissed_conflicts = set()


def _shift_time(time_str: str, minutes: int) -> str:
    try:
        t = datetime.strptime(time_str, "%H:%M") + timedelta(minutes=minutes)
        return t.strftime("%H:%M")
    except Exception:
        return ""


def _to_12h(time_str: str) -> str:
    try:
        return datetime.strptime(time_str, "%H:%M").strftime("%I:%M %p").lstrip("0")
    except Exception:
        return time_str or "—"


# ── Section 1: Owner setup ─────────────────────────────────────────────────────
st.header("1. Owner Info")

with st.form("owner_form"):
    owner_name        = st.text_input("Owner name", value="Jordan")
    available_minutes = st.number_input("Available time today (minutes)", min_value=10, max_value=480, value=90)
    submitted = st.form_submit_button("Save owner")

if submitted:
    st.session_state.owner                = Owner(name=owner_name, available_minutes=available_minutes)
    st.session_state.current_pet          = None
    st.session_state.scheduler            = None
    st.session_state.suggestions          = []
    st.session_state.suggestions_pet      = ""
    st.session_state.retrieved_guidelines = []
    st.session_state.editing_task_key     = None
    st.session_state.dismissed_conflicts  = set()
    st.success(f"Welcome, {owner_name}! You have {available_minutes} min available today.")

owner: Owner = st.session_state.owner

if owner is None:
    st.info("Fill in owner info above to get started.")
    st.stop()

# ── Section 2: Add a Pet ───────────────────────────────────────────────────────
st.header("2. Add a Pet")

with st.form("pet_form"):
    pet_name      = st.text_input("Pet name", value="Mochi")
    species       = st.selectbox("Species", ["dog", "cat", "other"])
    age           = st.number_input("Age", min_value=0, max_value=30, value=3)
    pet_submitted = st.form_submit_button("Add pet")

if pet_submitted:
    new_pet = Pet(name=pet_name, species=species, age=age)
    owner.add_pet(new_pet)
    st.session_state.current_pet = new_pet
    st.success(f"{new_pet.name} has been added as a {new_pet.age}-year-old {new_pet.species}.")

if owner.pets:
    st.write("**Registered pets:**")
    st.table([
        {"Name": p.name, "Species": p.species, "Age": p.age,
         "Total tasks": len(p.tasks), "Pending": len(p.get_pending_tasks())}
        for p in owner.pets
    ])

    with st.expander("✏️ Edit or delete a pet"):
        edit_pet_name = st.selectbox("Select pet", [p.name for p in owner.pets], key="edit_pet_select")
        edit_pet = next(p for p in owner.pets if p.name == edit_pet_name)
        with st.form("edit_pet_form"):
            new_pet_name    = st.text_input("Name", value=edit_pet.name)
            new_pet_species = st.selectbox(
                "Species", ["dog", "cat", "other"],
                index=["dog", "cat", "other"].index(edit_pet.species)
                      if edit_pet.species in ["dog", "cat", "other"] else 2,
            )
            new_pet_age  = st.number_input("Age", min_value=0, max_value=30, value=edit_pet.age)
            col_u, col_d = st.columns(2)
            with col_u:
                do_update_pet = st.form_submit_button("Update pet")
            with col_d:
                do_delete_pet = st.form_submit_button("Delete pet")

        if do_update_pet:
            edit_pet.name    = new_pet_name
            edit_pet.species = new_pet_species
            edit_pet.age     = new_pet_age
            st.success(f"{new_pet_name} has been updated to a {new_pet_age}-year-old {new_pet_species}.")
            st.rerun()

        if do_delete_pet:
            owner.pets.remove(edit_pet)
            st.success(f"{edit_pet_name} has been removed.")
            st.rerun()
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

    if st.session_state.suggestions_pet != selected_name:
        st.session_state.suggestions          = []
        st.session_state.suggestions_pet      = ""
        st.session_state.retrieved_guidelines = []

    with st.form("task_form"):
        task_title     = st.text_input("Task title", value="Morning walk")
        duration       = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        priority       = st.selectbox("Priority", ["low", "medium", "high"], index=2)
        task_type      = st.selectbox("Task type", ["walk", "feeding", "meds", "grooming", "enrichment", "other"])
        scheduled_time = st.text_input("Scheduled time (24h format, e.g. 09:00)", value="")
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
        st.success(f"'{task_title}' has been added to {selected_pet.name}'s schedule.")

    # ── AI Suggestions (RAG) ───────────────────────────────────────────────────
    st.subheader("🤖 AI Task Suggestions")

    if st.button(f"Get suggestions for {selected_pet.name}"):
        with st.spinner("Retrieving care guidelines and generating suggestions…"):
            guidelines = retrieve_care_guidelines(selected_pet)
            suggestions, used_ai = generate_task_suggestions(selected_pet, guidelines)
            st.session_state.suggestions          = suggestions
            st.session_state.suggestions_pet      = selected_name
            st.session_state.suggestions_used_ai  = used_ai
            st.session_state.retrieved_guidelines = guidelines

    if st.session_state.suggestions and st.session_state.suggestions_pet == selected_name:
        life_stage = _classify_age(selected_pet.species.lower(), selected_pet.age)
        source     = "Claude AI (RAG)" if st.session_state.suggestions_used_ai else "Built-in care guidelines"
        st.caption(f"Life stage detected: **{life_stage}** · Source: **{source}**")

        to_remove = []
        for i, task in enumerate(st.session_state.suggestions):
            col_info, col_btn = st.columns([5, 1])
            with col_info:
                recur_label = f" · {task.recurrence}" if task.recurrence else ""
                time_label  = f" · {_to_12h(task.scheduled_time)}" if task.scheduled_time else ""
                st.write(
                    f"**{task.title}** — {task.duration_minutes} min, "
                    f"{task.priority} priority, {task.task_type}{recur_label}{time_label}"
                )
            with col_btn:
                if st.button("Add", key=f"add_suggestion_{i}"):
                    selected_pet.add_task(task)
                    to_remove.append(i)
                    st.success(f"'{task.title}' added to {selected_pet.name}'s schedule.")

        for idx in reversed(to_remove):
            st.session_state.suggestions.pop(idx)

    # ── Task list with edit / delete ───────────────────────────────────────────
    if selected_pet.tasks:
        st.write(f"**Tasks for {selected_pet.name} — sorted by time:**")
        sorted_tasks = selected_pet.get_tasks_sorted_by_time()

        for i, task in enumerate(sorted_tasks):
            task_key = f"{selected_name}::{i}"
            col_info, col_edit, col_del = st.columns([5, 1, 1])

            with col_info:
                status = "✅" if task.completed else "🕐"
                st.write(
                    f"{status} **{task.title}** — {_to_12h(task.scheduled_time) if task.scheduled_time else '—'} · "
                    f"{task.duration_minutes} min · {task.priority} · {task.task_type}"
                )
            with col_edit:
                if st.button("Edit", key=f"edit_btn_{task_key}"):
                    st.session_state.editing_task_key = task_key
            with col_del:
                if st.button("Delete", key=f"del_btn_{task_key}"):
                    selected_pet.tasks.remove(task)
                    st.rerun()

            if st.session_state.editing_task_key == task_key:
                with st.form(f"edit_task_form_{task_key}"):
                    e_title    = st.text_input("Title", value=task.title)
                    e_duration = st.number_input("Duration (min)", min_value=1, max_value=240,
                                                 value=task.duration_minutes)
                    e_priority = st.selectbox("Priority", ["low", "medium", "high"],
                                              index=["low", "medium", "high"].index(task.priority))
                    e_type     = st.selectbox(
                        "Type", ["walk", "feeding", "meds", "grooming", "enrichment", "other"],
                        index=["walk", "feeding", "meds", "grooming", "enrichment", "other"].index(task.task_type),
                    )
                    e_time  = st.text_input("Scheduled time (HH:MM)", value=task.scheduled_time or "")
                    e_recur = st.selectbox(
                        "Recurrence", ["none", "daily", "weekly"],
                        index=["none", "daily", "weekly"].index(task.recurrence if task.recurrence else "none"),
                    )
                    col_s, col_c = st.columns(2)
                    with col_s:
                        do_save = st.form_submit_button("Save")
                    with col_c:
                        do_cancel = st.form_submit_button("Cancel")

                if do_save:
                    task.title            = e_title
                    task.duration_minutes = int(e_duration)
                    task.priority         = e_priority
                    task.task_type        = e_type
                    task.scheduled_time   = e_time.strip()
                    task.recurrence       = "" if e_recur == "none" else e_recur
                    st.session_state.editing_task_key = None
                    st.rerun()
                if do_cancel:
                    st.session_state.editing_task_key = None
                    st.rerun()

        n_pending   = len(selected_pet.get_pending_tasks())
        n_completed = len(selected_pet.get_completed_tasks())
        col1, col2  = st.columns(2)
        col1.metric("Pending tasks",   n_pending)
        col2.metric("Completed tasks", n_completed)
    else:
        st.info(f"No tasks for {selected_pet.name} yet.")

# ── Section 4: Generate Schedule ──────────────────────────────────────────────
st.header("4. Today's Schedule")

if st.button("Generate schedule"):
    scheduler = Scheduler(owner)
    scheduler.generate_plan()
    st.session_state.scheduler            = scheduler
    st.session_state.dismissed_conflicts  = set()

if st.session_state.scheduler:
    scheduler: Scheduler = st.session_state.scheduler

    conflicts = scheduler.detect_conflicts()
    if conflicts:
        st.warning(
            f"**Scheduling conflict{'s' if len(conflicts) > 1 else ''} detected "
            f"({len(conflicts)} time slot{'s' if len(conflicts) > 1 else ''})** — "
            "two or more tasks share the same time slot."
        )

        for slot, entries in conflicts:
            if slot in st.session_state.dismissed_conflicts:
                continue

            pet_task_lines = " · ".join(f"{pet}: {task.title}" for pet, task in entries)
            st.error(f"**{slot}** → {pet_task_lines}")

            if len(entries) >= 2:
                _, first_task         = entries[0]
                mover_pet, mover_task = entries[1]
                suggested_time        = _shift_time(slot, first_task.duration_minutes)

                if suggested_time:
                    st.info(
                        f"💡 Suggestion: move **{mover_task.title}** ({mover_pet}) "
                        f"from {_to_12h(slot)} → **{_to_12h(suggested_time)}** "
                        f"(right after **{first_task.title}** finishes)"
                    )
                    col_yes, col_no = st.columns([1, 5])
                    with col_yes:
                        if st.button("Yes, fix it", key=f"fix_{slot}"):
                            mover_task.scheduled_time = suggested_time
                            st.session_state.dismissed_conflicts.add(slot)
                            st.rerun()
                    with col_no:
                        if st.button("No, ignore", key=f"ignore_{slot}"):
                            st.session_state.dismissed_conflicts.add(slot)
                            st.rerun()
    else:
        st.success("All clear! No scheduling conflicts found.")

    st.divider()

    plan = scheduler._plan
    if plan:
        import pandas as pd

        _COLOR_PALETTE = [
            "#AED6F1", "#FADBD8", "#D5F5E3", "#FAD7A0",
            "#D2B4DE", "#A9DFBF", "#F9E79F", "#ABEBC6",
        ]

        task_to_pet: dict = {}
        for pet in owner.pets:
            for t in pet.tasks:
                task_to_pet[id(t)] = pet

        def _time_key(t):
            if not t.scheduled_time:
                return 9999
            try:
                h, m = t.scheduled_time.split(":")
                return int(h) * 60 + int(m)
            except Exception:
                return 9999

        sorted_plan = sorted(plan, key=_time_key)

        seen_species = list(dict.fromkeys(
            task_to_pet[id(t)].species.lower() if id(t) in task_to_pet else "other"
            for t in sorted_plan
        ))
        species_color_map = {s: _COLOR_PALETTE[i % len(_COLOR_PALETTE)] for i, s in enumerate(seen_species)}

        row_species = []
        plan_rows = []
        for i, t in enumerate(sorted_plan):
            pet      = task_to_pet.get(id(t))
            pet_name = pet.name if pet else "—"
            species  = pet.species.lower() if pet else "other"
            row_species.append(species)
            plan_rows.append({
                "#":        i + 1,
                "Task":     t.title,
                "Pet":      pet_name,
                "Time":     _to_12h(t.scheduled_time) if t.scheduled_time else "—",
                "Duration": f"{t.duration_minutes} min",
                "Priority": t.priority.capitalize(),
                "Type":     t.task_type,
            })

        df = pd.DataFrame(plan_rows)

        def _color_rows(row):
            color = species_color_map.get(row_species[row.name], "#FFFFFF")
            return [f"background-color: {color}"] * len(row)

        styled = df.style.apply(_color_rows, axis=1)

        legend = "   ".join(
            f"<span style='background:{species_color_map[s]};padding:2px 10px;border-radius:4px'>"
            f"{s.capitalize()}</span>"
            for s in seen_species
        )
        st.write("**Scheduled tasks:**")
        st.markdown(legend, unsafe_allow_html=True)
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("No tasks fit within the available time budget.")

    skipped = scheduler._skipped
    if skipped:
        st.warning(f"**{len(skipped)} task(s) skipped** — not enough time remaining:")
        for task in skipped:
            st.write(f"- {task.title} ({task.duration_minutes} min, {task.priority} priority)")

    time_used      = owner.available_minutes - scheduler._remaining_minutes
    time_remaining = scheduler._remaining_minutes
    col1, col2, col3 = st.columns(3)
    col1.metric("Time budget",    f"{owner.available_minutes} min")
    col2.metric("Time scheduled", f"{time_used} min")
    col3.metric("Time remaining", f"{time_remaining} min")
