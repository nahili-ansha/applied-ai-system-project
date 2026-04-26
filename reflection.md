# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.

My initial design consists of four classes. Owner stores the owner's name and daily time available. Pet stores the pet's name and species. Task stores a task's title, duration in minutes, and priority level. Scheduler takes an Owner, a Pet, and a list of Tasks as input and produces an ordered daily plan by sorting tasks by priority and checking that total duration fits within the owner's available time.

- What classes did you include, and what responsibilities did you assign to each?

- Owner: stores owner name and available time per day (in minutes) to be used by the Scheduler for the time budget

- Pet: stores pet name and species to be passed into the Scheduler for context in the output

- Task: stores task title, duration (minutes), and priority (low/medium/high) to be used by the Scheduler for operation

- Scheduler: takes an Owner, Pet, and list of Tasks, sorts tasks by priority,filters out tasks that don't fit in available time, and returns an ordered daily plan with reasoning

**b. Design changes**

- Did your design change during implementation? yes
- If yes, describe at least one change and why you made it.

The Scheduler now has self.remaining_minutes which starts at owner.available_minutes and gets decremented in generate_plan() to track the time budget properly

Why? initially has_time_for() function doesn't track the remaining time and available_time never decreases , so calling it twice with 2 tasks could say yes to both even if they exceed the budget


