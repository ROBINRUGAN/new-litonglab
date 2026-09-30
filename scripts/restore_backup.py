# designed by mew
"""Restore a verified backup into an EMPTY directory; never overwrite live data."""

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def restore(archive_path: Path, destination: Path):
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("目标目录必须为空。请先停止服务，将原数据目录改名保留。")
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != 1 or "lab.sqlite3" not in manifest["files"]:
                raise ValueError("不是受支持的 LitongLab 完整备份。")
            for name, checksum in manifest["files"].items():
                target = (staging / name).resolve()
                if not target.is_relative_to(staging.resolve()) or (
                    name != "lab.sqlite3" and not name.startswith("media/")
                ):
                    raise ValueError("备份包含非法文件路径。")
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with archive.open(name) as source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        output.write(chunk)
                if digest.hexdigest() != checksum:
                    raise ValueError(f"校验失败：{name}")
            with sqlite3.connect(staging / "lab.sqlite3") as database:
                if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("数据库完整性检查失败。")
        destination.mkdir(parents=True, exist_ok=True, mode=0o750)
        for child in staging.iterdir():
            shutil.move(str(child), destination / child.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    restore(args.archive, args.destination)
    print(f"恢复完成：{args.destination}。请核对权限与环境变量后再启动服务。")


if __name__ == "__main__":
    main()
