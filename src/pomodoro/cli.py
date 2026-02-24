import sys

from pomodoro import Pomodoro


def main():
    p = Pomodoro()
    command = sys.argv[1] if len(sys.argv) > 1 else None

    if command == "start":
        duration = None
        if len(sys.argv) > 2:
            try:
                duration = int(sys.argv[2])
            except ValueError:
                print("Error: Duration must be a positive integer", file=sys.stderr)
                sys.exit(1)
        try:
            mins = p.start(duration)
            print(f"Starting work session: {mins} minutes")
        except (ValueError, RuntimeError) as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    elif command == "stop":
        try:
            p.stop()
            print("Pomodoro stopped")
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    elif command == "extend":
        try:
            new_time = p.extend()
            print(f"Extended timer by 10 minutes. New time: {new_time} minutes")
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    elif command == "status":
        info = p.status()
        print(f"Status: {info['state']}")
        if "remaining" in info:
            print(f"Time remaining: {info['remaining']} minutes")
        print(f"Completed pomodoros today: {info['completed']}")

    elif command == "starship":
        output = p.starship()
        if output is None:
            sys.exit(1)
        print(output)

    elif command == "waybar":
        output = p.waybar()
        if output is None:
            sys.exit(1)
        sys.stdout.write(output)

    else:
        print("Usage: pomodoro {start|stop|extend|status|starship|waybar}")
        print("  start    - Start a new pomodoro work session (optional: duration in minutes)")
        print("  stop     - Stop the current pomodoro")
        print("  extend   - Add 10 minutes to current timer")
        print("  status   - Show current status")
        print("  starship - Output status for starship prompt")
        print("  waybar   - Output status for waybar (returns failure when idle)")
        sys.exit(1)
