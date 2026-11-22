"""The demo accounts: the shared background of docs/spec/background.md.

A test compares this list with that table, so the two cannot drift apart.
"""

from dataclasses import dataclass

# The same for all nine, and public: these accounts are for trying the system.
PASSWORD = "demo-password"


@dataclass(frozen=True)
class DemoAccount:
    name: str
    role: str
    zone: str
    big_meter: bool = False
    archived: bool = False


ACCOUNTS = (
    DemoAccount("Kuei", "OWNER", "WEST"),
    DemoAccount("Admin1", "ADMIN", "WEST"),
    DemoAccount("Admin2", "ADMIN", "WEST"),
    DemoAccount("Wen", "USER", "WEST"),
    DemoAccount("Wei", "USER", "WEST"),
    DemoAccount("Wan", "USER", "WEST"),
    DemoAccount("Nan", "USER", "SOUTH"),
    DemoAccount("Big", "USER", "WEST", big_meter=True),
    DemoAccount("Old", "USER", "WEST", archived=True),
)
