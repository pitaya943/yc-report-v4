import base64

import pytest
from fastapi.testclient import TestClient

from conftest import PDF
from spike.app import create_app
from spike.bank import (EDIT_REFUSED_TEXT, BankNumberEditRefused,
                        BankNumberInvalid, BankNumbers, Keyring, NotAllowed,
                        generate_key, key_id_of, keyring_from_config)

NUMBER = "12345678905678"
OTHER_NUMBER = "98765432101111"
KEY_1 = bytes(range(32))
KEY_2 = bytes(range(100, 132))
NO_KEY = Keyring({}, None)


def ring(**keys: bytes) -> Keyring:
    """A keyring whose last named key is the current one."""
    return Keyring(keys, list(keys)[-1])


def rows_with(account_id: str, number: str, keyring: Keyring) -> dict[str, str]:
    rows: dict[str, str] = {}
    BankNumbers(keyring, rows).set(account_id, number)
    return rows


# --- normal operation ---

def test_by_default_only_the_last_four_digits_are_shown():
    bank = BankNumbers(ring(k1=KEY_1), {})
    bank.set("amy", NUMBER)
    assert bank.masked("amy") == "**********5678"


def test_the_holder_can_reveal_the_full_number():
    bank = BankNumbers(ring(k1=KEY_1), {})
    bank.set("amy", NUMBER)
    assert bank.reveal("amy", viewer_id="amy", viewer_is_admin=False) == NUMBER


def test_an_administrator_can_reveal_the_full_number():
    bank = BankNumbers(ring(k1=KEY_1), {})
    bank.set("amy", NUMBER)
    assert bank.reveal("amy", viewer_id="boss", viewer_is_admin=True) == NUMBER


def test_another_employee_cannot_reveal_the_full_number():
    bank = BankNumbers(ring(k1=KEY_1), {})
    bank.set("amy", NUMBER)
    with pytest.raises(NotAllowed):
        bank.reveal("amy", viewer_id="bob", viewer_is_admin=False)


def test_the_stored_value_never_contains_the_plain_number():
    rows = rows_with("amy", NUMBER, ring(k1=KEY_1))
    stored = rows["amy"]
    assert NUMBER not in stored
    assert NUMBER.encode() not in base64.urlsafe_b64decode(stored.split(".")[2])
    assert stored.startswith("v1.k1.")


def test_the_same_number_stored_twice_gives_two_different_values():
    keyring = ring(k1=KEY_1)
    assert rows_with("amy", NUMBER, keyring) != rows_with("amy", NUMBER, keyring)


def test_a_number_that_is_not_14_digits_is_refused():
    rows: dict[str, str] = {}
    with pytest.raises(BankNumberInvalid):
        BankNumbers(ring(k1=KEY_1), rows).set("amy", "1234567890123")
    assert rows == {}


# --- missing key ---

def test_missing_key_viewing_shows_unreadable():
    rows = rows_with("amy", NUMBER, ring(k1=KEY_1))
    bank = BankNumbers(NO_KEY, rows)
    assert bank.masked("amy") == "無法讀取"
    assert bank.reveal("amy", viewer_id="amy", viewer_is_admin=False) == "無法讀取"


def test_missing_key_editing_is_refused_and_nothing_is_written():
    rows = rows_with("amy", NUMBER, ring(k1=KEY_1))
    before = dict(rows)
    bank = BankNumbers(NO_KEY, rows)
    with pytest.raises(BankNumberEditRefused) as refused:
        bank.set("amy", OTHER_NUMBER)
    assert str(refused.value) == "銀行帳號目前無法讀取，無法修改"
    with pytest.raises(BankNumberEditRefused):
        bank.set("new-hire", OTHER_NUMBER)  # no value yet: still nothing to encrypt with
    assert rows == before


def test_missing_key_every_other_feature_keeps_working(clock, tmp_path):
    config = {"LINK_SIGNING_KEY": "not-a-real-key", "STORAGE_BACKEND": "local",
              "STORAGE_LOCAL_DIR": str(tmp_path / "files")}  # no BANK_KEYS
    app = create_app(config, clock)
    app.state.bank_rows.update(rows_with("amy", NUMBER, ring(k1=KEY_1)))
    before = dict(app.state.bank_rows)
    client = TestClient(app)

    assert client.get("/accounts/amy/bank-number").json() == {"bank_number": "無法讀取"}
    full = client.get("/accounts/amy/bank-number/full", headers={"X-User-Id": "amy"})
    assert full.json() == {"bank_number": "無法讀取"}
    edit = client.put("/accounts/amy/bank-number", json={"bank_number": OTHER_NUMBER})
    assert edit.status_code == 409
    assert edit.json()["detail"] == EDIT_REFUSED_TEXT
    assert app.state.bank_rows == before

    assert client.get("/health").json() == {"ok": True}
    created = client.post("/archives", files={"file": ("r.pdf", PDF, "application/pdf")})
    assert created.status_code == 201
    url = client.get(f"/archives/{created.json()['id']}/files/0/link").json()["url"]
    assert client.get(url).content == PDF


