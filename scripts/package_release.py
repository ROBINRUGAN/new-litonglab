# designed by mew
"""Build one portable release archive; reuse it while its inputs are unchanged."""

import hashlib
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "backend",
    "frontend/dist",
    "content/seed",
    "deploy",
    "scripts/restore_backup.py",
    "docs",
)
FRONTEND_INPUTS = (
    "frontend/src",
    "frontend/public",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/tsconfig.json",
    "frontend/vite.config.ts",
    "package.json",
    "scripts/package_release.py",
)


def files_in(names):
    for name in names:
        base = ROOT / name
        for file in sorted(base.rglob("*")) if base.is_dir() else [base]:
            relative = file.relative_to(ROOT)
            if (
                file.is_file()
                and not file.is_symlink()
                and file.name != ".DS_Store"
                and "__pycache__" not in file.parts
                and file.suffix not in (".pyc", ".pyo")
                and not relative.is_relative_to("backend/cms/tests")
                and relative != Path("backend/requirements-dev.txt")
            ):
                yield file


def file_hash(file):
    digest = hashlib.sha256()
    with file.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    inputs = tuple(name for name in SOURCES if name != "frontend/dist") + FRONTEND_INPUTS
    digest = hashlib.sha256()
    for file in files_in(inputs):
        digest.update(str(file.relative_to(ROOT)).encode() + b"\0")
        digest.update(file_hash(file).encode() + b"\0")
    fingerprint = digest.hexdigest()
    destination = ROOT / "releases"
    state_file = destination / ".build-state.json"
    try:
        state = json.loads(state_file.read_text())
        cached = destination / Path(state["archive"]).name
        if (
            state["inputs"] == fingerprint
            and cached.is_file()
            and file_hash(cached) == state["sha256"]
        ):
            print(f"源码未变，复用部署包：{cached}")
            return
    except (OSError, ValueError, KeyError, TypeError):
        pass
    subprocess.run(["npm", "run", "build"], cwd=ROOT, check=True)
    destination.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = destination / f"litonglab-{stamp}.tar.gz"
    with tarfile.open(output, "w:gz", compresslevel=6) as archive:
        for file in files_in(SOURCES):
            archive.add(file, arcname=str(file.relative_to(ROOT)), recursive=False)
    state_file.write_text(
        json.dumps(
            {
                "inputs": fingerprint,
                "archive": output.name,
                "sha256": file_hash(output),
            }
        )
    )
    print(f"部署包：{output}（{output.stat().st_size / 1024**2:.1f} MB）")


if __name__ == "__main__":
    main()
