"""Bank-number encryption with AES-256-GCM from the `cryptography` library.

Stored value:  v1.<key id>.<base64url(nonce + ciphertext + tag)>
The key id says which key encrypted the value, so keys can be rotated one row
at a time. The account id is bound in as associated data, so a ciphertext
copied to another account's row does not decrypt.
"""
import base64
import os
import re
from typing import Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

UNREADABLE_TEXT = "無法讀取"
EDIT_REFUSED_TEXT = "銀行帳號目前無法讀取，無法修改"
_BANK_NUMBER = re.compile(r"[0-9]{14}")
_NONCE_BYTES = 12


class BankNumberUnreadable(Exception):
    """Missing key, unknown key id, wrong key or damaged ciphertext."""


class BankNumberEditRefused(Exception):
    def __init__(self) -> None:
        super().__init__(EDIT_REFUSED_TEXT)


class BankNumberInvalid(Exception):
    pass


class NotAllowed(Exception):
    pass


class Keyring:
    """Keys by id. `current` encrypts; every key in the ring can decrypt."""

    def __init__(self, keys: Mapping[str, bytes], current: str | None):
        if current is not None and current not in keys:
            raise ValueError(f"current key id {current!r} is not in the keyring")
        for key_id, key in keys.items():
            if "." in key_id or not key_id:
                raise ValueError(f"bad key id: {key_id!r}")
            if len(key) != 32:
                raise ValueError(f"key {key_id!r} must be 32 bytes")
        self._keys = dict(keys)
        self.current = current

    def get(self, key_id: str) -> bytes | None:
        return self._keys.get(key_id)


def keyring_from_config(config: Mapping[str, str]) -> Keyring:
    """BANK_KEYS="id:base64key,id:base64key"; BANK_KEY_CURRENT names the one
    that encrypts. Both unset means "no key": a supported mode, not an error."""
    keys: dict[str, bytes] = {}
    for item in filter(None, config.get("BANK_KEYS", "").split(",")):
        key_id, _, encoded = item.partition(":")
        keys[key_id.strip()] = base64.urlsafe_b64decode(encoded.strip())
    return Keyring(keys, config.get("BANK_KEY_CURRENT") or None)


def generate_key() -> str:
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()


def _aad(account_id: str) -> bytes:
    return f"bank-number:{account_id}".encode()


def encrypt(keyring: Keyring, account_id: str, number: str) -> str:
    if keyring.current is None:
        raise BankNumberUnreadable()
    nonce = os.urandom(_NONCE_BYTES)
    sealed = AESGCM(keyring.get(keyring.current)).encrypt(
        nonce, number.encode(), _aad(account_id))
    blob = base64.urlsafe_b64encode(nonce + sealed).decode()
    return f"v1.{keyring.current}.{blob}"


def decrypt(keyring: Keyring, account_id: str, stored: str) -> str:
    try:
        version, key_id, blob = stored.split(".")
        raw = base64.urlsafe_b64decode(blob)
    except ValueError:
        raise BankNumberUnreadable() from None
    key = keyring.get(key_id)
    if version != "v1" or key is None or len(raw) <= _NONCE_BYTES:
        raise BankNumberUnreadable()
    try:
        plain = AESGCM(key).decrypt(raw[:_NONCE_BYTES], raw[_NONCE_BYTES:],
                                    _aad(account_id))
    except InvalidTag:
        raise BankNumberUnreadable() from None
    return plain.decode()


def key_id_of(stored: str) -> str:
    return stored.split(".")[1]


class BankNumbers:
    """The bank-number feature over a row store (a dict standing in for the
    `bank_number_encrypted` column of the accounts table)."""

    def __init__(self, keyring: Keyring, rows: dict[str, str]):
        self._keyring = keyring
        self._rows = rows

    def masked(self, account_id: str) -> str:
        """What everyone allowed to see the account sees by default."""
        stored = self._rows.get(account_id)
        if stored is None:
            return ""
        try:
            number = decrypt(self._keyring, account_id, stored)
        except BankNumberUnreadable:
            return UNREADABLE_TEXT
        return "*" * (len(number) - 4) + number[-4:]

    def reveal(self, account_id: str, *, viewer_id: str, viewer_is_admin: bool) -> str:
        if not (viewer_is_admin or viewer_id == account_id):
            raise NotAllowed()
        stored = self._rows.get(account_id)
        if stored is None:
            return ""
        try:
            return decrypt(self._keyring, account_id, stored)
        except BankNumberUnreadable:
            return UNREADABLE_TEXT

    def set(self, account_id: str, number: str) -> None:
        """Refuses, writing nothing, unless a key to encrypt with is
        configured and the value now stored (if any) can be read."""
        if self._keyring.current is None:
            raise BankNumberEditRefused()
        stored = self._rows.get(account_id)
        if stored is not None:
            try:
                decrypt(self._keyring, account_id, stored)
            except BankNumberUnreadable:
                raise BankNumberEditRefused() from None
        if not _BANK_NUMBER.fullmatch(number):
            raise BankNumberInvalid()
        self._rows[account_id] = encrypt(self._keyring, account_id, number)

    def reencrypt_all(self) -> int:
        """Move every row to the current key. Returns how many rows moved."""
        moved = 0
        for account_id, stored in list(self._rows.items()):
            if key_id_of(stored) == self._keyring.current:
                continue
            number = decrypt(self._keyring, account_id, stored)
            self._rows[account_id] = encrypt(self._keyring, account_id, number)
            moved += 1
        return moved
