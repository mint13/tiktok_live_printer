"""
TikTok Live "mine 500" -> XP-420B label printer

Setup:
    pip3 install TikTokLive

Run:
    python3 tiktok_mine_printer.py
"""
import asyncio
import re
from datetime import datetime

import subprocess
import sys
import time
import csv
import json
import os

from env_file import parse_env
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, ConnectEvent

# ---------------- SETTINGS ----------------
# TIKTOK_USERNAME, STORE_NAME and PRINTER_NAME come from the .env file.
# The other settings come from config.json. Both are saved by the settings window
# (tiktok_printer_app.py). Anything missing falls back to these defaults.
DEFAULTS = {
    "TIKTOK_USERNAME": "sapphoena",
    "STORE_NAME": "Sapphoena",
    "PRINTER_NAME": "Xprinter_XP_420B",   # exact name from Terminal command: lpstat -p
    "LABEL_WIDTH_MM": 40,
    "LABEL_HEIGHT_MM": 30,
    "LABEL_GAP_MM": 3,
    "KEYWORD": "mine",                    # comment must be: mine <number>
    "DUPLICATE_WINDOW_SECONDS": 3,        # after the first "mine 1200", ignore other "mine 1200" for this long
    "STARTUP_IGNORE_SECONDS": 600,        # ignore all comments for this long after connecting
}  # (the first three are also the fallback when .env is missing)
ENV_KEYS = ("TIKTOK_USERNAME", "STORE_NAME", "PRINTER_NAME")
FOLDER = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(FOLDER, "config.json")
ENV_PATH = os.path.join(FOLDER, ".env")


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (FileNotFoundError, ValueError):
        pass
    env = parse_env(ENV_PATH)  # .env wins over config.json for these three values
    for key in ENV_KEYS:
        if env.get(key):
            cfg[key] = env[key]
    return cfg


_cfg = load_config()
# A username typed on the command line still wins: python3 tiktok_mine_printer.py yourusername
TIKTOK_USERNAME = (sys.argv[1] if len(sys.argv) > 1 else str(_cfg["TIKTOK_USERNAME"])).strip().lstrip("@")
STORE_NAME = str(_cfg["STORE_NAME"])
PRINTER_NAME = str(_cfg["PRINTER_NAME"])
LABEL_WIDTH_MM = _cfg["LABEL_WIDTH_MM"]
LABEL_HEIGHT_MM = _cfg["LABEL_HEIGHT_MM"]
LABEL_GAP_MM = _cfg["LABEL_GAP_MM"]
KEYWORD = str(_cfg["KEYWORD"])
DUPLICATE_WINDOW_SECONDS = _cfg["DUPLICATE_WINDOW_SECONDS"]
STARTUP_IGNORE_SECONDS = _cfg["STARTUP_IGNORE_SECONDS"]
# ------------------------------------------

PATTERN = re.compile(rf"^\s*{re.escape(KEYWORD)}\s+(\d+)\s*$", re.IGNORECASE)


def clean(text: str) -> str:
    """Printer's built-in fonts are ASCII only; drop emoji/symbols and quotes."""
    text = text.replace('"', "'")
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in text).strip()


