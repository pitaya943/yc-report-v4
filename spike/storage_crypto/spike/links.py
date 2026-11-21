"""Download links the application signs and expires itself.

A link is a signed token that carries the storage key and the second it stops
working. Nothing about a link is stored: checking one needs only the signing
key and the clock.
"""
from datetime import datetime, timezone

from itsdangerous import BadSignature, URLSafeSerializer

from .clock import Clock

LINK_LIFETIME_SECONDS = 3600


class LinkInvalid(Exception):
    """The token was not issued by this application."""


class LinkExpired(Exception):
    """The token is genuine but its lifetime is over."""


class LinkSigner:
    def __init__(self, signing_key: str, clock: Clock):
        self._serializer = URLSafeSerializer(signing_key, salt="file-link")
        self._clock = clock

    def issue(self, key: str) -> str:
        expires_at = int(self._clock.now().timestamp()) + LINK_LIFETIME_SECONDS
        return self._serializer.dumps({"k": key, "exp": expires_at})

    def resolve(self, token: str) -> str:
        """Return the storage key, or raise if the link is forged or expired."""
        try:
            payload = self._serializer.loads(token)
        except BadSignature:
            raise LinkInvalid() from None
        expires_at = datetime.fromtimestamp(payload["exp"], timezone.utc)
        if self._clock.now() >= expires_at:
            raise LinkExpired()
        return payload["k"]
