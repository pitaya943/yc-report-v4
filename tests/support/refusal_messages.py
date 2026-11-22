"""Finds refusal messages in the application that the spec's field table does not hold."""

import ast
from pathlib import Path


def _is_refusal(call: ast.Call) -> bool:
    func = call.func
    return (func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)) == "Refusal"


def _message(call: ast.Call) -> ast.expr | None:
    if len(call.args) >= 2:
        return call.args[1]
    return next((keyword.value for keyword in call.keywords if keyword.arg == "message"), None)


def unlisted_refusal_messages(app: Path, appendix_b: str) -> list[str]:
    """``path:line: why`` for every ``Refusal(...)`` under ``app`` whose message is not in appendix B.

    The message has to be written as a string where the refusal is raised:
    anything else cannot be checked, and is reported too.
    """
    problems: list[str] = []
    for path in sorted(app.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _is_refusal(node)):
                continue
            where = f"{path.relative_to(app)}:{node.lineno}"
            message = _message(node)
            if not (isinstance(message, ast.Constant) and isinstance(message.value, str)):
                problems.append(f"{where}: the message is not a plain string, so it cannot be checked")
            elif f"「{message.value}」" not in appendix_b:
                problems.append(f"{where}: 「{message.value}」 is not in appendix B")
    return problems
