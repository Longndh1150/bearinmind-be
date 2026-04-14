from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> "SemVer":
        m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", s.strip())
        if not m:
            raise ValueError(f"Invalid semver: {s!r} (expected MAJOR.MINOR.PATCH)")
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def bump(self, part: str) -> "SemVer":
        if part == "major":
            return SemVer(self.major + 1, 0, 0)
        if part == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if part == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        raise ValueError(f"Unknown bump part: {part!r}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


RE_INIT_VERSION = re.compile(r'^(?P<prefix>\s*__version__\s*=\s*")(?P<ver>\d+\.\d+\.\d+)(?P<suffix>"\s*)$')
RE_PYPROJECT_VERSION = re.compile(r'^(?P<prefix>\s*version\s*=\s*")(?P<ver>\d+\.\d+\.\d+)(?P<suffix>"\s*)$')


def _replace_first_matching_line(path: Path, pattern: re.Pattern[str], new_version: str) -> tuple[str, str]:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)

    replaced = False
    old_version: str | None = None
    for i, line in enumerate(lines):
        m = pattern.match(line.rstrip("\n").rstrip("\r"))
        if not m:
            continue
        old_version = m.group("ver")
        lines[i] = f'{m.group("prefix")}{new_version}{m.group("suffix")}' + ("\n" if line.endswith("\n") else "")
        replaced = True
        break

    if not replaced or old_version is None:
        raise RuntimeError(f"Could not find version line to update in {path}")

    updated = "".join(lines)
    path.write_text(updated, encoding="utf-8")
    return old_version, new_version


def _repo_root_from_this_file() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump backend version (semver) and sync files.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--major", action="store_true", help="Bump MAJOR (x+1.0.0)")
    g.add_argument("--minor", action="store_true", help="Bump MINOR (x.y+1.0)")
    g.add_argument("--patch", action="store_true", help="Bump PATCH (x.y.z+1)")
    g.add_argument("--set", metavar="X.Y.Z", help="Set an explicit semver (MAJOR.MINOR.PATCH)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended changes but do not modify files.",
    )
    args = parser.parse_args(argv)

    root = _repo_root_from_this_file()
    init_py = root / "app" / "__init__.py"
    pyproject = root / "pyproject.toml"

    init_text = init_py.read_text(encoding="utf-8")
    m = None
    for line in init_text.splitlines():
        m = RE_INIT_VERSION.match(line)
        if m:
            break
    if not m:
        raise RuntimeError(f"Missing __version__ in {init_py}")

    current = SemVer.parse(m.group("ver"))
    if args.set:
        next_ver = SemVer.parse(args.set)
    else:
        part = "major" if args.major else "minor" if args.minor else "patch"
        next_ver = current.bump(part)

    if args.dry_run:
        print(f"{init_py}: {current} -> {next_ver}")
        print(f"{pyproject}: {current} -> {next_ver}")
        return 0

    _replace_first_matching_line(init_py, RE_INIT_VERSION, str(next_ver))
    _replace_first_matching_line(pyproject, RE_PYPROJECT_VERSION, str(next_ver))

    print(str(next_ver))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
