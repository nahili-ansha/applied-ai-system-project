# PawPal+ — AI-Powered Pet Care Scheduler

PawPal+ is a Streamlit web application that helps busy pet owners organize daily care for their pets. It combines a priority based scheduling engine with a Claude powered AI recommender to generate personalized task plans grounded in species-specific care guidelines.

---

## Original Project (Modules 1–3)

The original PawPal+ was built across Modules 1 through 3 as a pure scheduling system. Its goals were to let a pet owner enter their available time for the day, add care tasks with priorities and durations, and receive a daily plan that respected their time budget. The system was built around four core classes `Owner`, `Pet`, `Task`, and `Scheduler` with logic for priority sorting, recurring tasks, conflict detection, and a Streamlit interface for interacting with all of it. This current version extends that foundation by adding an AI recommendation layer powered by the Claude API and a structured knowledge base, turning the manual task entry workflow into an intelligent assistant that can suggest what care tasks a pet needs based on its species and age.

---

## Title and Summary

**PawPal+** helps pet owners stay consistent with care routines by generating a structured daily schedule that fits within their available time. The owner adds their pet's profile and time budget, the app suggests care tasks using retrieval-augmented generation (RAG) with the Claude API, and the scheduler produces an ordered plan with conflict warnings and reasoning.

This matters because pet care consistency is easy to lose when life gets busy. Rather than requiring an owner to remember every task or manually research what a senior dog or kitten needs, PawPal+ surfaces expert-backed suggestions automatically and fits them into a realistic daily plan.

---

## Architecture Overview

The system is organized into four layers that each own a distinct responsibility.

The **Streamlit UI layer** (`app.py`) handles all user interaction: owner setup, pet management, task editing, AI suggestion display, and schedule generation. It maintains session state so the app persists data across reruns without a database.

The **AI Integration layer** (`ai_recommender.py`) retrieves care guidelines from the knowledge base (`pet_care_kb.json`) based on the pet's species and age group, then sends those guidelines as cached system context to the Claude API. Claude returns 3–5 structured task suggestions grounded in the retrieved guidelines. If no API key is present or the API is unavailable, the layer falls back to generating tasks directly from the knowledge base without calling Claude.

The **Core Business Logic layer** (`pawpal_system.py`) contains the `Task`, `Pet`, `Owner`, and `Scheduler` classes. The scheduler uses a greedy algorithm: tasks are sorted by priority (high → medium → low) and added to the plan one by one until the time budget runs out. Tasks that do not fit are placed in a skipped list with an explanation.

The **Knowledge Base** (`pet_care_kb.json`) is a structured JSON file containing care guidelines organized by species and life stage (puppy/adult/senior for dogs, kitten/adult/senior for cats). It serves as the retrieval source for the RAG pattern so that AI suggestions are always grounded in domain knowledge rather than generated from scratch.

```
Streamlit UI (app.py)
       |
AI Integration (ai_recommender.py)  <-->  Knowledge Base (pet_care_kb.json)
       |                                        |
       +---- Claude API (RAG) -----------------+
       |
Core Logic (pawpal_system.py)
  Owner / Pet / Task / Scheduler
```

---

## Setup Instructions

**1. Clone the repository and navigate to the project folder.**

```bash
git clone <your-repo-url>
cd applied-ai-system-project
```

**2. Create and activate a virtual environment.**

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows use `.venv\Scripts\activate` instead.

**3. Install dependencies.**

```bash
pip install -r requirements.txt
```

**4. Add your Anthropic API key.**

Copy the example environment file and fill in your key:

```bash
cp .env.example .env
```

Open `.env` and set:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

The app runs without an API key it will use the knowledge base fallback instead of calling Claude.

**5. Launch the Streamlit app.**

```bash
streamlit run app.py
```

The app opens in your browser at `http://localhost:8501`.

**6. Run the test suite (optional).**

```bash
python -m pytest tests/ -v
```

---

## Sample Interactions

### Example 1 — AI Suggestions for an Adult Dog

The owner sets their profile to 90 available minutes and adds a pet named Milo (dog, age 4). They click "Get AI Suggestions."

The system classifies Milo as an adult dog, retrieves care guidelines from the knowledge base, and sends them to Claude. Claude returns:

```
1. Morning Walk (30 min, high priority) adult dogs need 30–60 minutes of daily exercise to maintain
   healthy weight and reduce anxiety.
2. Breakfast Feeding (10 min, high priority) consistent twice-daily feeding prevents bloating and
   supports digestive health in adult dogs.
3. Evening Walk (30 min, medium priority) a second walk provides mental stimulation and reinforces
   routine.
4. Dental Chew Enrichment (10 min, low priority) daily chewing reduces tartar buildup and keeps
   dogs mentally engaged.
```

