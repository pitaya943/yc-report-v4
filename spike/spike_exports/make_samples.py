"""`python -m spike_exports.make_samples <dir>`: write the two sample files.

Every name, account number and amount is made up.
"""
import sys
from datetime import date
from pathlib import Path

from spike_jobs.clock import FixedClock

from .bank_docx import render_bank_transfer_docx
from .common import PayrollRow, TransferRow
from .payroll_pdf import render_payroll_pdf

PAYROLL = [
    PayrollRow("E001", "王小明", 45000, 3000, 2180, 0),
    PayrollRow("E002", "陳美玲", 52000, 0, 2560, -1200),
    PayrollRow("E003", "林志豪", 38500, 1500, 1890, 0),
    PayrollRow("E004", "張堃喆", 0, 0, 1200, 0),
]
TRANSFERS = [
    TransferRow("00412345678901", "王小明", 45820),
    TransferRow("00498765432109", "陳美玲", 48240),
    TransferRow("01200011122233", "林志豪", 38110),
    TransferRow("01255566677788", "張堃喆", -1200),
]


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    clock = FixedClock("2026-11-30T23:59:00")
    (out / "payroll.pdf").write_bytes(render_payroll_pdf("2026 年 11 月", PAYROLL, clock.now()))
    (out / "bank-transfer.docx").write_bytes(
        render_bank_transfer_docx("範例工程行", "00400000000001", date(2026, 12, 5), TRANSFERS)
    )
    print(f"wrote {out / 'payroll.pdf'} and {out / 'bank-transfer.docx'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
