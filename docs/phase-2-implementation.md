# Phase 2 implementation

## Identity and authorization

- `accounts.User` is the email-based custom user model.
- Organizations, memberships, and cohorts are scoped through foreign keys.
- `accounts.access` provides explicit student, teacher, and administrator role checks.
- Course authoring and review services require an actor and verify organization access.
- Dashboards and object views enforce access in the view or service, not only in middleware.

## Dashboards and authentication

- `/dashboard/administrator/` is scoped to organizations where the user is an owner or administrator.
- `/dashboard/teacher/` and `/dashboard/student/` reject users without the corresponding role.
- Password recovery is available under `/accounts/password-reset/`.
- Session cookies, CSRF cookies, HSTS, SSL redirects, password validators, and reset-token expiry are environment-configurable.

## Infrastructure

- `DATABASE_URL` supports PostgreSQL through `dj-database-url`; SQLite remains the local default.
- Redis and Celery are configured for JSON tasks, startup retries, and Africa/Lagos timezone operation.
- Local filesystem storage is the default; S3-compatible object storage is enabled with `STORAGE_BACKEND=s3`.
- Application and Django request logs are sent to structured console logging for container deployment.

## Verification

Run the checks and tests with:

```bash
uv run python manage.py check
uv run python manage.py test
```
