"""Password hashing: argon2id, with the parameters carried inside each hash."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# "fast" is the cheapest argon2 allows. It exists for tests; production refuses it.
_PROFILES: dict[str, dict[str, int]] = {
    "standard": {},
    "fast": {"time_cost": 1, "memory_cost": 8, "parallelism": 1},
}


class Passwords:
    def __init__(self, profile: str):
        self._hasher = PasswordHasher(**_PROFILES[profile])
        # Nobody knows what this is the hash of. Verifying against it costs
        # what verifying a real account's password costs.
        self._nobody = self._hasher.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def verify_for_nobody(self, password: str) -> None:
        """Spend the time of a verification when there is no account to verify against."""
        self.verify(self._nobody, password)