# --- wrong key, damaged value ---

def test_wrong_key_shows_unreadable_and_refuses_editing():
    rows = rows_with("amy", NUMBER, ring(k1=KEY_1))
    before = dict(rows)
    bank = BankNumbers(ring(k1=KEY_2), rows)  # same id, different key
    assert bank.masked("amy") == "無法讀取"
    assert bank.reveal("amy", viewer_id="amy", viewer_is_admin=False) == "無法讀取"
    with pytest.raises(BankNumberEditRefused):
        bank.set("amy", OTHER_NUMBER)
    assert rows == before


def test_a_value_whose_key_id_is_not_configured_shows_unreadable():
    rows = rows_with("amy", NUMBER, ring(k1=KEY_1))
    assert BankNumbers(ring(k2=KEY_2), rows).masked("amy") == "無法讀取"


@pytest.mark.parametrize("damage", [
    lambda s: s[:-6] + ("AAAAAA" if not s.endswith("AAAAAA") else "BBBBBB"),
    lambda s: s[:20] + ("A" if s[20] != "A" else "B") + s[21:],
    lambda s: s[:-10],
    lambda s: "v1.k1.",
    lambda s: "not a stored value at all",
    lambda s: NUMBER,
], ids=["tag-changed", "ciphertext-changed", "truncated", "empty-payload",
        "not-a-stored-value", "plain-number-in-the-column"])
def test_corrupted_ciphertext_shows_unreadable_and_refuses_editing(damage):
    keyring = ring(k1=KEY_1)
    rows = rows_with("amy", NUMBER, keyring)
    rows["amy"] = damage(rows["amy"])
    before = dict(rows)
    bank = BankNumbers(keyring, rows)
    assert bank.masked("amy") == "無法讀取"
    assert bank.reveal("amy", viewer_id="amy", viewer_is_admin=False) == "無法讀取"
    with pytest.raises(BankNumberEditRefused):
        bank.set("amy", OTHER_NUMBER)
    assert rows == before


def test_a_value_copied_onto_another_account_does_not_decrypt():
    keyring = ring(k1=KEY_1)
    rows = rows_with("amy", NUMBER, keyring)
    rows["bob"] = rows["amy"]
    assert BankNumbers(keyring, rows).masked("bob") == "無法讀取"


# --- key rotation ---

def test_rotating_the_key_loses_no_data():
    rows = rows_with("amy", NUMBER, ring(k1=KEY_1))

    # Step 1: add k2 and make it current. Old rows still read; new writes use k2.
    both = BankNumbers(ring(k1=KEY_1, k2=KEY_2), rows)
    assert both.reveal("amy", viewer_id="amy", viewer_is_admin=False) == NUMBER
    both.set("bob", OTHER_NUMBER)
    assert key_id_of(rows["amy"]) == "k1" and key_id_of(rows["bob"]) == "k2"

    # Step 2: re-encrypt the old rows.
    assert both.reencrypt_all() == 1
    assert key_id_of(rows["amy"]) == "k2"

    # Step 3: k1 can now be removed from the configuration.
    only_new = BankNumbers(ring(k2=KEY_2), rows)
    assert only_new.reveal("amy", viewer_id="amy", viewer_is_admin=False) == NUMBER
    assert only_new.reveal("bob", viewer_id="bob", viewer_is_admin=False) == OTHER_NUMBER


# --- the key comes from configuration ---

def test_keys_are_read_from_configuration():
    old, new = generate_key(), generate_key()
    keyring = keyring_from_config(
        {"BANK_KEYS": f"2026a:{old},2027a:{new}", "BANK_KEY_CURRENT": "2027a"})
    rows = rows_with("amy", NUMBER, keyring)
    assert key_id_of(rows["amy"]) == "2027a"
    assert BankNumbers(keyring, rows).masked("amy") == "**********5678"


def test_no_key_settings_means_no_key_rather_than_a_crash():
    assert keyring_from_config({}).current is None
