import json
import logging
import os
from pathlib import Path
from typing import List, Tuple

from pawpal_system import Pet, Task

logger = logging.getLogger("pawpal")

try:
    from anthropic import Anthropic, APIError
except ImportError:
    Anthropic = None  # type: ignore[assignment,misc]
    APIError = None   # type: ignore[assignment,misc]

_KB_PATH = Path(__file__).parent / "pet_care_kb.json"
with open(_KB_PATH, encoding="utf-8") as _f:
    _KNOWLEDGE_BASE: dict = json.load(_f)


# ── Age classification ─────────────────────────────────────────────────────────

def _classify_age(species: str, age: int) -> str:
    if species == "dog":
        if age <= 1:
            return "puppy"
        elif age <= 7:
            return "adult"
        else:
            return "senior"
    elif species == "cat":
        if age <= 1:
            return "kitten"
        elif age <= 10:
            return "adult"
        else:
            return "senior"
    return "adult"


# ── Retrieval ──────────────────────────────────────────────────────────────────

def retrieve_care_guidelines(pet: Pet) -> List[dict]:
    species = pet.species.lower()
    age_group = _classify_age(species, pet.age)

    try:
        guidelines = _KNOWLEDGE_BASE[species][age_group]["tasks"]
        logger.info(f"Retrieved {len(guidelines)} guidelines for species={species}, age_group={age_group}")
        return guidelines
    except KeyError:
        fallback = _KNOWLEDGE_BASE.get("other", {}).get("adult", {}).get("tasks", [])
        logger.warning(f"No KB entry for species={species}, age_group={age_group} — using generic fallback")
        return fallback


# ── Guardrails ─────────────────────────────────────────────────────────────────

_VALID_PRIORITIES = {"low", "medium", "high"}
_VALID_TYPES = {"walk", "feeding", "meds", "grooming", "enrichment", "other"}


def _validate_task(td: dict) -> bool:
    required = ["title", "duration_minutes", "priority", "task_type"]
    for field in required:
        if field not in td:
            logger.warning(f"Task rejected — missing field '{field}': {td}")
            return False

    if not isinstance(td["title"], str) or not td["title"].strip():
        logger.warning(f"Task rejected — empty title: {td}")
        return False

    if td["priority"] not in _VALID_PRIORITIES:
        logger.warning(f"Task rejected — invalid priority '{td['priority']}'")
        return False

    try:
        duration = int(td["duration_minutes"])
    except (TypeError, ValueError):
        logger.warning(f"Task rejected — non-integer duration: {td}")
        return False
    if duration <= 0:
        logger.warning(f"Task rejected — duration must be positive, got {duration}")
        return False
    td["duration_minutes"] = duration  # normalise to int in-place

    if td["task_type"] not in _VALID_TYPES:
        logger.warning(f"task_type '{td['task_type']}' unknown — coercing to 'other'")
        td["task_type"] = "other"

    return True


def _parse_tasks(task_dicts: list) -> List[Task]:
    tasks = []
    for td in task_dicts:
        if _validate_task(td):
            tasks.append(Task(
                title=str(td["title"]).strip(),
                duration_minutes=int(td["duration_minutes"]),
                priority=td["priority"],
                task_type=td["task_type"],
                scheduled_time=str(td.get("scheduled_time", "")).strip(),
                recurrence="" if td.get("recurrence") in (None, "none") else str(td.get("recurrence", "")),
            ))
    return tasks


def _kb_fallback(guidelines: List[dict]) -> List[Task]:
    tasks = []
    for g in guidelines[:5]:
        try:
            tasks.append(Task(
                title=g["title"],
                duration_minutes=int(g["duration_minutes"]),
                priority=g["priority"],
                task_type=g["task_type"],
                scheduled_time=g.get("scheduled_time", ""),
                recurrence=g.get("recurrence", ""),
            ))
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed KB entry: {e} — {g}")
    logger.info(f"KB fallback produced {len(tasks)} tasks")
    return tasks


# ── AI generation (RAG) ────────────────────────────────────────────────────────

def generate_task_suggestions(pet: Pet, guidelines: List[dict]) -> Tuple[List[Task], bool]:
    """Return (tasks, used_ai). used_ai=False means KB fallback was used instead of Claude."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping AI, using KB fallback")
        return _kb_fallback(guidelines), False

    if Anthropic is None:
        logger.error("anthropic package not installed — using KB fallback")
        return _kb_fallback(guidelines), False

    age_group = _classify_age(pet.species.lower(), pet.age)

    # Format retrieved guidelines as readable context for the AI
    context_lines = [
        f"- {g['title']}: {g['duration_minutes']} min, {g['priority']} priority, "
        f"type={g['task_type']}, recurrence={g.get('recurrence', 'none')} — {g['reason']}"
        for g in guidelines
    ]
    retrieved_context = "\n".join(context_lines)

    # System prompt cached — same content for every call in the session
    system_text = (
        "You are a veterinary-backed pet care assistant. "
        "You generate personalised, actionable daily care tasks grounded strictly "
        "in the care guidelines provided. "
        "Always return ONLY a valid JSON array — no markdown, no explanation, just the array.\n\n"
        f"Retrieved care guidelines:\n{retrieved_context}"
    )

    user_text = (
        f"Generate 3 to 5 daily care tasks for {pet.name}, "
        f"a {pet.age}-year-old {pet.species} (life stage: {age_group}). "
        "Base each task on the guidelines above.\n\n"
        "Each object in the JSON array must have exactly these fields:\n"
        '  "title": string\n'
        '  "duration_minutes": integer (positive)\n'
        '  "priority": "low", "medium", or "high"\n'
        '  "task_type": "walk", "feeding", "meds", "grooming", "enrichment", or "other"\n'
        '  "scheduled_time": "HH:MM" or ""\n'
        '  "recurrence": "daily", "weekly", or ""\n\n'
        "Return only the JSON array."
    )

    client = Anthropic(api_key=api_key)

    try:
        logger.info(f"AI query: pet={pet.name}, species={pet.species}, age={pet.age}, age_group={age_group}")
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=[{
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},  # prompt caching — reused across pets
            }],
            messages=[{"role": "user", "content": user_text}],
        )

        cache_read = getattr(response.usage, "cache_read_input_tokens", 0)
        cache_created = getattr(response.usage, "cache_creation_input_tokens", 0)
        logger.info(
            f"API response: input={response.usage.input_tokens}, "
            f"output={response.usage.output_tokens}, "
            f"cache_read={cache_read}, cache_created={cache_created}"
        )

        raw = response.content[0].text.strip()

        # Strip markdown fences if the model adds them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        task_dicts = json.loads(raw)
        if not isinstance(task_dicts, list):
            raise ValueError("Claude returned a non-array JSON value")

        tasks = _parse_tasks(task_dicts)
        logger.info(f"Generated {len(tasks)} valid suggestions for {pet.name}")
        return tasks, True

    except Exception as e:
        logger.error(f"AI generation failed ({type(e).__name__}): {e} — using KB fallback")
        return _kb_fallback(guidelines), False
