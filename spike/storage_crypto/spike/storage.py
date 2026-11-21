"""One storage interface, three modes chosen by configuration only."""
from pathlib import Path
from typing import Iterator, Mapping, Protocol

CHUNK = 64 * 1024


class StorageUnavailable(Exception):
    """File storage is not configured."""


class FileNotStored(Exception):
    """No object is stored under that key."""


class Storage(Protocol):
    configured: bool

    def put(self, key: str, data: bytes) -> None: ...
    def open(self, key: str) -> Iterator[bytes]: ...
    def delete(self, key: str) -> None: ...


class NotConfiguredStorage:
    configured = False

    def put(self, key: str, data: bytes) -> None:
        raise StorageUnavailable()

    def open(self, key: str) -> Iterator[bytes]:
        raise StorageUnavailable()

    def delete(self, key: str) -> None:
        raise StorageUnavailable()


class LocalDirStorage:
    configured = True

    def __init__(self, root: str | Path):
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"key escapes the storage root: {key!r}")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def open(self, key: str) -> Iterator[bytes]:
        path = self._path(key)
        if not path.is_file():
            raise FileNotStored(key)

        def chunks() -> Iterator[bytes]:
            with path.open("rb") as handle:
                while block := handle.read(CHUNK):
                    yield block

        return chunks()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    """Any S3-compatible store: Supabase Storage, Cloudflare R2, MinIO, moto."""

    configured = True

    def __init__(self, *, bucket: str, endpoint_url: str, access_key_id: str,
                 secret_access_key: str, region: str):
        import boto3
        from botocore.config import Config

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(s3={"addressing_style": "path"}),
        )

    def put(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def open(self, key: str) -> Iterator[bytes]:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey:
            raise FileNotStored(key) from None
        return response["Body"].iter_chunks(CHUNK)

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


def storage_from_config(config: Mapping[str, str]) -> Storage:
    """STORAGE_BACKEND unset means "not configured"; it is not an error."""
    backend = config.get("STORAGE_BACKEND", "")
    if backend == "":
        return NotConfiguredStorage()
    if backend == "local":
        return LocalDirStorage(config["STORAGE_LOCAL_DIR"])
    if backend == "s3":
        return S3Storage(
            bucket=config["S3_BUCKET"],
            endpoint_url=config["S3_ENDPOINT_URL"],
            access_key_id=config["S3_ACCESS_KEY_ID"],
            secret_access_key=config["S3_SECRET_ACCESS_KEY"],
            region=config.get("S3_REGION", "auto"),
        )
    raise ValueError(f"unknown STORAGE_BACKEND: {backend!r}")
