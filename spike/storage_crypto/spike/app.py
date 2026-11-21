"""A throwaway FastAPI app that wires the pieces together.

Everything that differs between a laptop and production comes in through
`config` (in the product: environment variables). Records live in dicts here;
in the product they are database rows.
"""
import uuid
from typing import Mapping

from fastapi import FastAPI, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from .bank import (BankNumberEditRefused, BankNumberInvalid, BankNumbers,
                   NotAllowed, keyring_from_config)
from .clock import Clock
from .links import LINK_LIFETIME_SECONDS, LinkExpired, LinkInvalid, LinkSigner
from .receipts import (MAX_RECEIPT_BYTES, ReceiptTooLarge,
                       ReceiptTypeNotAllowed, check_receipt)
from .storage import FileNotStored, StorageUnavailable, storage_from_config

FILE_UNAVAILABLE_TEXT = "檔案儲存未設定，檔案目前無法使用"
LINK_EXPIRED_TEXT = "下載連結已過期，請重新開啟檔案"


def create_app(config: Mapping[str, str], clock: Clock) -> FastAPI:
    app = FastAPI()
    storage = storage_from_config(config)
    signer = LinkSigner(config["LINK_SIGNING_KEY"], clock)
    bank_rows: dict[str, str] = {}
    bank = BankNumbers(keyring_from_config(config), bank_rows)
    app.state.bank_rows = bank_rows

    # archive id -> its files, oldest first; the last one is the current file
    archives: dict[str, list[dict]] = {}
    content_types: dict[str, str] = {}  # storage key -> content type

    async def store_upload(archive_id: str, upload: UploadFile) -> str | None:
        """Store the file; return a warning instead when storage is off."""
        data = await upload.read(MAX_RECEIPT_BYTES + 1)
        try:
            content_type = check_receipt(data)
        except ReceiptTooLarge:
            raise HTTPException(413, "檔案超過 10 MB") from None
        except ReceiptTypeNotAllowed:
            raise HTTPException(415, "只接受 PDF、JPEG、PNG、WebP") from None
        key = f"archives/{archive_id}/{uuid.uuid4().hex}"
        try:
            storage.put(key, data)
        except StorageUnavailable:
            return FILE_UNAVAILABLE_TEXT
        archives[archive_id].append({"key": key, "name": upload.filename})
        content_types[key] = content_type
        return None

    def view(archive_id: str, warning: str | None = None) -> dict:
        files = [f["name"] for f in archives[archive_id]]
        return {"id": archive_id, "files": files, "warning": warning}

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/archives", status_code=201)
    async def create_archive(file: UploadFile | None = None):
        archive_id = uuid.uuid4().hex
        archives[archive_id] = []
        try:
            warning = await store_upload(archive_id, file) if file else None
        except HTTPException:
            del archives[archive_id]
            raise
        return view(archive_id, warning)

    @app.put("/archives/{archive_id}/file")
    async def replace_file(archive_id: str, file: UploadFile):
        """The new file becomes current; earlier ones stay openable."""
        if archive_id not in archives:
            raise HTTPException(404)
        return view(archive_id, await store_upload(archive_id, file))

    @app.get("/archives/{archive_id}")
    def show_archive(archive_id: str):
        if archive_id not in archives:
            raise HTTPException(404)
        return view(archive_id)

    @app.get("/archives/{archive_id}/files/{index}/link")
    def open_file(archive_id: str, index: int):
        """Every open issues a fresh link. Nothing about it is stored."""
        files = archives.get(archive_id)
        if files is None or not 0 <= index < len(files):
            raise HTTPException(404)
        if not storage.configured:
            return JSONResponse({"warning": FILE_UNAVAILABLE_TEXT}, 503)
        token = signer.issue(files[index]["key"])
        return {"url": f"/download/{token}", "expires_in": LINK_LIFETIME_SECONDS}

    @app.get("/download/{token}")
    def download(token: str):
        try:
            key = signer.resolve(token)
        except LinkInvalid:
            raise HTTPException(404) from None
        except LinkExpired:
            raise HTTPException(410, LINK_EXPIRED_TEXT) from None
        try:
            body = storage.open(key)
        except StorageUnavailable:
            return JSONResponse({"warning": FILE_UNAVAILABLE_TEXT}, 503)
        except FileNotStored:
            raise HTTPException(404) from None
        return StreamingResponse(
            body,
            media_type=content_types.get(key, "application/octet-stream"),
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @app.delete("/archives/{archive_id}", status_code=204)
    def delete_archive(archive_id: str):
        files = archives.get(archive_id)
        if files is None:
            raise HTTPException(404)
        for stored in files:
            storage.delete(stored["key"])
            del content_types[stored["key"]]
        del archives[archive_id]

    # --- bank number. X-User-Id / X-Admin stand in for the login session. ---

    @app.get("/accounts/{account_id}/bank-number")
    def bank_masked(account_id: str):
        return {"bank_number": bank.masked(account_id)}

    @app.get("/accounts/{account_id}/bank-number/full")
    def bank_full(account_id: str, x_user_id: str = Header(),
                  x_admin: str = Header("0")):
        try:
            number = bank.reveal(account_id, viewer_id=x_user_id,
                                 viewer_is_admin=x_admin == "1")
        except NotAllowed:
            raise HTTPException(403) from None
        return {"bank_number": number}

    @app.put("/accounts/{account_id}/bank-number")
    def bank_set(account_id: str, body: dict):
        try:
            bank.set(account_id, body["bank_number"])
        except BankNumberEditRefused as refused:
            raise HTTPException(409, str(refused)) from None
        except BankNumberInvalid:
            raise HTTPException(422, "銀行帳號必須是 14 位數字") from None
        return {"bank_number": bank.masked(account_id)}

    return app
