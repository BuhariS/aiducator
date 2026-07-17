# Phase 3 implementation

## Teacher workflow

1. Create a course from `/teacher/courses/new/`.
2. Create a private draft version, modules, and lessons.
3. Add text, code examples, video links or uploads, image links or uploads, and simulation links.
4. Add questions and teacher-approved rubric criteria.
5. Preview every lesson through the student-view preview.
6. Publish only after validation passes.

Published course versions, modules, lessons, artifacts, translations, questions, and rubrics reject edits and deletes at the model layer. New changes start in a new draft version, while enrollments remain pinned to their selected course version.

## Student workflow

Students enroll in the latest published version, navigate module-by-module, consume lesson content and artifacts, submit controlled assessments, view teacher-confirmed feedback, and progress through completed lessons. Content-only lessons can be marked complete; assessed lessons complete after a passing teacher-confirmed grade.

## Accessibility

Students can request support from an assessment page. Teachers review requests at `/assessments/accommodations/`. Copy/paste, cut, drop, and context-menu deterrents remain enabled unless a teacher approves a copy/paste accommodation for that course. Browser enforcement is not treated as a security boundary.

## Validation

```bash
uv run python manage.py migrate
uv run python manage.py check
uv run python manage.py test
```
