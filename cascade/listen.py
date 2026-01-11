"""
Cascade Passive Monitor.

Listens to stdin or follows a log file and observes events.

Usage:
    python -m cascade.listen                    # Listen to stdin
    python -m cascade.listen --follow app.log   # Follow a log file

This module:
1. Reads input from stdin or a log file
2. Pipes lines -> Cascade Adapter
3. Writes events to tape file (JSONL) and human log (Markdown)
4. Emits events to event_queue for external consumers

For visualization, point a consumer at the event_queue or load the tape file
into your preferred visualization tool.
"""

import sys
import argparse
import time
import json
from pathlib import Path
from queue import Queue

# Ensure package root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cascade import Monitor

# Shared event queue for external consumers (e.g., custom UIs)
event_queue: Queue = Queue()


def main():
    parser = argparse.ArgumentParser(description="Cascade Passive Monitor")
    parser.add_argument("--log-dir", default="./logs", help="Directory for logs")
    parser.add_argument("--follow", help="Log file to follow (tail -f style)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress console output")
    args = parser.parse_args()

    # 0. Setup Logs & Baggies
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    baggies_dir = log_dir / "baggies"
    baggies_dir.mkdir(exist_ok=True)
    
    # Excrement Management (Archive old artifacts)
    follow_abs = Path(args.follow).absolute() if args.follow else None
    for f in log_dir.glob("*.*"):
        if f.is_file() and f.suffix in [".md", ".jsonl", ".log"] and "baggies" not in str(f):
            if follow_abs and f.absolute() == follow_abs:
                continue
            try:
                dest = baggies_dir / f.name
                if dest.exists():
                    dest = baggies_dir / f"{f.stem}_{int(time.time())}{f.suffix}"
                f.replace(dest)
            except Exception:
                pass
    print(f"[CASCADE] Logs archived to {baggies_dir}")

    session_id = int(time.time())
    tape_path = log_dir / f"cascade_tape_{session_id}.jsonl"
    human_path = log_dir / f"cascade_log_{session_id}.md"
    
    tape_file = open(tape_path, "w", encoding="utf-8")
    human_file = open(human_path, "w", encoding="utf-8")
    
    # Init Log
    human_file.write(f"# CASCADE MISSION LOG // SESSION {session_id}\n")
    human_file.write(f"**Mode:** PASSIVE {'FOLLOWER' if args.follow else 'LISTENER'}\n")
    human_file.write(f"**Target:** `{args.follow or 'STDIN'}`\n---\n\n")
    human_file.flush()
    
    print("="*60)
    print("CASCADE // LISTENER")
    print(f"Monitoring: {args.follow if args.follow else 'Standard Input'}")
    print(f"Tape:       {tape_path.absolute()}")
    print(f"Baggies:    {baggies_dir.absolute()}")
    print("="*60)

    monitor = Monitor("symbiont_passive")

    def process_line(line):
        line = line.strip()
        if not line:
            return
        event = monitor.observe(line)
        payload = {
            "event": {
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "component": event.component,
                "event_type": event.event_type,
                "data": event.data,
                "raw": line,  # Include original line for drill-down
            },
            "metrics": monitor.metrics.summary(),
            "triage": monitor.metrics.triage(),
        }
        event_queue.put(payload)
        tape_file.write(json.dumps(payload) + "\n")
        tape_file.flush()
        
        # Narrative
        t_str = time.strftime('%H:%M:%S', time.localtime(event.timestamp))
        icon = {"error": "🔴", "warning": "⚠️", "state_change": "🔄"}.get(event.event_type, "ℹ️")
        if "loss" in str(event.data):
            icon = "📉"
        human_file.write(f"### {icon} {t_str} // {event.event_type.upper()}\n")
        human_file.write(f"Event observed in **{event.component}**.\n")
        if event.data:
            human_file.write("```yaml\n")
            for k, v in event.data.items():
                human_file.write(f"{k}: {v}\n")
            human_file.write("```\n")
        human_file.write("\n")
        human_file.flush()
        
        # Mirror to console (unless quiet)
        if not args.quiet:
            sys.stdout.write(f"[SIGHT] {line[:80]}...\n")
            sys.stdout.flush()

    try:
        if args.follow:
            print(f"[CASCADE] Waiting for stream: {args.follow}")
            f_path = Path(args.follow)
            if not f_path.exists():
                f_path.touch()
            with open(f_path, "r", encoding="utf-8", errors="replace") as f:
                print(f"[CASCADE] Scanning for events...")
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    process_line(line)
        else:
            print("[CASCADE] Reading from stdin (Ctrl+C to stop)...")
            for line in sys.stdin:
                process_line(line)
    except KeyboardInterrupt:
        print("\n[CASCADE] Detaching...")
    finally:
        tape_file.close()
        human_file.close()
        print(f"[CASCADE] Session complete. Tape: {tape_path}")

if __name__ == "__main__":
    main()
