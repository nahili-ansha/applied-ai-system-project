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
