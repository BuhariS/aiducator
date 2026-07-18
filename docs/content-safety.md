# Content safety and security

Aiducator applies these controls before AI-generated material reaches learners:

- AI prompts are length-limited, teacher prompts reject common instruction-override patterns, and provider prompts label learner and teacher data as untrusted.
- Provider inputs are minimized and redact email addresses and phone numbers. Raw student answers are encrypted with `AI_FIELD_ENCRYPTION_KEY` (or a key derived from `DJANGO_SECRET_KEY` for local development).
- Structured AI output is schema-validated, moderated for executable markup, sanitized before draft persistence, and never published automatically.
- Generated learning materials require the teacher approval checkbox before a version can be published. Media and embed URLs must use HTTPS and an allowlisted host.
- AI course generation and assessment submissions are rate-limited. Django CSRF middleware remains enabled for every browser POST form.
- Security actions are recorded in the immutable `analytics.AuditEvent` table with a keyed IP hash rather than the raw address.
- Python execution runs only in Docker with no network, a read-only filesystem, no added capabilities, a non-root UID, process/CPU/memory/file limits, and no package installation path.

## Production checklist

1. Generate and store a stable key outside the repository:

   ```bash
   uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Set the result as `AI_FIELD_ENCRYPTION_KEY`. Do not rotate it without a planned decrypt/re-encrypt migration.
2. Run `uv run python manage.py reencrypt_sensitive_answers` after upgrading an existing database.
3. Set `DJANGO_DEBUG=0`, `CELERY_TASK_ALWAYS_EAGER=0`, and use Redis for cache and Celery.
4. Review `AI_ALLOWED_EMBED_HOSTS` and keep only hosts approved by the organization.
5. Pin `SANDBOX_IMAGE` to an internally scanned image digest before production use.
6. Keep teacher approval required for every AI-generated media artifact; never bypass the publish validation.
