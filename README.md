# TikTok Live "Mine" Label Printer

Prints a label on your XP-420B printer every time a viewer comments `mine <number>` on your TikTok Live. At the end of the live, it gives you each buyer's items and total.

## What it does

When a viewer comments `mine 500`, the script prints a label like this:

```
Your Store Name
2026-10-05 04:48:10 PM
Maria Santos(maria_s88)
500
```

- **First comment wins.** If several people comment `mine 1200` within 2 seconds of each other, only the first one prints. This is meant for items that have just one in stock.
- **Old comments are ignored.** Comments made before the script started are never printed.
- **Each number is separate.** `mine 500` and `mine 1200` at the same time both print.
- **End-of-live summary.** Every item is listed per buyer, with a total, and saved to files.

## What's in this folder

| File | What it is |
|---|---|
| `tiktok_printer_app.py` | The settings window. Fill in your settings and start the printer from here. |
| `tiktok_mine_printer.py` | The script that listens to your live and prints (the window starts it for you) |
| `Start TikTok Printer.command` | Double-click launcher for Mac. It opens the settings window. |
| `config.json` | Created automatically. Holds your saved settings. |
| `README.md` | This guide |

When a live ends, the script also creates two files in this same folder:

- `live_summary_<date>_<time>.csv` has one row per item, plus a total row for each buyer. It opens in Excel or Numbers.
- `live_messages_<date>_<time>.txt` has a ready-to-paste message for each buyer.

## What you need

- A Mac (Windows also works, see the Windows section at the bottom)
- Python 3.10 or newer, from python.org
- The XP-420B printer, connected by USB and added to your Mac
- A TikTok account that is going live

## One-time setup (Mac)

1. **Install Python** from python.org.
2. **Install the library.** Open Terminal and run:
   ```
   pip3 install TikTokLive
   ```
3. **Fix certificates.** Open the Applications folder, then the Python folder, and double-click **Install Certificates.command**. Do this once. It prevents a "CERTIFICATE_VERIFY_FAILED" error.
4. **Add the printer.** Go to System Settings > Printers & Scanners and add the XP-420B. If the Xprinter driver isn't available, choose "Generic" as the driver.
5. **Find the printer's exact name.** In Terminal, run:
   ```
   lpstat -p
   ```
   Copy the name right after the word `printer`.
6. **Make the launcher runnable.** In Terminal, run this once, with your own folder path:
   ```
   chmod +x "/path/to/your/folder/Start TikTok Printer.command"
   ```
   The first time you open it, right-click the file, choose **Open**, then click **Open** again.

## Settings

You enter all settings in the settings window. Click **Save & Start** and they are saved to `config.json`, so they are filled in the next time you open the window. **Reset to defaults** puts the values below back.

| Setting | What it does | Default |
|---|---|---|
| TikTok username | Your live account, without the `@` | `sapphoena` |
| Store name | The first line on the label | `Sapphoena` |
| Printer name | The exact printer name from `lpstat -p` | `Xprinter_XP_420B` |
| Label width (mm) | Label width in millimeters | `40` |
| Label height (mm) | Label height in millimeters | `30` |
| Label gap (mm) | Gap between labels on the roll | `3` |
| Keyword | The word viewers type before the number | `mine` |
| Duplicate window (seconds) | After the first claim of a number, other claims of it are ignored for this long | `3` |
| Startup ignore (seconds) | After connecting, every comment is ignored for this long, so old comments never print | `600` |

**About the startup ignore:** 600 seconds is 10 minutes. For that long after the script connects, no claim prints, including real ones. If you start the script while the live is already running, lower this (for example to `5`) so new claims print right away.

The window cannot change settings while the printer is running. Stop it first, edit, then start again.

## Running it

1. **Go live on TikTok first.**
2. Double-click `Start TikTok Printer.command`. A Terminal window opens, then the settings window.
3. Check the settings and click **Save & Start**.
4. Wait for `Connected to @yourusername's live` in the box at the bottom of the window. The script is now listening.
5. **Keep both windows open** for the whole live.
6. When your live ends, the summary appears in the window and the files are saved. To stop earlier, click **Stop**, which also shows the summary.

