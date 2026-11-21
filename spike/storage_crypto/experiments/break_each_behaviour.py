"""Break one behaviour at a time and show which tests notice.

For each entry below: copy the spike to a temporary directory, replace one
piece of code with a broken version, run the tests, and print the tests that
failed. An entry that breaks nothing is reported as NOT CAUGHT and makes this
script exit 1. The checked-out files are never modified.

Run:  .venv/bin/python experiments/break_each_behaviour.py
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# (what is broken, file, code as written, broken code)
BREAKS = [
    ("link still works at 3,600 seconds", "spike/links.py",
     "if self._clock.now() >= expires_at:", "if self._clock.now() > expires_at:"),
    ("link lives 3,599 seconds instead of 3,600", "spike/links.py",
     "LINK_LIFETIME_SECONDS = 3600", "LINK_LIFETIME_SECONDS = 3599"),
    ("expiry is checked against the system time, not the clock", "spike/links.py",
     "if self._clock.now() >= expires_at:",
     "if datetime.now(timezone.utc) >= expires_at:"),
    ("expiry is stamped from the system time, not the clock", "spike/links.py",
     "int(self._clock.now().timestamp())",
     "int(datetime.now(timezone.utc).timestamp())"),
    ("link signature is not checked", "spike/links.py",
     "payload = self._serializer.loads(token)",
     "payload = self._serializer.load_payload(token.split('.')[0].encode())"),
    ("the link is remembered and reused instead of issued fresh", "spike/app.py",
     'token = signer.issue(files[index]["key"])',
     'token = files[index].setdefault("t", signer.issue(files[index]["key"]))'),
    ("10 MB + 1 byte is accepted", "spike/receipts.py",
     "if len(data) > MAX_RECEIPT_BYTES:", "if len(data) > MAX_RECEIPT_BYTES + 1:"),
    ("exactly 10 MB is refused", "spike/receipts.py",
     "if len(data) > MAX_RECEIPT_BYTES:", "if len(data) >= MAX_RECEIPT_BYTES:"),
    ("a GIF is accepted", "spike/receipts.py",
     "    return None\n\n\ndef check_receipt",
     '    if data.startswith(b"GIF8"):\n        return "image/gif"\n'
     "    return None\n\n\ndef check_receipt"),
    ("WebP is refused", "spike/receipts.py",
     'if data[:4] == b"RIFF" and data[8:12] == b"WEBP":', "if False:"),
    ("the type is taken from what the sender declared", "spike/receipts.py",
     "    content_type = sniff_content_type(data)\n    if content_type is None:",
     "    content_type = 'application/pdf'\n    if content_type is None:"),
    ("the served type is what the sender declared", "spike/app.py",
     "content_types[key] = content_type", "content_types[key] = upload.content_type"),
    ("a replacement overwrites the earlier file", "spike/app.py",
     'key = f"archives/{archive_id}/{uuid.uuid4().hex}"',
     'key = f"archives/{archive_id}/file"'),
    ("deleting an archive leaves its files in storage", "spike/app.py",
     '            storage.delete(stored["key"])\n', ""),
    ("local storage delete does nothing", "spike/storage.py",
     "self._path(key).unlink(missing_ok=True)", "pass"),
    ("S3 storage delete does nothing", "spike/storage.py",
     "self._client.delete_object(Bucket=self._bucket, Key=key)", "pass"),
    ("missing storage settings crash the application", "spike/storage.py",
     '    if backend == "":\n        return NotConfiguredStorage()\n', ""),
    ("upload fails when storage is not configured", "spike/app.py",
     "        except StorageUnavailable:\n            return FILE_UNAVAILABLE_TEXT",
     "        except StorageUnavailable:\n            raise HTTPException(500) from None"),
    ("download without storage gives no warning", "spike/app.py",
     "        except StorageUnavailable:\n"
     '            return JSONResponse({"warning": FILE_UNAVAILABLE_TEXT}, 503)',
     "        except StorageUnavailable:\n            raise HTTPException(404) from None"),
    ("the full bank number is shown by default", "spike/bank.py",
     'return "*" * (len(number) - 4) + number[-4:]', "return number"),
    ("anyone can reveal the full bank number", "spike/bank.py",
     "if not (viewer_is_admin or viewer_id == account_id):", "if False:"),
    ("administrators cannot reveal the full bank number", "spike/bank.py",
     "if not (viewer_is_admin or viewer_id == account_id):",
     "if viewer_id != account_id:"),
    ("the holder cannot reveal the full bank number", "spike/bank.py",
     "if not (viewer_is_admin or viewer_id == account_id):",
     "if not viewer_is_admin:"),
    ("the plain number is stored", "spike/bank.py",
     "blob = base64.urlsafe_b64encode(nonce + sealed).decode()",
     "blob = base64.urlsafe_b64encode(nonce + number.encode()).decode()"),
    ("the same nonce is used every time", "spike/bank.py",
     "nonce = os.urandom(_NONCE_BYTES)", "nonce = bytes(_NONCE_BYTES)"),
    ("an unreadable number is shown as blank", "spike/bank.py",
     "        except BankNumberUnreadable:\n            return UNREADABLE_TEXT\n"
     '        return "*"',
     '        except BankNumberUnreadable:\n            return ""\n        return "*"'),
    ("with no key, an edit erases the stored value", "spike/bank.py",
     "        if self._keyring.current is None:\n"
     "            raise BankNumberEditRefused()\n        stored",
     "        if self._keyring.current is None:\n"
     "            self._rows.pop(account_id, None)\n"
     "            raise BankNumberEditRefused()\n        stored"),
    ("with no key, an edit is refused with a different message", "spike/bank.py",
     'EDIT_REFUSED_TEXT = "銀行帳號目前無法讀取，無法修改"',
     'EDIT_REFUSED_TEXT = "無法修改"'),
    ("an unreadable stored value can be overwritten", "spike/bank.py",
     "            except BankNumberUnreadable:\n"
     "                raise BankNumberEditRefused() from None",
     "            except BankNumberUnreadable:\n                pass"),
    ("a wrong key or damaged value crashes instead of showing unreadable",
     "spike/bank.py",
     "    except InvalidTag:\n        raise BankNumberUnreadable() from None",
     "    except InvalidTag:\n        raise"),
    ("a value is not tied to its account", "spike/bank.py",
     'return f"bank-number:{account_id}".encode()', 'return b"bank-number"'),
    ("the key id stored with the value is ignored", "spike/bank.py",
     "key = keyring.get(key_id)", 'key = keyring.get(keyring.current or "")'),
    ("re-encryption does nothing", "spike/bank.py",
     "        moved = 0\n", "        return 0\n        moved = 0\n"),
    ("13 digits are accepted as a bank number", "spike/bank.py",
     '_BANK_NUMBER = re.compile(r"[0-9]{14}")',
     '_BANK_NUMBER = re.compile(r"[0-9]{13,14}")'),
]


def failing_tests(directory: Path) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
         "-o", "addopts=", "--tb=no", "-rfE"],
        cwd=directory, capture_output=True, text=True)
    return re.findall(r"^(?:FAILED|ERROR) (\S+)", result.stdout, re.MULTILINE)


def main() -> int:
    not_caught = 0
    for number, (what, file, good, broken) in enumerate(BREAKS, 1):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "spike"
            shutil.copytree(HERE, copy, ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", ".pytest_cache"))
            target = copy / file
            source = target.read_text()
            if source.count(good) != 1:
                print(f"{number:2}. {what}: code to break not found exactly once")
                return 2
            target.write_text(source.replace(good, broken))
            failed = failing_tests(copy)
        print(f"{number:2}. BROKEN: {what}")
        if not failed:
            not_caught += 1
            print("      NOT CAUGHT: every test still passed")
        for test in failed:
            print(f"      fails: {test}")
    print(f"\n{len(BREAKS) - not_caught} of {len(BREAKS)} breaks were caught by a test")
    return 1 if not_caught else 0


if __name__ == "__main__":
    sys.exit(main())
