import pytest

from spike.links import LinkExpired, LinkInvalid, LinkSigner


def test_a_link_issued_3599_seconds_ago_still_resolves(clock):
    signer = LinkSigner("signing-key", clock)
    token = signer.issue("archives/1/receipt")
    clock.advance(3599)
    assert signer.resolve(token) == "archives/1/receipt"


def test_a_link_issued_3600_seconds_ago_no_longer_works(clock):
    signer = LinkSigner("signing-key", clock)
    token = signer.issue("archives/1/receipt")
    clock.advance(3600)
    with pytest.raises(LinkExpired):
        signer.resolve(token)


def test_a_link_altered_after_issue_is_rejected(clock):
    signer = LinkSigner("signing-key", clock)
    token = signer.issue("archives/1/receipt")
    payload, signature = token.rsplit(".", 1)
    clock.advance(10)  # a later link for another file has a different payload
    other_payload = signer.issue("archives/2/someone-else").rsplit(".", 1)[0]
    with pytest.raises(LinkInvalid):
        signer.resolve(f"{other_payload}.{signature}")
    with pytest.raises(LinkInvalid):
        signer.resolve(payload)


def test_a_link_signed_with_another_key_is_rejected(clock):
    token = LinkSigner("some-other-key", clock).issue("archives/1/receipt")
    with pytest.raises(LinkInvalid):
        LinkSigner("signing-key", clock).resolve(token)
