import hashlib
import hmac

from django.conf import settings

from .models import AuditEvent


def record_audit_event(*, action, actor=None, obj=None, request=None, metadata=None):
    entity_type = obj.__class__.__name__ if obj is not None else ""
    entity_id = getattr(obj, "pk", None) if obj is not None else None
    ip_hash = ""
    if request is not None:
        remote_ip = request.META.get("REMOTE_ADDR", "")
        if remote_ip:
            ip_hash = hmac.new(
                settings.SECRET_KEY.encode(), remote_ip.encode(), hashlib.sha256
            ).hexdigest()
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_hash=ip_hash,
        metadata=metadata or {},
    )
