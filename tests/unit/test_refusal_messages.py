import shutil

import pytest

from tests.support.cli import REPO
from tests.support.refusal_messages import unlisted_refusal_messages

APP = REPO / "app"
APPENDIX_B = (REPO / "docs/spec/reference/appendix-b-fields.md").read_text(encoding="utf-8")


def test_every_refusal_message_of_the_application_is_in_appendix_b():
    assert unlisted_refusal_messages(APP, APPENDIX_B) == []


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        ('raise Refusal(Outcome.INVALID, "請選擇一個類型")', "system/sneaky.py:3: 「請選擇一個類型」 is not in appendix B"),
        (
            'raise outcomes.Refusal(outcomes.Outcome.INVALID, message="密碼錯誤")',
            "system/sneaky.py:3: 「密碼錯誤」 is not in appendix B",
        ),
        (
            'raise Refusal(Outcome.INVALID, f"請選擇{field}")',
            "system/sneaky.py:3: the message is not a plain string, so it cannot be checked",
        ),
        (
            "raise Refusal(Outcome.INVALID, MESSAGE)",
            "system/sneaky.py:3: the message is not a plain string, so it cannot be checked",
        ),
    ],
)
def test_a_refusal_whose_message_is_not_in_appendix_b_is_found(tmp_path, line, problem):
    copy = tmp_path / "app"
    shutil.copytree(APP, copy, ignore=shutil.ignore_patterns("__pycache__"))
    (copy / "system" / "sneaky.py").write_text(
        f"from app.core.outcomes import Outcome, Refusal\ndef refuse(field):\n    {line}\n", encoding="utf-8"
    )

    assert unlisted_refusal_messages(copy, APPENDIX_B) == [problem]


def test_a_message_that_is_in_appendix_b_is_not_reported(tmp_path):
    (tmp_path / "fine.py").write_text('raise Refusal(Outcome.RATE_LIMITED, "登入嘗試過於頻繁，請稍後再試")\n', encoding="utf-8")

    assert unlisted_refusal_messages(tmp_path, APPENDIX_B) == []
