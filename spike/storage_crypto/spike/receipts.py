"""What counts as an acceptable receipt file."""

MAX_RECEIPT_BYTES = 10 * 1024 * 1024


class ReceiptRefused(Exception):
    pass


class ReceiptTooLarge(ReceiptRefused):
    pass


class ReceiptTypeNotAllowed(ReceiptRefused):
    pass


def sniff_content_type(data: bytes) -> str | None:
    """The type the leading bytes say the file is; None when not allowed."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def check_receipt(data: bytes) -> str:
    """Return the content type to serve the file with, or raise."""
    if len(data) > MAX_RECEIPT_BYTES:
        raise ReceiptTooLarge()
    content_type = sniff_content_type(data)
    if content_type is None:
        raise ReceiptTypeNotAllowed()
    return content_type
