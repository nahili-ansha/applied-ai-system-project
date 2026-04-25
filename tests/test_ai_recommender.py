import json
from unittest.mock import MagicMock, patch

import pytest

from pawpal_system import Pet, Task
from ai_recommender import (
    _classify_age,
    _kb_fallback,
    _validate_task,
    generate_task_suggestions,
    retrieve_care_guidelines,
)


# ── Age classification ─────────────────────────────────────────────────────────

def test_classify_age_dog_puppy():
    assert _classify_age("dog", 0) == "puppy"
    assert _classify_age("dog", 1) == "puppy"


def test_classify_age_dog_adult():
    assert _classify_age("dog", 2) == "adult"
    assert _classify_age("dog", 7) == "adult"


def test_classify_age_dog_senior():
    assert _classify_age("dog", 8) == "senior"
    assert _classify_age("dog", 14) == "senior"


def test_classify_age_cat():
    assert _classify_age("cat", 0) == "kitten"
    assert _classify_age("cat", 5) == "adult"
    assert _classify_age("cat", 12) == "senior"


def test_classify_age_unknown_species():
    assert _classify_age("rabbit", 3) == "adult"


# ── Knowledge base retrieval ───────────────────────────────────────────────────

def test_retrieve_returns_tasks_for_dog():
    pet = Pet(name="Rex", species="dog", age=3)
    guidelines = retrieve_care_guidelines(pet)
    assert isinstance(guidelines, list)
    assert len(guidelines) > 0
    assert "title" in guidelines[0]


def test_retrieve_returns_tasks_for_cat():
    pet = Pet(name="Luna", species="cat", age=6)
    guidelines = retrieve_care_guidelines(pet)
    assert len(guidelines) > 0


def test_retrieve_falls_back_for_unknown_species():
    pet = Pet(name="Bugs", species="rabbit", age=2)
    guidelines = retrieve_care_guidelines(pet)
    assert isinstance(guidelines, list)


# ── Guardrails ─────────────────────────────────────────────────────────────────

def test_validate_task_valid():
    td = {
        "title": "Morning walk",
        "duration_minutes": 30,
        "priority": "high",
        "task_type": "walk",
    }
    assert _validate_task(td) is True


def test_validate_task_missing_required_field():
    td = {"duration_minutes": 30, "priority": "high", "task_type": "walk"}
    assert _validate_task(td) is False


def test_validate_task_invalid_priority():
    td = {"title": "Walk", "duration_minutes": 30, "priority": "critical", "task_type": "walk"}
    assert _validate_task(td) is False


def test_validate_task_zero_duration():
    td = {"title": "Walk", "duration_minutes": 0, "priority": "high", "task_type": "walk"}
    assert _validate_task(td) is False


def test_validate_task_unknown_type_coerced():
    td = {"title": "Bath", "duration_minutes": 15, "priority": "low", "task_type": "swimming"}
    result = _validate_task(td)
    assert result is True
    assert td["task_type"] == "other"


# ── KB fallback ────────────────────────────────────────────────────────────────

def test_kb_fallback_returns_task_objects():
    guidelines = [
        {
            "title": "Morning walk",
            "duration_minutes": 30,
            "priority": "high",
            "task_type": "walk",
            "scheduled_time": "07:00",
            "recurrence": "daily",
            "reason": "Exercise",
        }
    ]
    tasks = _kb_fallback(guidelines)
    assert len(tasks) == 1
    assert isinstance(tasks[0], Task)
    assert tasks[0].title == "Morning walk"


def test_kb_fallback_skips_malformed_entry():
    guidelines = [
        {"title": "Good task", "duration_minutes": 10, "priority": "low", "task_type": "other"},
        {"broken": True},  # missing required fields
    ]
    tasks = _kb_fallback(guidelines)
    assert len(tasks) == 1


# ── AI generation ──────────────────────────────────────────────────────────────

def test_generate_uses_fallback_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pet = Pet(name="Mochi", species="dog", age=3)
    guidelines = retrieve_care_guidelines(pet)
    tasks, used_ai = generate_task_suggestions(pet, guidelines)
    assert used_ai is False
    assert isinstance(tasks, list)
    assert all(isinstance(t, Task) for t in tasks)


def test_generate_returns_tasks_from_valid_api_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key")

    valid_response = json.dumps([
        {
            "title": "Morning walk",
            "duration_minutes": 30,
            "priority": "high",
            "task_type": "walk",
            "scheduled_time": "07:00",
            "recurrence": "daily",
        }
    ])

    mock_content = MagicMock()
    mock_content.text = valid_response

    mock_usage = MagicMock()
    mock_usage.input_tokens = 200
    mock_usage.output_tokens = 80
    mock_usage.cache_read_input_tokens = 0
    mock_usage.cache_creation_input_tokens = 0

    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("ai_recommender.Anthropic", return_value=mock_client):
        pet = Pet(name="Rex", species="dog", age=3)
        guidelines = retrieve_care_guidelines(pet)
        tasks, used_ai = generate_task_suggestions(pet, guidelines)

    assert used_ai is True
    assert len(tasks) == 1
    assert tasks[0].title == "Morning walk"
    assert tasks[0].priority == "high"


def test_generate_falls_back_on_malformed_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key")

    mock_content = MagicMock()
    mock_content.text = "This is not JSON at all!"

    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=10)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("ai_recommender.Anthropic", return_value=mock_client):
        pet = Pet(name="Luna", species="cat", age=4)
        guidelines = retrieve_care_guidelines(pet)
        tasks, used_ai = generate_task_suggestions(pet, guidelines)

    assert used_ai is False
    assert isinstance(tasks, list)


def test_generate_falls_back_on_api_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("Connection timeout")

    with patch("ai_recommender.Anthropic", return_value=mock_client):
        pet = Pet(name="Buddy", species="dog", age=5)
        guidelines = retrieve_care_guidelines(pet)
        tasks, used_ai = generate_task_suggestions(pet, guidelines)

    assert used_ai is False
    assert isinstance(tasks, list)
