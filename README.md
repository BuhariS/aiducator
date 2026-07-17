# AIDUCATOR

AI-assisted Python learning for Nigerian secondary-school students and teachers.

## Local setup

Install Python dependencies with `uv`:

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Create accounts at `/accounts/signup/`, or use the role-specific entry points `/accounts/signup/student/` and `/accounts/signup/teacher/`. Teacher signup creates a private organization workspace; every account receives the corresponding student or teacher membership.

Seed the first Python course and demo accounts:

```bash
uv run python manage.py seed_python_course
```

New demo accounts use `AIDUCATOR123!` unless `AIDUCATOR_SEED_PASSWORD` is set before running the command. The command is safe to run repeatedly.

Install the frontend dependency and build Tailwind CSS:

```bash
npm install
npm run build
```

Use `npm run dev` during UI development. The implementation plan, schema, user journeys, screen inventory, and acceptance criteria are in `docs/phase-1-specification.md`.

## AI grading worker

Copy `.env.example` to `.env`. The default `fake` provider is safe for local development. To use OpenAI, set `AI_LLM_PROVIDER=openai` and provide `OPENAI_API_KEY` in `.env`. Keep the key server-side and never expose it to templates or JavaScript.

Start Redis and the Django worker in separate terminals:

```bash
docker compose up -d redis
uv run celery -A config worker --loglevel=INFO
uv run python manage.py runserver
```

Student submissions create a queued `AIJob`. The worker evaluates the answer with structured output, creates a teacher review item, and records provider usage. Teachers review submissions at `/assessments/reviews/`; confirmed grades update progress, notifications, and XP.
