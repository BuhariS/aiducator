# Aiducator Phase 1 Specification

## 1. Product boundary

Aiducator is a 12-week, AI-assisted Python fundamentals course for Nigerian secondary-school students. Students complete lessons and submit typed answers through protected assessment textboxes. The AI evaluates submissions against a teacher-approved rubric and recommends a score and feedback. A teacher confirms or overrides the result before it becomes final.

The first release is English-first, mobile-friendly, and designed for intermittent connectivity. It targets beginner Senior Secondary students by default; the pilot must confirm the precise year group before content is finalized.

### In scope

- Teacher-created and AI-drafted 12-week Python courses
- Teacher review, editing, versioning, and publishing
- Student enrollment, learning, assessments, feedback, retries, and progress
- Typed-answer assessment with copy, paste, cut, drop, and context-menu controls
- AI grading advice with confidence, evidence, and teacher confirmation
- Two retries after the first attempt
- Basic teacher analytics and AI usage tracking

### Deferred

- Image generation and automatic YouTube curation
- Local-language translation
- Multiplayer classrooms and live video
- Autonomous adaptive course paths
- Payment and marketplace features
- Production code execution sandbox, unless the pilot requires code execution in the first release

## 2. Course definition

The course runs for 12 weekly modules:

1. Algorithms, computing concepts, and Python setup
2. Variables, values, and data types
3. Input, output, and operators
4. Conditional statements
5. `for` and `while` loops
6. Functions and parameters
7. Strings and string methods
8. Lists, tuples, dictionaries, and sets
9. Debugging and common errors
10. Files, modules, and code organization
11. Mini-project development
12. Revision, final assessment, and presentation

Each module contains lessons, worked examples, practice activities, and at least one assessed task. All AI-generated material is a draft until a teacher approves the course version.

## 3. Learning outcomes

By the end of the course, a student can:

- Explain basic programming concepts using appropriate terminology.
- Use Python variables, values, data types, input, output, and operators.
- Write programs using conditions and loops.
- Define and call simple functions.
- Use strings and common collection types.
- Read simple Python code and explain its behavior.
- Identify and correct common syntax and logic errors.
- Write a small Python program to solve a defined problem.
- Explain the reasoning behind a programming solution.

Each outcome must map to at least one lesson and one rubric criterion.

## 4. Database schema

The schema is relational by default. JSONB is reserved for validated, versioned structures such as rubric criteria, AI responses, and artifact metadata.

### Identity and organization

| Entity | Important fields | Constraints |
|---|---|---|
| `User` | `id`, `email`, `full_name`, `preferred_language`, `is_active`, timestamps | Unique normalized email |
| `Organization` | `id`, `name`, `slug`, timestamps | Unique slug |
| `Membership` | `organization_id`, `user_id`, `role` (`owner`, `admin`, `teacher`, `student`) | Unique organization/user pair |
| `Cohort` | `organization_id`, `name`, `start_date`, `end_date`, `teacher_id` | Teacher must belong to organization |

Platform administrators may have a separate global permission rather than being represented as a student-facing organization role.

### Courses and content

| Entity | Important fields | Constraints |
|---|---|---|
| `Course` | `organization_id`, `created_by`, `title`, `slug`, `description`, `duration_weeks`, `passing_score`, `max_retries`, `status` | `duration_weeks=12`, `passing_score=70`, `max_retries=2` by default |
| `CourseVersion` | `course_id`, `version_number`, `status`, `generated_by_ai`, `approved_by`, `approved_at` | Published versions are immutable; unique course/version |
| `Module` | `course_version_id`, `title`, `position` | Unique course version/position |
| `LessonVersion` | `module_id`, `title`, `objectives`, `content`, `position`, `status` | Unique module/position; published content is immutable |
| `LessonArtifact` | `lesson_version_id`, `artifact_type`, `content`, `metadata`, `is_active`, `position` | Only allowlisted artifact types and URLs |
| `Translation` | `lesson_version_id`, `language_code`, `content`, `status` | Unique lesson version/language |

Suggested artifact types are `text`, `video_embed`, `image`, `simulation_link`, and `code_example`. Uploaded assets should use object storage rather than database blobs.

### Enrollment and progress

| Entity | Important fields | Constraints |
|---|---|---|
| `Enrollment` | `course_id`, `course_version_id`, `student_id`, `cohort_id`, `status`, timestamps | Unique active course/student enrollment |
| `LessonProgress` | `enrollment_id`, `lesson_version_id`, `status`, `best_score`, `attempts_used`, `completed_at` | Unique enrollment/lesson; attempts cannot exceed three |
| `CourseCompletion` | `enrollment_id`, `completed_at`, `confirmed_by` | One completion per enrollment |

Progress belongs to an enrollment, not directly to a user, so a student can repeat a course or belong to different cohorts.

### Assessments and teacher review

