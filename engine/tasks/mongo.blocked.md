# blocked — task mongo

none. the acceptance test passed against the spec as written; no frozen file needed a change.

not a blocker for this task, already tracked in `engine/tasks/blocked.md`: `MONGODB_URI` is absent
from `.env`, so the live mirror cannot be exercised here. tests inject a fake database by design;
the CLI flag that turns the sink on comes in task `wire`.