def build_tspl(nickname: str, username: str, number: str) -> bytes:
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    lines = [
        f"SIZE {LABEL_WIDTH_MM} mm,{LABEL_HEIGHT_MM} mm",
        f"GAP {LABEL_GAP_MM} mm,0 mm",
        "DIRECTION 1",
        "CLS",
        f'TEXT 20,20,"3",0,1,1,"{clean(STORE_NAME)}"',
        f'TEXT 20,65,"2",0,1,1,"{now}"',
        f'TEXT 20,110,"3",0,1,1,"{clean(nickname)}({clean(username)})"',
        f'TEXT 20,170,"4",0,1,1,"{number}"',
        "PRINT 1,1",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def print_raw(data: bytes) -> None:
    if sys.platform == "win32":
        # Windows: send raw TSPL commands straight to the printer
        import win32print
        handle = win32print.OpenPrinter(PRINTER_NAME)
        try:
            win32print.StartDocPrinter(handle, 1, ("TikTok Order", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)
        return

    # Mac: send raw TSPL commands through CUPS (the Mac print system)
    if not os.path.exists("/usr/bin/lp"):
        raise RuntimeError("The 'lp' print command was not found. This script needs a Mac (or Windows with pywin32).")
    result = subprocess.run(["/usr/bin/lp", "-d", PRINTER_NAME, "-o", "raw"], input=data, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="ignore").strip() or "lp failed")


client = TikTokLiveClient(unique_id=f"@{TIKTOK_USERNAME}")


connected_at = None  # when we connected; comments right after this are old ones


@client.on(ConnectEvent)
async def on_connect(event: ConnectEvent):
    global connected_at
    connected_at = time.monotonic()
    print(f"Connected to @{TIKTOK_USERNAME}'s live. Waiting for '{KEYWORD} <number>' comments...")


last_claimed = {}  # number -> time of the comment that got printed
claims = {}        # username -> {"nickname": ..., "amounts": [...]}  (used for the end-of-live summary)


@client.on(CommentEvent)
async def on_comment(event: CommentEvent):
    print(f"COMMENT: {event.user.nickname}: {event.comment!r}")

    # Skip old comments that TikTok sends when we first connect
    if connected_at is None or time.monotonic() - connected_at < STARTUP_IGNORE_SECONDS:
        print("IGNORED (old comment from before the script started)")
        return

    match = PATTERN.match(event.comment)
    if not match:
        return
    number = match.group(1)
    nickname = event.user.nickname or ""
    username = event.user.unique_id or ""

    # First comment wins: skip if this number was already claimed within the window
    now = time.monotonic()
    claimed_at = last_claimed.get(number)
    if claimed_at is not None and now - claimed_at < DUPLICATE_WINDOW_SECONDS:
        print(f"SKIPPED (too late): {nickname} (@{username}) -> {number}")
        return
    last_claimed[number] = now

    # Remember this claim for the end-of-live summary
    entry = claims.setdefault(username, {"nickname": nickname, "amounts": []})
    entry["amounts"].append(int(number))
    print(f"MATCH: {nickname} (@{username}) -> {number}")
    try:
        print_raw(build_tspl(nickname, username, number))
    except Exception as e:
        print(f"PRINT FAILED: {e}")


def finish_session():
    """Show each user's total, save a CSV and a copy-paste message list."""
    if not claims:
        print("No claims this live.")
        return

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    folder = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(folder, f"live_summary_{stamp}.csv")
    txt_path = os.path.join(folder, f"live_messages_{stamp}.txt")

    users = []
    for username, c in sorted(claims.items(), key=lambda kv: -sum(kv[1]["amounts"])):
        users.append((c["nickname"], username, c["amounts"], sum(c["amounts"])))

    def build_message(username, amounts, total):
        lines = [f"@{username}"]
        lines += [f"  {i}) {a:,}" for i, a in enumerate(amounts, start=1)]
        lines.append(f"  Total: {total:,}")
        return "\n".join(lines)

    messages = [build_message(u, a, t) for _, u, a, t in users]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Account Name", "Username", "Item No", "Amount"])
        for nickname, username, amounts, total in users:
            for i, a in enumerate(amounts, start=1):
                writer.writerow([nickname, username, i, a])
            writer.writerow([nickname, username, "TOTAL", total])

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(messages) + "\n")

    print("\n===== LIVE SUMMARY =====")
    print("\n\n".join(messages))
    print(f"\nGrand total: {sum(u[3] for u in users):,}")
    print(f"Saved: {csv_path}")
    print(f"Saved: {txt_path}")
    print("========================\n")

    claims.clear()
    last_claimed.clear()


async def main():
    while True:
        try:
            if not await client.is_live():
                print(f"@{TIKTOK_USERNAME} is not live yet (or the username is wrong). Checking again in 10 seconds...")
                await asyncio.sleep(10)
                continue
            await client.connect()  # stays running until the live ends
            if not await client.is_live():
                print("The live has ended.")
                finish_session()
            else:
                print("Disconnected but the live is still on. Reconnecting in 10 seconds...")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"Connection problem: {e}. Retrying in 10 seconds...")
        await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")
        finish_session()