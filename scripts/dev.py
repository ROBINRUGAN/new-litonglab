# designed by mew
"""Run Vue and Django together locally, closing both when the command stops."""

import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
children = []


def stop(*_):
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    commands = [
        [
            str(ROOT / ".venv/bin/python"),
            "backend/manage.py",
            "runserver",
            "127.0.0.1:8000",
            "--noreload",
        ],
        ["npm", "--prefix", "frontend", "run", "dev"],
    ]
    for command in commands:
        children.append(subprocess.Popen(command, cwd=ROOT))
    try:
        while all(child.poll() is None for child in children):
            try:
                children[0].wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    finally:
        stop()


if __name__ == "__main__":
    main()