The scheduler fits all four tasks (80 min total) within the 90-minute budget and marks Breakfast Feeding and Morning Walk as scheduled at 07:00 and 08:00 respectively.

---

### Example 2 — Schedule Generation with a Conflict Warning

The owner manually adds two tasks at the same time slot "Evening Meds" at 18:00 and "Grooming Brush" also at 18:00 and generates the plan.

The app displays the ordered schedule and appends:

```
Conflict detected at 18:00:
  * Evening Meds (15 min, high)
  * Grooming Brush (20 min, low)

These tasks are scheduled at the same time. Consider shifting one to a different slot.
```

The plan still runs, but the owner is warned to resolve the overlap manually.

---

### Example 3 — Knowledge Base Fallback (No API Key)

If `ANTHROPIC_API_KEY` is not set, the app uses the knowledge base directly. For a senior cat (age 12), the fallback generates:

```
1. Wet Food Feeding (10 min, high priority) senior cats often have reduced kidney function;
   wet food increases water intake.
2. Gentle Play Session (15 min, medium priority) low-impact play maintains mobility in older cats.
3. Litter Box Cleaning (5 min, high priority) senior cats are more sensitive to dirty litter and
   may avoid the box if it is not cleaned daily.
```

The suggestions are surfaced immediately with a note that they were generated from the local knowledge base rather than the Claude API.

---

## Design Decisions

**Why greedy scheduling instead of an optimal search?**

A greedy approach that processes tasks in priority order and stops when time runs out is fast, predictable, and easy to explain to users. An optimal search (e.g., a knapsack solver) would maximize the total value of tasks scheduled, but it would be much harder to reason about and for a daily care app where "high priority tasks always go first" is the clear user expectation, greedy matches the mental model better than a black-box optimizer.

**Why RAG instead of purely prompting Claude?**

Prompting Claude without grounding produces plausible but inconsistent suggestions. By retrieving care guidelines specific to the pet's species and life stage before calling the API, the suggestions are anchored to domain knowledge. This also means the fallback (no API key, network error) still produces reasonable output from the same knowledge base, so the AI layer degrades gracefully rather than failing hard.

**Why prompt caching on the system message?**

The system message containing the care guidelines is the same for every pet at a given life stage. Marking it with `cache_control` allows the Anthropic API to cache it across calls, reducing latency and cost for repeated suggestion requests. This is a straightforward win given the structure of the prompts.

**Why exact time-match conflict detection instead of duration overlap?**

Pet owners plan their day in named slots ("morning," "after work") more than precise minute intervals. Detecting exact `scheduled_time` string matches is simple, transparent, and catches the most common mistake assigning two tasks to the same named slot. Implementing full duration-overlap detection would require converting `HH:MM` strings to minutes since midnight and checking interval intersections, which adds complexity for a relatively rare edge case in this domain.

**Why separate the AI layer from the core logic?**

The `ai_recommender.py` module is entirely independent of the scheduling classes. It takes a `Pet` object in and returns a list of `Task` objects out. This means the scheduler does not know or care whether tasks came from AI suggestions or manual entry they are the same objects. The separation also makes it possible to swap out the AI provider or disable it entirely without touching any scheduling code.

---

## Testing Summary

The test suite covers two areas: core scheduling logic (`tests/test_pawpal.py`, 8 tests) and the AI integration layer (`tests/test_ai_recommender.py`, 10 tests).

**What worked well:** The behavioral tests for recurrence turned out to be the most valuable. When Copilot first implemented `next_occurrence()`, it always used `date.today()` as the base date, which meant completing a recurring task twice on the same day would give both new instances tomorrow's date instead of chaining forward correctly. A test that traced through two consecutive completions caught this immediately, and fixing it to use `self.due_date` as the base locked in correct behavior. Tests for conflict detection, priority sorting, and task completion all passed from the first implementation and gave confidence that refactoring the Streamlit UI layer would not silently break the logic underneath.

**What did not work (known gaps):** The conflict detector only catches exact time-slot matches. A 60-minute task starting at 08:00 and a task starting at 08:45 will not be flagged even though they overlap in practice. The Streamlit UI layer has no automated tests any regression in session state management or UI behavior can only be caught manually. Both gaps are known trade-offs rather than oversights.

**What I learned from writing tests:** Testing each behavior in isolation first made it possible to trust that when something later broke, the failing test would point directly at the cause. Because recurrence calls `mark_complete()` internally and conflict detection reads from `pet.tasks` which is also modified by `complete_task()`, having unit tests for each piece meant that a bug in recurrence would not silently surface as a mysterious conflict detection failure downstream.