| Entity | Important fields | Constraints |
|---|---|---|
| `Question` | `lesson_version_id`, `question_type`, `prompt`, `max_score`, `position` | Question belongs to a published lesson version |
| `RubricVersion` | `question_id`, `criteria`, `total_score`, `approved_by`, `version_number` | Criteria must pass schema validation |
| `Attempt` | `enrollment_id`, `question_id`, `attempt_number`, `answer_text`, `status`, timestamps | Attempt number is 1, 2, or 3; unique enrollment/question/attempt number |
| `AIGrade` | `attempt_id`, `suggested_score`, `confidence`, `strengths`, `mistakes`, `feedback`, `remediation`, `model`, `prompt_version`, `raw_response` | One AI grade per attempt; raw response is access-controlled |
| `GradeDecision` | `attempt_id`, `final_score`, `status` (`provisional`, `confirmed`, `overridden`), `decided_by`, `reason` | One final decision per attempt |
| `ReviewQueueItem` | `attempt_id`, `reason`, `status`, `assigned_to`, timestamps | One open review item per attempt |

The first submission plus two retries is the complete attempt allowance. A confirmed score of 70 or higher passes. A failed attempt exposes remediation feedback and the next retry when attempts remain.

### Operations, AI, and audit

| Entity | Important fields | Constraints |
|---|---|---|
| `AIJob` | `job_type`, `entity_type`, `entity_id`, `status`, `progress`, `retry_count`, `error_message`, timestamps | Jobs are idempotent and retryable |
| `AIUsageEvent` | `job_id`, `provider`, `model`, `input_tokens`, `output_tokens`, `estimated_cost` | Immutable cost record |
| `AuditLog` | `actor_id`, `action`, `entity_type`, `entity_id`, `metadata`, timestamp | Append-only for grade, publish, and permission events |
| `Notification` | `recipient_id`, `notification_type`, `title`, `body`, `read_at` | User-scoped |
| `XPEvent` | `student_id`, `enrollment_id`, `event_type`, `points`, `source_id`, timestamp | Awarded only from confirmed events |

## 5. Core user journeys

### Student onboarding and enrollment

1. Student signs in or is invited by a teacher.
2. Student joins an organization or cohort.
3. Student views the Python course overview and outcomes.
4. Student enrolls or is enrolled by a teacher.
5. Student completes a diagnostic assessment.
6. Dashboard shows starting level, current module, and next action.

### Student learning and assessment

1. Student opens the current lesson.
2. Student consumes active lesson artifacts.
3. Student completes practice activities.
4. Student opens the assessment.
5. Protected textbox blocks copy, paste, cut, drop, and context menu actions.
6. Student submits a typed answer.
7. The server stores an immutable attempt and starts an AI job.
8. The student sees an evaluation state, then feedback and a provisional score.
9. A teacher confirms or changes the result.
10. The platform marks the lesson passed or exposes remediation and a retry.

### Student remediation and retry

1. A failed result displays the missed rubric criteria.
2. The student receives a targeted explanation and practice recommendation.
3. The retry button becomes available if attempts remain.
4. The student submits attempt two or three.
5. The best confirmed score is retained for progress.
6. After the third failed attempt, the lesson is marked `needs_teacher_support`.

### Teacher course creation

1. Teacher opens Course Studio and enters an outline or selects a template.
2. Teacher starts AI generation.
3. The interface shows job progress, errors, and partial completion.
4. AI creates a draft course version, lessons, questions, and rubric suggestions.
5. Teacher reviews and edits every generated lesson and assessment.
6. Teacher approves a rubric and publishes the version.
7. Students can enroll only in published versions.

### Teacher grading review

1. Teacher opens the review queue.
2. The queue prioritizes low-confidence, borderline, flagged, and appealed attempts.
3. Teacher sees the student answer, rubric, AI reasoning, and prior attempts.
4. Teacher confirms or overrides the recommendation.
5. Teacher records an optional reason.
6. Progress, notifications, and XP update only after confirmation.

### Teacher analytics

1. Teacher selects a course, cohort, or lesson.
2. Teacher sees completion, scores, retries, common errors, and students needing help.
3. Teacher compares AI recommendations with confirmed grades.
4. Teacher exports a summary without exposing unnecessary student data.

## 6. Screen list

### Shared screens

- Sign in
- Invitation acceptance and account setup
- Password reset
- Profile and accessibility settings
- Notifications
- Help and feedback

### Student screens

- Student dashboard: current lesson, progress, streak, retries, and recommended next step
- Course catalog
- Course detail and enrollment
- Learn screen: lesson content and step accordion
- Assessment screen: prompt, rubric guidance, protected textbox, character count, and submit action
- Evaluation state: queued, processing, failed, or complete
- Feedback screen: score, strengths, mistakes, remediation, teacher-review state, and retry action
- Progress screen: module completion, scores, attempts, and course outcome
- Course completion screen

### Teacher screens

