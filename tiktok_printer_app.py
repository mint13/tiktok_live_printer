"""
Simple settings window for the TikTok Live "mine" label printer.

Run:
    python3 tiktok_printer_app.py

Fill in the settings, click Start. Settings are saved to config.json (next to this file)
and the label printer script (tiktok_mine_printer.py) runs in the background.
Its output shows in the box at the bottom of the window.
"""
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

FOLDER = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(FOLDER, "config.json")
SCRIPT_PATH = os.path.join(FOLDER, "tiktok_mine_printer.py")

DEFAULTS = {
    "TIKTOK_USERNAME": "your_username",
    "STORE_NAME": "YOUR STORE NAME",
    "PRINTER_NAME": "YOUR PRINTER NAME",
    "LABEL_WIDTH_MM": 40,
    "LABEL_HEIGHT_MM": 30,
    "LABEL_GAP_MM": 3,
    "KEYWORD": "mine",
    "DUPLICATE_WINDOW_SECONDS": 3,
    "STARTUP_IGNORE_SECONDS": 600,
}

# (setting name, label shown in the window, small hint under the box)
FIELDS = [
    ("TIKTOK_USERNAME", "TikTok username", "Your live account, without the @"),
    ("STORE_NAME", "Store name", "Printed on the first line of every label"),
    ("PRINTER_NAME", "Printer name", "Exact name from Terminal command:  lpstat -p"),
    ("LABEL_WIDTH_MM", "Label width (mm)", ""),
    ("LABEL_HEIGHT_MM", "Label height (mm)", ""),
    ("LABEL_GAP_MM", "Label gap (mm)", "Gap between labels on the roll"),
    ("KEYWORD", "Keyword", "Viewers comment:  <keyword> <number>   e.g. mine 500"),
    ("DUPLICATE_WINDOW_SECONDS", "Duplicate window (seconds)", "After the first claim of a number, ignore the same number for this long"),
    ("STARTUP_IGNORE_SECONDS", "Startup ignore (seconds)", "After connecting, ALL comments are ignored for this long (600 = 10 minutes)"),
]
NUMBER_FIELDS = {
    "LABEL_WIDTH_MM", "LABEL_HEIGHT_MM", "LABEL_GAP_MM",
    "DUPLICATE_WINDOW_SECONDS", "STARTUP_IGNORE_SECONDS",
}
ZERO_OK = {"LABEL_GAP_MM", "DUPLICATE_WINDOW_SECONDS", "STARTUP_IGNORE_SECONDS"}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TikTok Live Label Printer")
        self.minsize(680, 640)
        self.proc = None
        self.lines = queue.Queue()
        self.vars = {}
        self.entries = {}

        saved = self.load_saved()

        form = ttk.Frame(self, padding=(14, 10, 14, 0))
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        for i, (key, label, hint) in enumerate(FIELDS):
            ttk.Label(form, text=label).grid(row=i * 2, column=0, sticky="w", pady=(8, 0))
            var = tk.StringVar(value=str(saved[key]))
            entry = ttk.Entry(form, textvariable=var, width=36)
            entry.grid(row=i * 2, column=1, sticky="ew", padx=(14, 0), pady=(8, 0))
            if hint:
                ttk.Label(form, text=hint, foreground="#777777").grid(
                    row=i * 2 + 1, column=1, sticky="w", padx=(14, 0))
            self.vars[key] = var
            self.entries[key] = entry

        buttons = ttk.Frame(self, padding=(14, 14, 14, 0))
        buttons.pack(fill="x")
        self.start_btn = ttk.Button(buttons, text="Save & Start", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(buttons, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        self.reset_btn = ttk.Button(buttons, text="Reset to defaults", command=self.reset_defaults)
        self.reset_btn.pack(side="left")

        self.status = tk.StringVar(value="Not running. Go live on TikTok first, then click Save & Start.")
        ttk.Label(self, textvariable=self.status, padding=(14, 10, 14, 4)).pack(fill="x")

        log_frame = ttk.Frame(self, padding=(14, 0, 14, 14))
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, height=12, wrap="word", state="disabled",
                           font=("Menlo", 11) if sys.platform == "darwin" else ("Consolas", 10))
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- settings ----------
    def load_saved(self):
        values = dict(DEFAULTS)
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                values.update(json.load(f))
        except (FileNotFoundError, ValueError):
            pass
        return values

    def reset_defaults(self):
        for key, var in self.vars.items():
            var.set(str(DEFAULTS[key]))

    def read_form(self):
        values = {}
        for key, label, _ in FIELDS:
            text = self.vars[key].get().strip()
            if key == "TIKTOK_USERNAME":
                text = text.lstrip("@").strip()
            if not text:
                messagebox.showerror("Missing value", f"Please fill in: {label}")
                return None
            if key == "KEYWORD" and any(ch.isspace() for ch in text):
                messagebox.showerror("Invalid keyword", "The keyword can't contain spaces.")
                return None
            if key in NUMBER_FIELDS:
                try:
                    number = float(text)
                except ValueError:
                    messagebox.showerror("Not a number", f"{label} must be a number.")
                    return None
                if number < 0 or (number == 0 and key not in ZERO_OK):
                    messagebox.showerror("Invalid number", f"{label} must be greater than 0.")
                    return None
                values[key] = int(number) if number.is_integer() else number
            else:
                values[key] = text
        return values

    def save_config(self, values):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(values, f, indent=2)

    # ---------- running the listener ----------
    def start(self):
        if self.proc is not None:
            return
        values = self.read_form()
        if values is None:
            return
        try:
            self.save_config(values)
        except OSError as e:
            messagebox.showerror("Could not save settings", str(e))
            return

        self.clear_log()
        self.lines = queue.Queue()
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            self.proc = subprocess.Popen(
                [sys.executable, "-u", SCRIPT_PATH],
                cwd=FOLDER,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                **kwargs,
            )
        except OSError as e:
            messagebox.showerror("Could not start", str(e))
            return

        threading.Thread(target=self.read_output, args=(self.proc, self.lines), daemon=True).start()
        self.set_running(True)
        self.status.set(f"Running for @{values['TIKTOK_USERNAME']}. Keep this window open during your live.")
        self.poll()

    def read_output(self, proc, lines):
        for line in proc.stdout:
            lines.put(line)
        proc.wait()
        lines.put(None)

    def poll(self):
        try:
            while True:
                line = self.lines.get_nowait()
                if line is None:
                    self.on_exit()
                    break
                self.append_log(line)
        except queue.Empty:
            pass
        if self.proc is not None:
            self.after(100, self.poll)

    def on_exit(self):
        self.proc = None
        self.append_log("\n[Stopped]\n")
        self.set_running(False)
        self.status.set("Not running.")

    def stop(self):
        proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        self.status.set("Stopping... (writing the end-of-live summary)")
        if sys.platform == "win32":
            proc.terminate()  # on Windows this skips the summary
        else:
            proc.send_signal(signal.SIGINT)  # same as Ctrl+C: prints the summary and saves the files
        self.after(10000, lambda: proc.poll() is None and proc.kill())

    def on_close(self):
        proc = self.proc
        if proc is not None and proc.poll() is None:
            if not messagebox.askyesno("Quit", "The listener is still running. Stop it and quit?"):
                return
            self.stop()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.destroy()

    # ---------- small helpers ----------
    def set_running(self, running):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.reset_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")
        for entry in self.entries.values():
            entry.configure(state="disabled" if running else "normal")

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        # keep the box from growing forever
        if int(self.log.index("end-1c").split(".")[0]) > 3000:
            self.log.delete("1.0", "1000.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    App().mainloop()