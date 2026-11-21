import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import boto3
import pytest
from moto.server import ThreadedMotoServer

from spike.clock import FixedClock

# Far from the real date on purpose: code that reads the system time instead
# of the injected clock makes the expiry tests fail.
START = datetime(2030, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8 " + b"\x00" * 16
GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00" + b"\x00" * 16


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(START)


@pytest.fixture(scope="session")
def s3_endpoint():
    """A local stand-in for an S3-compatible store (moto), on a free port."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port, verbose=False)
    server.start()
    yield f"http://127.0.0.1:{port}"
    server.stop()


@dataclass
class Backend:
    name: str
    config: dict[str, str]
    stored_keys: Callable[[], list[str]]  # read straight from the backend


@pytest.fixture(params=["local", "s3"])
def backend(request, tmp_path) -> Backend:
    if request.param == "local":
        root = tmp_path / "files"
        return Backend(
            "local",
            {"STORAGE_BACKEND": "local", "STORAGE_LOCAL_DIR": str(root)},
            lambda: sorted(str(p.relative_to(root))
                           for p in root.rglob("*") if p.is_file()),
        )
    endpoint = request.getfixturevalue("s3_endpoint")
    bucket = f"spike-{uuid.uuid4().hex}"
    client = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1",
                          aws_access_key_id="test", aws_secret_access_key="test")
    client.create_bucket(Bucket=bucket)
    return Backend(
        "s3",
        {"STORAGE_BACKEND": "s3", "S3_BUCKET": bucket,
         "S3_ENDPOINT_URL": endpoint, "S3_REGION": "us-east-1",
         "S3_ACCESS_KEY_ID": "test", "S3_SECRET_ACCESS_KEY": "test"},
        lambda: sorted(o["Key"] for o in
                       client.list_objects_v2(Bucket=bucket).get("Contents", [])),
    )