- Teacher dashboard: active courses, pending reviews, cohort progress, and AI job status
- Course Studio: outline, module tree, lesson list, and generation action
- Generation status: job progress, partial results, retry, and error details
- Lesson editor: content, artifacts, objectives, and preview
- Assessment editor: question, expected concepts, rubric criteria, and scoring guidance
- Publish review: draft changes, validation errors, and approval action
- Student roster and individual student profile
- Manual review queue
- Attempt review: answer, rubric, AI recommendation, history, and teacher decision
- Course analytics
- AI usage and cost view

### Administrator screens

- Organization and user management
- Course moderation
- Platform analytics
- AI usage and cost monitoring
- Audit log

## 7. Technical acceptance criteria

### Foundation

- `AC-001`: Python dependencies install successfully with `uv sync`.
- `AC-002`: The application runs with `uv run` and uses environment variables for secrets and database settings.
- `AC-003`: Tailwind CSS builds locally with `npm run build`; production templates do not depend on the Tailwind CDN.
- `AC-004`: The UI uses responsive Tailwind components with visible focus states, keyboard navigation, and readable contrast.
- `AC-005`: All protected actions enforce authentication, CSRF protection, and object-level authorization.

### Course management

- `AC-010`: A teacher can create, edit, preview, and save a draft course.
- `AC-011`: A course defaults to 12 weeks, a 70 passing score, and two retries, with authorized teacher overrides.
- `AC-012`: A teacher can publish a course version only after required lessons, questions, and rubrics pass validation.
- `AC-013`: Published course content is immutable; edits create a new version.
- `AC-014`: Students cannot access draft or unapproved course versions.

### AI authoring

- `AC-020`: AI generation runs asynchronously and never blocks the HTTP request until completion.
- `AC-021`: Every AI job exposes status, progress, retry, failure, model, prompt version, and estimated cost.
- `AC-022`: Malformed or unsafe AI output is rejected and shown as a teacher-actionable error.
- `AC-023`: AI-generated lessons, questions, rubrics, and media suggestions remain drafts until teacher approval.
- `AC-024`: AI prompts do not include unnecessary personally identifiable student data.

### Assessment and grading

- `AC-030`: The assessment textbox blocks copy, paste, cut, drop, and context menu events in controlled assessment mode.
- `AC-031`: The server treats browser controls as untrusted and stores only the submitted answer and permitted event metadata.
- `AC-032`: An enrollment/question pair cannot create more than three attempts.
- `AC-033`: The student cannot submit a new attempt while another evaluation is active.
- `AC-034`: AI grading returns a schema-valid score, confidence, evidence, feedback, remediation, and review recommendation.
- `AC-035`: Low-confidence, borderline, flagged, or appealed attempts enter the review queue.
- `AC-036`: A score is not final until a teacher confirms or overrides it.
- `AC-037`: A confirmed score of 70 or higher passes the lesson; a lower score exposes remediation when retries remain.
- `AC-038`: The third failed confirmed attempt marks the lesson as requiring teacher support.
- `AC-039`: Every grade change records the actor, previous score, new score, reason, and timestamp.

### Progress and analytics

- `AC-040`: Progress is calculated from confirmed grades only.
- `AC-041`: XP, streaks, and badges are generated from immutable confirmed events.
- `AC-042`: Teachers can see completion, scores, attempts, common errors, and review volume by cohort.
- `AC-043`: AI grading accuracy can be calculated by comparing AI recommendations with teacher decisions.
- `AC-044`: AI token usage and estimated cost are visible to authorized administrators.

### Reliability and safety

- `AC-050`: Celery jobs are idempotent and retry transient provider failures without creating duplicate grades or course content.
- `AC-051`: AI-generated HTML is sanitized before rendering.
- `AC-052`: External media URLs are validated against an allowlist and cannot trigger server-side requests.
- `AC-053`: Student answers, rubrics, grades, and audit logs are access-controlled and covered by retention rules.
- `AC-054`: The platform records provider, model, prompt version, and response metadata for each AI evaluation.
- `AC-055`: Automated tests cover permissions, attempt limits, grading transitions, retry behavior, and published-content immutability.

## 8. Initial HTMX interaction contract

The first implementation should use server-rendered HTML and small partial responses:

```text
POST /courses/{course_id}/generate/
GET  /ai-jobs/{job_id}/status/
POST /questions/{question_id}/attempts/
GET  /attempts/{attempt_id}/status/
GET  /attempts/{attempt_id}/feedback/
POST /reviews/{review_id}/decision/
POST /lessons/{lesson_id}/retry/
```

Every endpoint must return an appropriate HTML partial, preserve form errors, and enforce the same authorization rules as a full-page request.

## 9. Pilot readiness gate

The pilot can begin when:

- One complete 12-week course is teacher-reviewed and published.
- At least one teacher can manage a cohort without administrator intervention.
- Student attempts, retries, grades, and progress are auditable.
- AI recommendations have been compared against a human-scored sample.
- Browser assessment controls work on supported devices and an accommodation process exists.
- The platform can measure learning improvement, completion, grading accuracy, and teacher time saved.