---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers two primary constraints: time budget (the owner's available minutes for the day) and task priority (high/medium/low). It also uses scheduled_time as an optional soft constraint for display ordering, and recurrence as a forward-planning constraint that generates future tasks automatically.

Priority was weighted most heavily because a pet missing meds or a meal is a real welfare issue, those tasks need to run even if time is tight. Time budget was the hard cutoff: no matter how many tasks exist, the plan cannot exceed what the owner can realistically do. Scheduled time and recurrence were treated as secondary because they affect organization and planning, not the immediate daily decision of what gets done.

**b. Tradeoffs**

The conflict detector checks for exact scheduled_time matches (e.g., both tasks say 08:00) than checking whether task durations overlap (e.g., a 30-minute task at 08:00 and a 20-minute task at 08:15 would overlap in real life but undetected).

This is a reasonable  because pet care tasks are typically assigned to named time slots like "morning walk," "breakfast," "evening meds"  than precise start times down to the minute. Implementing full duration-overlap detection would require converting HH:MM strings into comparable time objects, calculating end times, and checking range intersections which is more complex given how pet owners actually plan their day.

---

## 3. AI Collaboration

**a. How you used AI**

I used Copilot as my primary AI collaborator throughout the project. It was most effective in three phases:

- **Implementation support** I described what I wanted each method to do in plain English ("filter tasks by completion status," "sort by HH:MM time") and Copilot translated those into correct Python with the right data structures. This was faster than writing boilerplate from scratch and let me focus on whether the logic was right rather than syntax.
- **Debugging**  When the Streamlit app threw `AttributeError: 'NoneType' object has no attribute 'pets'`, I pasted the traceback and Copilot diagnosed that `st.stop()` wasn't preventing execution and restructured the guard correctly.
- **Incremental feature building** Each feature (recurrence, conflict detection, UI components) was added in a focused conversation. Copilot explained the tradeoff of each approach before writing the code, which helped me understand what I was accepting.

The most effective prompts were specific and outcome-focused: "add a method that returns tasks sorted chronologically, tasks with no time go last" produced better results than open ended requests like "improve the scheduler."

**b. Judgment and verification**

When Copilot first implemented `next_occurrence()`, it always used `date.today()` as the base date for calculating the next due date. I noticed this would be wrong for chained completions if you completed a daily task twice on the same day, both new tasks would get tomorrow's date instead of day+1 and day+2.

I asked Copilot to fix it to use `self.due_date` as the base when it exists, falling back to `date.today()` only when no due date is set. I verified this by tracing through the logic manually: complete task with `due_date=2026-03-29` → next due is `2026-03-30` → complete that → next due is `2026-03-31`. I then added the chain completion test in `test_pawpal.py` to lock in this behavior so it couldn't regress.

---

## 4. Testing and Verification

**a. What you tested**

I tested five behavioral areas: task completion status, task addition, chronological sorting, recurrence logic, and conflict detection. Each test was written to verify one specific outcome for example, that completing a daily task produces exactly one new task with a due date of tomorrow, not two, and not with today's date.

These tests mattered because the features interact. Recurrence calls `mark_complete()` internally; conflict detection reads from `pet.tasks` which is also modified by `complete_task()`. Testing each behavior in isolation made it possible to trust that when something broke, the failing test would point directly at the cause rather than somewhere downstream.

**b. Confidence**

⭐⭐⭐⭐ (4 / 5)

The scheduling logic, recurrence, sorting, and conflict detection all work correctly for the cases I tested. My confidence drops slightly for two reasons: the conflict detector only catches exact time-slot matches and would miss a 30-minute task at 08:00 overlapping a task at 08:15, and the Streamlit UI has no automated tests regressions there would only surface manually. Given more time I would test: completing a recurring task with no `due_date` set, tasks whose total duration exactly equals `available_minutes`, and generating a schedule when all tasks are already completed.

---

## 5. Reflection

**a. What went well**

The recurrence system is the part I'm most satisfied with. The design `next_occurrence()` on `Task`, `complete_task()` on `Pet`, `mark_task_complete()` on `Scheduler` delegating down  keeps each class responsible for only what it owns. `Task` knows how to copy itself. `Pet` knows how to append to its own list. `Scheduler` doesn't need to know about either. That separation made it easy to test each piece independently and meant adding recurrence didn't require touching the core scheduling algorithm at all.

**b. What you would improve**

I would replace the exact time-match conflict detector with a proper duration-overlap check. The current approach compares `scheduled_time` strings, so two tasks at `"08:00"` conflict but a 60-minute task at `"08:00"` and a task at `"08:45"` do not even though they clearly overlap. The fix would convert `HH:MM` to total minutes since midnight and check whether `[start, start + duration]` intervals intersect, which is a standard range-overlap problem: two ranges overlap if `start_a < end_b and start_b < end_a`.

**c. Key takeaway**

The most important thing I learned is that AI is a powerful implementer but a poor architect and those are different jobs. Copilot could write a correct `next_occurrence()` method in seconds, but it couldn't know that the base date should chain from `self.due_date` rather than always rebasing to today until I thought through the behavior myself and caught the issue. Every time I accepted AI output without reading it, I risked building on a subtly wrong assumption. The lead architect's job is not to write every line it's to define what "correct" means, verify that the code matches that definition, and push back when it doesn't.

---

## 6. Responsible AI

**a. Limitations and biases**

The most significant limitation is species coverage. The knowledge base only contains guidelines for dogs and cats. Any other species such as rabbits, birds, or hamsters falls through to a generic adult profile that was written as a catch all rather than as accurate guidance for that animal. An owner entering a rabbit would receive suggestions designed for a generic pet, not one calibrated to a rabbit's actual dietary, environmental, or behavioral needs. Within dogs and cats, the age thresholds are fixed: dogs become senior at age 8 and cats at age 11 regardless of breed or size. In veterinary practice a seven year old large breed dog is already considered senior while a seven year old toy breed is not, but the system treats them identically. The knowledge base also reflects general best practices and cannot account for individual health conditions, a specific vet's instructions, or breed specific care. Claude's suggestions introduce a second layer of variability because generative output is non-deterministic: two identical pet profiles submitted on different days may receive slightly different task recommendations even though the underlying knowledge base has not changed.

**b. Misuse potential and prevention**

The most realistic misuse scenario is an owner treating the AI's suggestions as a substitute for veterinary advice. A pet recovering from surgery, managing a chronic condition, or on a restricted diet needs professional guidance, not an automated task list. The app does not include a disclaimer making this distinction clear, which is a gap. Adding a visible note that suggestions reflect general care guidelines and are not a replacement for a vet's recommendations would reduce this risk without changing the functionality.

A second concern is that the app does not validate the pet profile beyond checking that a name and species are provided. An owner who enters an incorrect age or the wrong species receives suggestions calibrated for a pet that does not match their actual animal. This is unlikely to be deliberate misuse but could lead to inappropriate care through honest data entry errors. Adding a brief confirmation step ("Your dog Milo is 4 years old is this correct?") before generating suggestions would catch most of these mistakes.

On the technical side, the API key is stored in a local `.env` file. If someone were to deploy this app publicly without securing that file, the key could be exposed in the repository or through the server environment. The `.gitignore` already excludes `.env`, but anyone forking or deploying the project needs to understand that the key must be set in the deployment environment and never committed to version control.

**c. Surprises during reliability testing**

The biggest surprise was how important the malformed JSON fallback turned out to be in practice. I expected the most common failure mode to be a missing API key, but during testing I discovered that Claude occasionally returns a brief preamble sentence before the JSON block, or wraps the output in markdown fencing, which causes the JSON parser to fail. Without an explicit catch for that case, the failure would surface as an unhandled exception in the UI rather than a graceful fallback. Writing a test specifically for malformed JSON responses exposed this early and led directly to the `try/except json.JSONDecodeError` block in `ai_recommender.py`. I would not have anticipated this without the test.

The second surprise was how useful the `used_ai` return value turned out to be during development. At one point I thought Claude was generating suggestions but the output looked identical to the knowledge base fallback. The boolean flag made it immediately obvious that the API key in my `.env` file had a typo and the fallback had been running silently the entire time. A test that only checked whether tasks were returned would have missed this entirely.

**d. AI collaboration: one helpful suggestion and one flawed one**

The most helpful suggestion came when the Streamlit app threw `AttributeError: 'NoneType' object has no attribute 'pets'` at startup. I pasted the traceback into Copilot and it immediately diagnosed that Streamlit's rerun model does not stop execution cleanly at `st.stop()` in the way I expected. It restructured the guard to call `st.error()` followed by `st.stop()` inside an `if "owner" not in st.session_state` block placed before any code that touched the owner object. That fix worked on the first try and taught me something about how Streamlit reruns work that I would have spent much longer debugging on my own.

The flawed suggestion was Copilot's first implementation of `next_occurrence()`. It calculated the next due date using `date.today()` as the base, which looks correct at first glance since completing a task today should schedule the next one for tomorrow. The bug only appears when a recurring task is completed more than once on the same day: both new instances get tomorrow's date rather than chaining forward to day plus one and day plus two respectively. I caught this by thinking through the chained completion scenario manually and then writing a test that completed the same daily task twice in sequence and checked that the due dates were one day apart. Copilot had optimized for the common case and missed the edge case entirely. The fix, using `self.due_date` as the base when it exists and falling back to `date.today()` only when no due date is set, was something I had to identify and specify myself before Copilot could implement it correctly.
