# Aiducator

AI-native Learning Management System (LMS) for AI era.
## Inspiration

Large Language Models (LLMs) have revolutionized education, offering an incredible ability to generate rich academic content at unprecedented speed. However, because LLMs operate on probabilistic patterns, their outputs aren't infallible: they can contain subtle logical flaws, biases, or factual hallucinations.

While AI excels at automating the foundational levels of Bloom’s Taxonomy (remembering and understanding) at scale, the true future of education lies in elevated critical thinking. To safely and effectively leverage AI, learners must develop skills in prompt engineering, critical evaluation, and error detection.

Driven by this vision, I collaborated with **GPT-5.6 Luna** to rapidly prototype **Aiducator**—a modern Learning Management System (LMS) designed to transform how we learn and teach.

### Key Objectives:

* **For Learners:** Shift focus toward higher-order critical thinking by prompting students to analyze, critique, and evaluate AI-generated course content and assessments.
* **For Educators:** Eliminate administrative burn-out. Aiducator automates course creation, assessment design, and learning analytics, freeing up valuable time for teachers to provide personalized mentorship, tailored guidance, and timely instructional adjustments.

## What I Learned

Tools like **Codex** and **GPT-5.6** are profound force multipliers. When guided effectively, they drastically compress the development lifecycle: reducing both the time and cost required to turn high-impact ideas into real-world software that serves humanity.

## How Aiducator Was Built

The development workflow followed an iterative, human-in-the-loop co-creation model:

1. **Problem Definition & Architecture:** I defined the core problem, selected the tech stack, and authored the initial software functional specifications.
2. **AI Architectural Review:** I submitted the specifications to the AI model for critical analysis, stress-testing, and suggestions. I then synthesized these insights to produce a final, optimized blueprint.
3. **Phased Implementation:** I fed the refined specifications into Codex powered by GPT-5.6 Luna. Codex structured the project into logical execution phases and handled the heavy lifting—from initial scaffold drafting to test execution.
4. **Co-Creation & Refinement:** Working phase-by-phase alongside Codex, I evaluated the generated code, refined components, debugged edge cases, and managed version control commits and remte update.

## Challenges

The sheer speed and capability of Codex and GPT-5.6 presented a unique challenge: **managing scope and abstraction**. Because the AI could generate complex features so rapidly, I was at times stuck in the implementation details.

## Next Steps
To build upon Aiducator's foundational LMS capabilities, future development will expand beyond text and traditional assessments into fully multimodal learning environments:

- AI-Generated Academic Videos: Integrate video synthesis tools to automatically produce tailored bite-sized lecture clips and visual walkthroughs for complex topics.

- Automated Educational Infographics: Expand generative workflows to output structured visual summaries, process diagrams, and data charts that aid visual learners.

- Interactive Science & Physics Simulations: Enable real-time generation of interactive sandbox environments and simulations, allowing students to manipulate variables directly to deepen conceptual understanding.

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
