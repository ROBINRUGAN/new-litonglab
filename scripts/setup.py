# designed by mew
"""Install locked local dependencies and initialize only missing content/accounts."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    if sys.version_info < (3, 10):
        raise SystemExit("需要 Python 3.10 或更高版本。")
    if not (ROOT / ".venv").exists():
        run([sys.executable, "-m", "venv", ".venv"])
    python = str(ROOT / ".venv/bin/python")
    run([python, "-m", "pip", "install", "-r", "backend/requirements-dev.txt"])
    run(["npm", "--prefix", "frontend", "ci"])
    for command in ("migrate", "seed_site", "sync_public_media", "bootstrap_admin"):
        run([python, "backend/manage.py", command])
    run(["npm", "--prefix", "frontend", "run", "build"])
    print("准备完成。运行 npm run dev；账号见 var/initial-admin.txt。")


if __name__ == "__main__":
    main()
