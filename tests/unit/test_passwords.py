import pytest

from app.accounts.passwords import Passwords


@pytest.mark.parametrize(
    ("profile", "parameters"),
    [
        ("standard", "$argon2id$v=19$m=65536,t=3,p=4$"),  # the library's defaults
        ("fast", "$argon2id$v=19$m=8,t=1,p=1$"),  # the least argon2 accepts
    ],
)
def test_a_hash_is_argon2id_with_the_parameters_of_its_profile(profile, parameters):
    assert Passwords(profile).hash("秘密").startswith(parameters)


def test_only_the_password_that_was_hashed_verifies():
    passwords = Passwords("fast")
    hashed = passwords.hash("秘密")

    assert passwords.verify(hashed, "秘密") is True
    assert passwords.verify(hashed, "秘密 ") is False
    assert passwords.verify(hashed, "") is False
    assert passwords.hash("秘密") != hashed  # salted


def test_a_hash_made_with_other_parameters_still_verifies():
    hashed = Passwords("standard").hash("秘密")

    assert Passwords("fast").verify(hashed, "秘密") is True


def test_something_that_is_not_a_hash_verifies_nothing():
    assert Passwords("fast").verify("not-a-hash", "秘密") is False
    assert Passwords("fast").verify("", "") is False
