# Phase 4: Teacher Course Generation

## Teacher workflow

1. Choose manual authoring or **Generate with AI** from the teacher dashboard.
2. Submit a course title, objective, duration, audience, optional translation languages, and a free-form prompt.
3. A Celery `AIJob` is created with progress, retry, provider, model, prompt-version, token, cost, and error metadata.
4. The provider returns a structured `CourseGenerationResult` validated by Pydantic before persistence.
5. A private draft `CourseVersion` is created with lessons, objectives, artifacts, questions, rubrics, and translation drafts.
6. The teacher reviews and edits the draft in Course Studio.
7. The existing validation and publish action remains the only path to a published immutable version.

## Supported generated content

- Lesson explanations and suggested objectives
- Text, code examples, image prompts, and YouTube search suggestions
- Scenario, critical-thinking, task-prompt, misconception, error-identification, explanation, code-writing, debugging, and reflection questions
- Rubric criteria for every generated question
- Translation drafts for requested language codes

Generated image prompts and YouTube suggestions are stored as reviewable text artifacts. They are not silently converted into media or published.

## Local operation

Start Redis and the worker in separate terminals:

```bash
docker compose up -d redis
uv run celery -A config worker --loglevel=INFO
uv run python manage.py runserver
```

Open `/teacher/courses/generate/` as a teacher. With the default `AI_LLM_PROVIDER=fake`, generation is deterministic and safe for local development. Set `AI_LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and the course prompt/cost settings to use a live provider.

The generated draft is never published by the Celery task. Teachers must use Course Studio validation and the explicit publish action.
