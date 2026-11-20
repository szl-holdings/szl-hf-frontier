"""Self-lint: plain ASCII and lines <= 80 columns for this package."""

import pathlib
import sys

MAX_COLS = 80


def lint_tree(root):
    """Return a list of violation strings for the package at root."""
    root = pathlib.Path(root)
    violations = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="ascii", errors="strict")
        for num, line in enumerate(text.splitlines(), 1):
            if len(line) > MAX_COLS:
                violations.append("%s:%d exceeds %d cols" %
                                  (path.name, num, MAX_COLS))
    return violations


def main(argv):
    if len(argv) != 2:
        print("usage: selflint <dir>")
        return 2
    violations = lint_tree(argv[1])
    if violations:
        for item in violations:
            print(item)
        return 1
    print("SELF_LINT_OK ascii+cols")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
