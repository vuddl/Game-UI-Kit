#!/usr/bin/env python3
"""Install or update game-ui-kit and its gui-* commands from GitHub, or from a local zip."""
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
        roots = [p for p in stage.rglob("SKILL.md") if p.parent.name == "game-ui-kit" or p.parent.name.startswith("gui-")]
        folders = [p.parent for p in roots]
        if not any(f.name == "game-ui-kit" for f in folders):
            print("The archive has no game-ui-kit skill, nothing changed.", file=sys.stderr)
            return 1
        skills.mkdir(parents=True, exist_ok=True)
        for folder in folders:
            target = skills / folder.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(folder, target)
    print(f"Installed {len(folders)} skills in {skills}. Open a new Codex session to use them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