**Test confidence: 4 out of 5.** The core logic is well covered. The remaining gap is edge cases around duration overlaps and the absence of UI tests.

---

## Reliability and Evaluation

Proving that the system works required four complementary approaches: automated tests for the deterministic logic, return value signaling for the AI layer, structured logging for runtime failures, and manual evaluation for the parts that cannot be tested programmatically.

**Automated tests.** The project has 28 automated tests split across two suites. The core scheduling suite (`tests/test_pawpal.py`) contains 9 tests covering task completion, task addition, chronological sorting, daily recurrence, weekly recurrence, non-recurring task behavior, same-slot conflict detection, and a false-positive check that verifies different time slots do not produce a spurious conflict. The AI integration suite (`tests/test_ai_recommender.py`) contains 19 tests covering age classification for both dogs and cats across all life stages, knowledge base retrieval for known and unknown species, four input validation scenarios (valid task, missing field, invalid priority, zero duration, and unknown type coercion), knowledge base fallback construction, and four end-to-end generation paths (no API key, valid API response, malformed JSON response, and connection error). All 28 tests pass.

**Confidence signaling.** The `generate_task_suggestions()` function returns a `(tasks, used_ai)` tuple where `used_ai` is `True` if Claude generated the output and `False` if the knowledge base fallback ran instead. The Streamlit UI displays this distinction directly to the user, so they always know whether suggestions came from the AI or the local knowledge base. This is a lightweight but meaningful reliability signal: any API failure is transparent rather than silent.

**Logging and error handling.** `logger_config.py` configures a named `pawpal` logger that writes timestamped entries to `logs/pawpal.log`. The AI integration layer catches three failure classes separately missing API key, malformed JSON in the response, and any other exception (network timeout, rate limit, etc.) and logs each with its specific reason before falling back to the knowledge base. This means the fallback path is never a silent swallow: every time Claude is bypassed, there is a log entry explaining why.

**Human evaluation.** The Streamlit UI has no automated tests, so each UI workflow was verified manually: entering owner and pet profiles, triggering AI suggestions with and without an API key, adding and editing tasks, generating a schedule with a time budget that forces tasks to be skipped, and creating a deliberate time-slot conflict to confirm the warning message appeared. Edge cases checked manually included an owner with zero available minutes, a pet with no tasks before requesting suggestions, and dismissing a conflict warning and then regenerating the schedule.

**Summary.** All 28 automated tests passed. The AI fallback system achieved 100 percent reliability across every simulated failure mode: missing key, malformed JSON, and connection error all correctly redirected to the knowledge base path with no crash. Overall system confidence is 4 out of 5. The known gap is that the conflict detector checks exact time-slot string matches only, not duration overlaps, and the UI layer relies on manual verification rather than automated coverage.

---

## Reflection

The biggest thing this project taught me about AI is that it separates two jobs that are easy to confuse: *implementation* and *architecture*. Copilot (and Claude) can write a correct method in seconds given a clear description of what it should do. But "what it should do" is the hard part, and that judgment cannot be delegated. Every time I accepted AI-generated code without reading it, I risked building on a subtly wrong assumption. The `next_occurrence()` base-date bug is the clearest example: the code looked correct, it ran without errors, and it would have been wrong in production for any user who completed a recurring task more than once per day.

The RAG architecture taught me something different: retrieval and generation are complementary rather than interchangeable. Asking Claude to generate pet care tasks from scratch produces output that sounds confident but varies across runs and cannot be verified against a known source. Grounding the prompt in a curated knowledge base first produces output that is consistent, explainable, and can degrade gracefully to the knowledge base alone when the API is unavailable. Building a fallback path forced me to think about the knowledge base as a first-class component rather than just a prompt-stuffing trick.

The scheduling algorithm taught me to think about user mental models before algorithm elegance. A greedy priority-first scheduler is not optimal in the mathematical sense, but it is optimal for this user: someone who wants "feed and walk my dog before anything else, and stop when I run out of time." An optimal knapsack solution might sometimes schedule a cluster of low-priority tasks instead of one high-priority task, and a user would rightly find that confusing. Matching the algorithm to the user's mental model is a design decision as important as any technical trade-off.

For a future employer: this project demonstrates end-to-end applied AI system design from knowledge base construction and RAG implementation to prompt caching, fallback design, and behavioral test coverage. The code is clean, the architecture has clear boundaries, and the decisions were made deliberately with documented reasoning.
