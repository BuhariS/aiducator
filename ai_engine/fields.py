import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _cipher() -> Fernet:
    configured_key = getattr(settings, "AI_FIELD_ENCRYPTION_KEY", "")
    if configured_key:
        key = configured_key.encode("ascii")
    else:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


class EncryptedTextField(models.TextField):
    prefix = "enc:v1:"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value.startswith(self.prefix):
            return value
        return self.prefix + _cipher().encrypt(value.encode("utf-8")).decode("ascii")

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        value = super().to_python(value)
        if value is None or not value.startswith(self.prefix):
            return value
        try:
            return _cipher().decrypt(value[len(self.prefix) :].encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise ValueError(
                "Encrypted answer data could not be decrypted with the configured key."
            ) from exc
