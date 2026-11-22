"""What can be said about the Dockerfile without building it. The image itself is proven by the workflow's image job."""

import json
import re

from tests.support.cli import REPO

INSTRUCTION = re.compile(r"^([A-Z]+)\s+(.*)$")


def instructions() -> list[tuple[str, str]]:
    text = (REPO / "Dockerfile").read_text(encoding="utf-8").replace("\\\n", " ")
    lines = (line.strip() for line in text.splitlines())
    found = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        match = INSTRUCTION.match(line)
        assert match, f"not an instruction: {line}"
        found.append((match.group(1), match.group(2)))
    return found


def arguments(name: str) -> list[str]:
    return [argument for instruction, argument in instructions() if instruction == name]


def test_every_instruction_is_one_docker_knows_and_the_first_is_from():
    names = [name for name, _ in instructions()]

    assert names[0] == "FROM"
    assert set(names) <= {"FROM", "ENV", "WORKDIR", "COPY", "RUN", "USER", "EXPOSE", "CMD"}


def test_every_copied_source_exists_and_is_sent_to_the_build():
    sent = {
        line[1:] for line in (REPO / ".dockerignore").read_text(encoding="utf-8").splitlines() if line.startswith("!")
    }
    sources = [source for argument in arguments("COPY") for source in argument.split()[:-1]]

    assert {"app", "migrations", "pyproject.toml"} <= set(sources)
    for source in sources:
        assert (REPO / source).exists(), source
        assert source in sent, f"{source} is left out by .dockerignore"


def test_the_image_runs_serve_as_a_user_that_is_not_root():
    assert arguments("USER")[-1] not in ("root", "0")
    assert [name for name, _ in instructions()][-1] == "CMD"
    command = " ".join(json.loads(arguments("CMD")[-1]))
    assert "python -m app serve" in command
    assert "--host 0.0.0.0" in command
    assert "${PORT" in command


def test_no_setting_is_baked_into_the_image():
    baked = " ".join(arguments("ENV"))

    for setting in ("DATABASE_URL", "APP_ENV", "BANK_KEY", "STORAGE_BACKEND", "PASSWORD", "SECRET", "TOKEN"):
        assert setting not in baked
