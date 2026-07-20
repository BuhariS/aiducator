# Aiducator

AI-assisted Python learning for Nigerian secondary-school students and teachers.

## Local setup

Install Python dependencies with `uv`:

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

The default local database is SQLite. For PostgreSQL, start the bundled service with `docker compose up -d postgres` and set `DATABASE_URL=postgresql://aiducator:aiducator@localhost:5432/aiducator` in `.env`. Redis is available with `docker compose up -d redis`.

Create accounts at `/accounts/signup/`, or use the role-specific entry points `/accounts/signup/student/` and `/accounts/signup/teacher/`. Teacher signup requires a school or organization name and creates that organization plus a teacher membership. Student signup creates a personal learning organization plus a student membership. Students and teachers are associated through these organization memberships.

Seed the first Python course and demo accounts:

```bash
uv run python manage.py seed_python_course
```

New demo accounts use `Aiducator123!` unless `AIDUCATOR_SEED_PASSWORD` is set before running the command. The command is safe to run repeatedly.

## Local database reset and demo data

For the default local SQLite database only, stop the development server, move the existing database to a timestamped backup, then migrate and seed fresh demo data:

```bash
mv db.sqlite3 "db.sqlite3.backup.$(date +%Y%m%d%H%M%S)"
uv run python manage.py migrate
uv run python manage.py seed_python_course
```

Do not run these commands against a shared or production database. For PostgreSQL, use an environment-specific backup and reset procedure instead.

## Course publishing and archive lifecycle

Draft courses can be deleted when no learner is enrolled. Published courses and their published versions are immutable, so a published course must be archived rather than deleted. Archiving removes the course from the catalog and prevents new enrollment while retaining its teaching history. An archived course can be deleted only when it has no enrollments.

Install the frontend dependency and build Tailwind CSS:

```bash
npm install
npm run build
```

Use `npm run dev` during UI development. The implementation plan, schema, user journeys, screen inventory, and acceptance criteria are in `docs/phase-1-specification.md`. Phase 3 workflow details are in `docs/phase-3-implementation.md`.

Teacher course-generation details are in `docs/phase-4-course-generation.md`.

Content safety and production security controls are documented in `docs/content-safety.md`.

Gamification event rules and teacher/administrator analytics are documented in `docs/gamification-analytics.md`.

## AI grading worker

Copy `.env.example` to `.env`. The default `fake` provider is safe for local development. The only supported `AI_LLM_PROVIDER` values are `fake` and `openai`. To use OpenAI, set `AI_LLM_PROVIDER=openai` and provide a non-empty `OPENAI_API_KEY` in `.env`; the app fails at startup if this configuration is missing or unsupported. Keep the key server-side and never expose it to templates or JavaScript.

In local debug mode, generation runs eagerly by default, so Redis and a worker are optional. To run the production-style asynchronous workflow, set `CELERY_TASK_ALWAYS_EAGER=0`, then start Redis and the Django worker in separate terminals:

```bash
docker compose up -d redis
uv run celery -A config worker --loglevel=INFO
uv run python manage.py runserver
```

For production, set `STORAGE_BACKEND=s3` and provide the AWS-compatible bucket and endpoint variables from `.env.example`. Session and CSRF cookies become secure when `DJANGO_DEBUG=0`; configure SMTP variables to enable password-recovery email delivery.

Student submissions create a queued `AIJob`. The worker evaluates the answer with structured output, creates a teacher review item, and records provider usage. Teachers review submissions at `/assessments/reviews/`; confirmed grades update progress, notifications, and XP.
