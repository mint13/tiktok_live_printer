"""Tiny .env reader/writer, so no extra packages are needed."""
import os
import re


def parse_env(path: str) -> dict:
    """Read KEY=value lines. Supports "double quoted", 'single quoted' and plain values."""
    values = {}
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[7:].lstrip()
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if len(val) >= 2 and val[0] == val[-1] == '"':
                    val = re.sub(r'\\(["\\])', r"\1", val[1:-1])
                elif len(val) >= 2 and val[0] == val[-1] == "'":
                    val = val[1:-1]
                values[key] = val
    except FileNotFoundError:
        pass
    return values


def _format(key: str, value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}="{escaped}"'


def update_env(path: str, updates: dict) -> None:
    """Set the given keys in the .env file. Other lines and comments are left alone.
    The file is only readable by you (permissions 600) on Mac/Linux."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []

    remaining = dict(updates)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.removeprefix("export ").partition("=")[0].strip()
        if key in remaining:
            lines[i] = _format(key, remaining.pop(key))
    for key, value in remaining.items():
        lines.append(_format(key, value))

    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)