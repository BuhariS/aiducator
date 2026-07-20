# Phase 4: Teacher Course Generation

## Teacher workflow

1. Choose manual authoring or **Generate with AI** from the teacher dashboard.
2. Submit a course title, objective, duration, audience, selected assessment types, and a free-form prompt.
3. A Celery `AIJob` is created with progress, retry, provider, model, prompt-version, token, cost, and error metadata.
4. The provider returns a structured `CourseGenerationResult` validated by Pydantic before persistence.
5. A private draft `CourseVersion` is created with lessons, objectives, questions, and rubrics.
6. The teacher reviews and edits the draft in Course Studio.
7. The existing validation and publish action remains the only path to a published immutable version.

## Generated content boundaries

- Lesson titles, content, and learning objectives
- Only the assessment types selected by the teacher: scenario, critical thinking, task prompt, misconception, or reflection
- Rubric criteria for every generated question

The AI must not return learning materials or artifacts such as text supplements, video URLs, embeds, image prompts, simulations, or code examples. Teachers can still add and manage learning materials manually in Course Studio.

## Local operation

Start Redis and the worker in separate terminals:

```bash
docker compose up -d redis
uv run celery -A config worker --loglevel=INFO
uv run python manage.py runserver
```

Open `/teacher/courses/generate/` as a teacher. With the default `AI_LLM_PROVIDER=fake`, generation is deterministic and safe for local development. To use a live provider, set `AI_LLM_PROVIDER=openai` and a non-empty `OPENAI_API_KEY`; startup rejects unsupported provider values or missing OpenAI credentials.

The generated draft is never published by the Celery task. Teachers must use Course Studio validation and the explicit publish action.
