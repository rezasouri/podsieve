"""Validate local Markdown links without dependencies or network access."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "README.md", ROOT / "ui" / "README.md", ROOT / "CONTRIBUTING.md"]
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def main() -> int:
    failures = []
    for document in FILES:
        if not document.is_file():
            failures.append(f"Missing documentation: {document.relative_to(ROOT)}")
            continue
        content = document.read_text(encoding="utf-8")
        for target in LINK.findall(content):
            target = target.strip().split(" ", 1)[0].strip("<>")
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            path = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if path and not (document.parent / path).exists():
                failures.append(f"{document.relative_to(ROOT)}: broken link to {target}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Local Markdown links are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
