# Gamification and analytics

## Gamification rules

Gamification is event-driven. Learning services create immutable `XPEvent`,
`StreakEvent`, `BadgeAward`, and `PraiseNotification` records after a lesson
or assessment is confirmed. XP is not maintained by incrementing a value on a
student profile, so every award has a reason, source, and optional metadata.

Use `gamification.services.correct_xp()` for teacher corrections. It creates a
new correction event linked to the original event; it never edits or deletes
the original record. Rewards are idempotent for the same source event.

## Analytics routes

- `/analytics/teacher/` — teacher course completion, assessment performance,
  common mistakes, learners needing help, AI overrides, AI/human score gaps,
  lesson time, and lesson drop-off.
- `/analytics/administrator/` — scoped administrator reporting for active
  users, course usage, AI request volume and error rate, token usage, cost, and
  manual review volume.
- `/analytics/lessons/<lesson-id>/time/` — authenticated student-only POST
  endpoint used by the learning screen to record lesson time.

Analytics are scoped to the teacher's created courses or the administrator's
organizations. Lesson-time events are immutable and limited to one second
through one hour per browser event. Browser time is an engagement signal, not
proof of learning.

## Operational notes

Run `uv run python manage.py migrate` after pulling these changes. The Django
admin exposes the event records under **Analytics** and **Gamification** for
auditing and support.
