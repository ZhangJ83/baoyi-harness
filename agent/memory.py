from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RULES_FILE = BASE / "memory" / "RULES.md"
NOTES_FILE = BASE / "memory" / "NOTES.md"


def load_rules() -> str:
    if RULES_FILE.exists():
        return RULES_FILE.read_text(encoding="utf-8")
    return ""


def load_notes() -> str:
    if NOTES_FILE.exists():
        return NOTES_FILE.read_text(encoding="utf-8")
    return ""


def append_note(text: str) -> None:
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NOTES_FILE.open("a", encoding="utf-8") as f:
        f.write(text.rstrip("\n") + "\n")
