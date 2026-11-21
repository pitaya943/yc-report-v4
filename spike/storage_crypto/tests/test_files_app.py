"""File behaviour seen through HTTP, run against both storage backends."""
import pytest
from fastapi.testclient import TestClient

from conftest import GIF, JPEG, PDF, PNG, WEBP
from spike.app import FILE_UNAVAILABLE_TEXT, create_app

TEN_MB = 10 * 1024 * 1024
SIGNING = {"LINK_SIGNING_KEY": "not-a-real-key"}


@pytest.fixture
def client(backend, clock) -> TestClient:
    return TestClient(create_app({**backend.config, **SIGNING}, clock))


def upload(client, data, name="receipt.pdf", declared="application/pdf"):
    return client.post("/archives", files={"file": (name, data, declared)})


def link(client, archive_id, index=0) -> str:
    response = client.get(f"/archives/{archive_id}/files/{index}/link")
    assert response.status_code == 200
    assert response.json()["expires_in"] == 3600
    return response.json()["url"]


def test_an_uploaded_file_downloads_through_its_link(client):
    archive_id = upload(client, PDF).json()["id"]
    response = client.get(link(client, archive_id))
    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"


def test_link_works_at_3599_seconds_and_stops_at_3600(client, clock):
    archive_id = upload(client, PDF).json()["id"]
    url = link(client, archive_id)
    clock.advance(3599)
    assert client.get(url).status_code == 200
    clock.advance(1)
    expired = client.get(url)
    assert expired.status_code == 410
    assert expired.content != PDF


def test_every_open_issues_a_fresh_link_with_its_own_hour(client, clock):
    archive_id = upload(client, PDF).json()["id"]
    first = link(client, archive_id)
    clock.advance(1800)
    second = link(client, archive_id)
    assert second != first
    clock.advance(1800)  # the first link is now 3,600 seconds old
    assert client.get(first).status_code == 410
    assert client.get(second).status_code == 200


def test_exactly_10_mb_is_accepted(client, backend):
    data = PDF + b"\x00" * (TEN_MB - len(PDF))
    response = upload(client, data)
    assert response.status_code == 201
    assert len(client.get(link(client, response.json()["id"])).content) == TEN_MB


def test_10_mb_plus_one_byte_is_refused_and_nothing_is_stored(client, backend):
    data = PDF + b"\x00" * (TEN_MB + 1 - len(PDF))
    assert upload(client, data).status_code == 413
    assert backend.stored_keys() == []


@pytest.mark.parametrize("data, name, declared, served_as", [
    (PDF, "r.pdf", "application/pdf", "application/pdf"),
    (JPEG, "r.jpg", "image/jpeg", "image/jpeg"),
    (PNG, "r.png", "image/png", "image/png"),
    (WEBP, "r.webp", "image/webp", "image/webp"),
], ids=["pdf", "jpeg", "png", "webp"])
def test_pdf_jpeg_png_and_webp_are_accepted(client, data, name, declared, served_as):
    response = upload(client, data, name, declared)
    assert response.status_code == 201
    served = client.get(link(client, response.json()["id"]))
    assert served.headers["content-type"] == served_as


def test_a_gif_is_refused(client, backend):
    assert upload(client, GIF, "anim.gif", "image/gif").status_code == 415
    assert backend.stored_keys() == []


def test_a_gif_is_refused_even_when_named_and_declared_as_a_pdf(client, backend):
    assert upload(client, GIF, "receipt.pdf", "application/pdf").status_code == 415
    assert backend.stored_keys() == []


def test_the_served_type_comes_from_the_file_not_from_what_the_sender_said(client):
    response = upload(client, PNG, "page.html", "text/html")
    assert response.status_code == 201
    served = client.get(link(client, response.json()["id"]))
    assert served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"


def test_a_replaced_file_stays_openable_beside_the_current_one(client, backend):
    archive_id = upload(client, PDF, "old.pdf").json()["id"]
    replaced = client.put(f"/archives/{archive_id}/file",
                          files={"file": ("new.png", PNG, "image/png")})
    assert replaced.json()["files"] == ["old.pdf", "new.png"]
    assert client.get(link(client, archive_id, 0)).content == PDF
    assert client.get(link(client, archive_id, 1)).content == PNG
    assert len(backend.stored_keys()) == 2


def test_deleting_an_archive_removes_its_stored_files(client, backend):
    kept = upload(client, JPEG, "kept.jpg").json()["id"]
    doomed = upload(client, PDF, "old.pdf").json()["id"]
    client.put(f"/archives/{doomed}/file",
               files={"file": ("new.png", PNG, "image/png")})
    old_url = link(client, doomed, 0)
    assert len(backend.stored_keys()) == 3

    assert client.delete(f"/archives/{doomed}").status_code == 204

    assert len(backend.stored_keys()) == 1
    assert client.get(old_url).status_code == 404
    assert client.get(link(client, kept)).content == JPEG


# --- file storage not configured ---

def test_without_storage_the_record_is_created_without_a_file(clock):
    client = TestClient(create_app(SIGNING, clock))
    response = upload(client, PDF)
    assert response.status_code == 201
    assert response.json()["files"] == []
    assert response.json()["warning"] == FILE_UNAVAILABLE_TEXT
    shown = client.get(f"/archives/{response.json()['id']}")
    assert shown.status_code == 200 and shown.json()["files"] == []


def test_without_storage_the_rest_of_the_system_keeps_working(clock):
    client = TestClient(create_app(SIGNING, clock))
    assert client.get("/health").json() == {"ok": True}
    assert client.post("/archives").status_code == 201


def test_without_storage_a_download_attempt_warns_the_file_is_unavailable(
        backend, clock):
    # The file was stored while storage was configured...
    configured = TestClient(create_app({**backend.config, **SIGNING}, clock))
    url = link(configured, upload(configured, PDF).json()["id"])
    # ...then the same application starts without its storage settings.
    unconfigured = TestClient(create_app(SIGNING, clock))
    response = unconfigured.get(url)
    assert response.status_code == 503
    assert response.json() == {"warning": FILE_UNAVAILABLE_TEXT}
