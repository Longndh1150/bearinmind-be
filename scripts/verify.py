from __future__ import annotations

import os
import subprocess
import sys


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    # Run from repo root even if called elsewhere
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)

    run([sys.executable, "-m", "ruff", "format", "."])
    run([sys.executable, "-m", "ruff", "check", ".", "--fix"])
    run([sys.executable, "-m", "pytest", "--cov=app", "--cov-report=term-missing"])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