If you start it before going live, it checks again every 10 seconds and connects once you are live.

You can also skip the window and run the script directly with `python3 tiktok_mine_printer.py`. It reads `config.json`, and a username typed after the command (`python3 tiktok_mine_printer.py yourusername`) overrides the saved one.

## What you see in the window

| Message | Meaning |
|---|---|
| `COMMENT: name: 'text'` | Every comment the script receives |
| `IGNORED (old comment...)` | A comment from before the script started, so it is skipped |
| `MATCH: name (@user) -> 500` | A valid claim, sent to the printer |
| `SKIPPED (too late)` | Someone else already claimed that number in the time window |
| `PRINT FAILED: ...` | The label did not print. The reason follows the message. |

## End-of-live summary

At the end, each buyer's items are listed in the order they claimed them, with a total, and the biggest total comes first:

```
@maria_s88
  1) 1,200
  2) 500
  3) 1,000
  Total: 2,700

@juan_dc
  1) 800
  Total: 800

Grand total: 3,500
```

Copy any block from the `.txt` file and paste it into the live chat or a DM. The script cannot post to TikTok for you.

Only claims that actually printed are counted. Totals are kept in memory, so close the live properly or press Ctrl+C. If you close Terminal or the script crashes, that live's totals are lost.

## Troubleshooting

| Problem | What to do |
|---|---|
| `is not live yet (or the username is wrong)` | Check that you are live. Use your exact `@handle` as shown in your profile link, not your display name. Open `tiktok.com/@yourusername/live` in a browser to check. |
| `CERTIFICATE_VERIFY_FAILED` | Run **Install Certificates.command** (setup step 3). If it still fails, turn off any VPN, antivirus web protection, or proxy, or try a different network. |
| Connects but no `COMMENT:` lines | Upgrade the library: `pip3 install --upgrade TikTokLive`, then restart. |
| `COMMENT:` shows but never `MATCH:` | The comment must be only the keyword and a number, like `mine 500`. |
| `PRINT FAILED` and the printer does not exist | The `PRINTER_NAME` is wrong. Run `lpstat -p` and copy the exact name. |
| `PRINT FAILED` and the printer is not accepting jobs | Turn the printer on and check the USB cable. Then run `cupsenable PRINTERNAME` and `cupsaccept PRINTERNAME` in Terminal. |
| Garbage text prints, or nothing prints | Remove the printer and add it again with the Xprinter driver, or "Generic". |
| The label is cut off or shifted | Adjust the label size and gap settings, or the `TEXT` positions in `build_tspl`. |
| Emoji in names print as `?` | Normal. The printer's built-in fonts only support plain letters and numbers. |

### Test the printer by itself

This checks the printer without TikTok. Use your real printer name instead of `XP_420B`:

```
printf 'SIZE 80 mm,50 mm\r\nGAP 3 mm,0 mm\r\nCLS\r\nTEXT 20,20,"3",0,1,1,"TEST"\r\nPRINT 1,1\r\n' | lp -d XP_420B -o raw
```

A label that says TEST should print. If it does not, the problem is the printer setup, not the script.

## Good to know

- The script reads public live comments through an unofficial library. It does not log in to TikTok and cannot post comments.
- Because it is unofficial, TikTok updates can break it. If it suddenly stops working, run `pip3 install --upgrade TikTokLive`.
- The summary only shows the amounts, because the script reads just the number in `mine <number>`.
- Restarting the script during a live clears the totals so far.

## Windows

The script also works on Windows.

1. Install Python and tick "Add Python to PATH".
2. Run `pip install TikTokLive pywin32`.
3. Set `PRINTER_NAME` to the exact name in Settings > Printers & scanners.
4. Run it with `python tiktok_mine_printer.py`, or make a small `.bat` file that runs that command.