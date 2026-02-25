import os
import re
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path

from today import DiaryDate, KVManager

WORK_DURATION = 60
BREAK_DURATION = 10
STATE_FILE = Path.home() / ".pomodoro_state"


class Pomodoro:
    def get_state(self, key, default=""):
        """Read a key from the state file."""
        if not STATE_FILE.exists():
            return default
        for line in STATE_FILE.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1]
        return default

    def set_state(self, key, value):
        """Set a key in the state file."""
        STATE_FILE.touch(exist_ok=True)
        lines = [
            l
            for l in STATE_FILE.read_text().splitlines()
            if not l.startswith(f"{key}=")
        ]
        lines.append(f"{key}={value}")
        STATE_FILE.write_text("\n".join(lines) + "\n")

    def remove_state(self, key):
        """Remove a key from the state file."""
        if not STATE_FILE.exists():
            return
        lines = [
            l
            for l in STATE_FILE.read_text().splitlines()
            if not l.startswith(f"{key}=")
        ]
        STATE_FILE.write_text("\n".join(lines) + "\n")

    def _update_matrix(self, text):
        """Send text to the HA matrix display via show."""
        try:
            subprocess.run(
                ["show"], input=text, text=True, capture_output=True, timeout=5
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _get_distraction_stats(self):
        """Get daily distraction count and weekly average."""
        diary = DiaryDate()
        kv = KVManager()
        today_path = str(diary.filepath(datetime.today(), create=False))
        today_distractions = kv.get([today_path], "distractions")
        week_paths = [str(p) for p in diary.week_files()]
        weekly_avg = kv.get(week_paths, "distractions") if week_paths else 0
        return today_distractions, weekly_avg

    def start(self, duration=None):
        """Start a pomodoro work session. Spawns a background timer via fork."""
        work_duration = duration or WORK_DURATION

        if not isinstance(work_duration, int) or work_duration <= 0:
            raise ValueError("Duration must be a positive integer")

        current_state = self.get_state("POMODORO_STATE", "idle")
        if current_state != "idle":
            remaining = self._remaining_minutes()
            raise RuntimeError(
                f"Pomodoro already running. State: {current_state}, "
                f"remaining: {remaining} minutes"
            )

        self.set_state("POMODORO_STATE", "work")
        self.set_state("POMODORO_TIME", str(work_duration))
        self.set_state("POMODORO_START_TIME", str(int(time.time())))

        self._update_matrix(f"{work_duration}m")

        pid = os.fork()
        if pid == 0:
            # Child process — run the timer
            try:
                self._run_timer(work_duration)
            finally:
                os._exit(0)

        # Parent — record child PID
        self.set_state("POMODORO_PID", str(pid))
        return work_duration

    def _run_timer(self, work_duration):
        """Background timer: work -> break -> idle transitions."""
        time.sleep(work_duration * 60)

        if self.get_state("POMODORO_STATE", "idle") != "work":
            return

        # Work session completed — increment pomodoro count
        diary = DiaryDate()
        kv = KVManager()
        diary_path = str(diary.filepath(datetime.today(), create=True))
        kv.add(diary_path, "pomodoro", 1)

        self.set_state("POMODORO_STATE", "break")
        self.set_state("POMODORO_TIME", str(BREAK_DURATION))
        self.set_state("POMODORO_START_TIME", str(int(time.time())))
        self._update_matrix(f"{BREAK_DURATION}m")

        # Break timer
        time.sleep(BREAK_DURATION * 60)

        if self.get_state("POMODORO_STATE", "idle") != "break":
            return

        self.set_state("POMODORO_STATE", "idle")
        self.remove_state("POMODORO_TIME")
        self.remove_state("POMODORO_START_TIME")
        self.remove_state("POMODORO_PID")
        self._update_matrix("")

    def stop(self):
        """Stop the current pomodoro."""
        current_state = self.get_state("POMODORO_STATE", "idle")
        if current_state == "idle":
            raise RuntimeError("No pomodoro running")

        pid = self.get_state("POMODORO_PID", "")
        if pid:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (ProcessLookupError, ValueError):
                pass

        self.set_state("POMODORO_STATE", "idle")
        self.remove_state("POMODORO_TIME")
        self.remove_state("POMODORO_START_TIME")
        self.remove_state("POMODORO_PID")

        today_distractions, _ = self._get_distraction_stats()
        self._update_matrix(f"d: {today_distractions}")

    def extend(self, minutes=10):
        """Extend the current timer by the given minutes."""
        current_state = self.get_state("POMODORO_STATE", "idle")
        if current_state == "idle":
            raise RuntimeError("No pomodoro running")

        current_time = int(self.get_state("POMODORO_TIME", "0"))
        new_time = current_time + minutes
        self.set_state("POMODORO_TIME", str(new_time))
        return new_time

    def _remaining_minutes(self):
        """Calculate remaining minutes for the current timer."""
        start_time = int(self.get_state("POMODORO_START_TIME", "0"))
        current_time = int(self.get_state("POMODORO_TIME", "0"))
        elapsed = (int(time.time()) - start_time) // 60
        remaining = current_time - elapsed
        return max(remaining, 0)

    def _remaining_seconds_total(self):
        """Calculate total remaining seconds for the current timer."""
        start_time = int(self.get_state("POMODORO_START_TIME", "0"))
        current_time = int(self.get_state("POMODORO_TIME", "0"))
        if start_time:
            elapsed = int(time.time()) - start_time
            total = current_time * 60
            return max(total - elapsed, 0)
        return current_time * 60

    def status(self):
        """Return current status as a dict."""
        state = self.get_state("POMODORO_STATE", "idle")
        result = {"state": state}

        if state != "idle":
            result["remaining"] = self._remaining_minutes()

        diary = DiaryDate()
        kv = KVManager()
        diary_path = str(diary.filepath(datetime.today(), create=False))
        result["completed"] = kv.get([diary_path], "pomodoro")

        return result

    def starship(self):
        """Format status for starship prompt. Returns None when idle."""
        state = self.get_state("POMODORO_STATE", "idle")
        if state == "idle":
            return None

        remaining_total = self._remaining_seconds_total()
        minutes = remaining_total // 60
        seconds = remaining_total % 60

        if state == "break":
            self._update_matrix(f"BREAK: {minutes}:{seconds}")
            return f"\u2615 {minutes}:{seconds:02d}"

        # work state
        self._update_matrix(f"{minutes}:{seconds}")
        today_distractions, weekly_avg = self._get_distraction_stats()
        return (
            f"\U0001f345 {minutes}:{seconds:02d} "
            f"\U0001f4f1{today_distractions}({weekly_avg})"
        )

    def waybar(self):
        """Format status for waybar. Returns None when idle."""
        state = self.get_state("POMODORO_STATE", "idle")
        if state == "idle":
            return None

        remaining_total = self._remaining_seconds_total()
        minutes = remaining_total // 60
        seconds = remaining_total % 60

        if state == "break":
            self._update_matrix(f"BREAK: {minutes}:{seconds}")
            return f"\u2615 {minutes}:{seconds:02d}"

        # work state
        self._update_matrix(f"{minutes}:{seconds}")
        today_distractions, weekly_avg = self._get_distraction_stats()
        return (
            f"\U0001f345 {minutes}:{seconds:02d} "
            f"\U0001f4f1{today_distractions}({weekly_avg})"
        )


def increment_distracted(path):
    """Increment the distracted counter in the YAML frontmatter of the given file."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""

    if text.startswith("---\n"):
        end = text.index("\n---\n", 4)
        front = text[4:end]
        rest = text[end + 5:]

        m = re.search(r"^(distracted:\s*)(\d+)", front, re.MULTILINE)
        if m:
            count = int(m.group(2)) + 1
            front = front[:m.start(2)] + str(count) + front[m.end(2):]
        else:
            count = 1
            front = front.rstrip("\n") + f"\ndistracted: {count}\n"

        path.write_text(f"---\n{front}\n---\n{rest}", encoding="utf-8")
    else:
        count = 1
        path.write_text(f"---\ndistracted: {count}\n---\n{text}", encoding="utf-8")

    return count
