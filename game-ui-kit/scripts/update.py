#!/usr/bin/env python3
"""Install or update game-ui-kit and its commands ($setup, $wireframe, $mockup, $export, $reset, $info) from GitHub or a local zip.

Removes the old gui-* commands and any command an earlier install added that is gone now."""
import json
import argparse
import io
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

URL = "https://github.com/vuddl/Game-UI-Kit/archive/refs/heads/main.zip"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", help="Use this local zip instead of downloading")
    args = parser.parse_args()
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    skills = home / "skills"
    try:
        if args.zip:
            data = Path(args.zip).read_bytes()
        else:
            request = urllib.request.Request(URL, headers={"User-Agent": "game-ui-kit-update"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
    except OSError as exc:
        print(f"Could not get the update, nothing changed: {exc}", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.namelist():
                parts = Path(member).parts
                if ".." in parts or Path(member).is_absolute():
                    print(f"Unsafe path in the archive, nothing changed: {member}", file=sys.stderr)
                    return 1
            archive.extractall(stage)
        roots = [p for p in stage.rglob("SKILL.md")
                 if p.parent.name == "game-ui-kit" or p.parent.parent.name == "commands"]
        folders = [p.parent for p in roots]
        if not any(f.name == "game-ui-kit" for f in folders):
            print("The archive has no game-ui-kit skill, nothing changed.", file=sys.stderr)
            return 1
        skills.mkdir(parents=True, exist_ok=True)
        record = skills / ".game-ui-kit.json"
        try:
            earlier = set(json.loads(record.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            earlier = set()
        names = {f.name for f in folders}
        stale = sorted((earlier - names) | {p.name for p in skills.glob("gui-*") if p.is_dir()})
        for name in stale:
            shutil.rmtree(skills / name, ignore_errors=True)
        for folder in folders:
            target = skills / folder.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(folder, target)
        record.write_text(json.dumps(sorted(names)), encoding="utf-8")
    print(f"Installed {len(folders)} skills in {skills}: {', '.join(sorted(names))}.")
    if stale:
        print(f"Removed old commands: {', '.join(stale)}.")
    print("Open a new Codex session to use them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
