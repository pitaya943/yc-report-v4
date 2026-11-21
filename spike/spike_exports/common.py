from dataclasses import dataclass
from pathlib import Path

FONT_NAME = "NotoSansTC"
FONT_PATH = Path(__file__).parent.parent / "fonts" / "NotoSansTC-Regular.ttf"


def format_amount(amount: int) -> str:
    """New Taiwan dollars: thousands separators, a leading minus when negative."""
    return f"{amount:,}"


@dataclass(frozen=True)
class PayrollRow:
    employee_no: str
    name: str
    base_pay: int
    allowance: int
    deduction: int
    adjustment: int

    @property
    def net_pay(self) -> int:
        return self.base_pay + self.allowance - self.deduction + self.adjustment


@dataclass(frozen=True)
class TransferRow:
    account_no: str  # 14 digits
    name: str
    amount: int
