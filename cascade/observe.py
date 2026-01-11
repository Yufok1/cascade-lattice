"""
Cascade Observer CLI.

Wraps a target process and observes its output.

Usage:
    python -m cascade.observe --cmd "python path/to/train.py --args..."

This module:
1. Wraps the target process
2. Pipes stdout/stderr -> Cascade Adapter
3. Writes events to tape file (JSONL) and human log (Markdown)
4. Emits events to event_queue for external consumers

For visualization, point a consumer at the event_queue or load the tape file
into your preferred visualization tool.
"""

import sys
import subprocess
import argparse
import time
import json
import shlex
import shutil
from pathlib import Path
from queue import Queue

# Ensure package root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cascade import Monitor

# Shared event queue for external consumers (e.g., custom UIs)
event_queue: Queue = Queue()


def scoop_the_poop(log_dir: Path):
    """
    Baggies system - archive old logs on startup.
    Keeps the logs folder clean. Old sessions go to baggies/.
    """
    baggies_dir = log_dir / "baggies"
    baggies_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all old log files (not the current session)
    tape_files = list(log_dir.glob("cascade_tape_*.jsonl"))
    log_files = list(log_dir.glob("cascade_log_*.md"))
    
    moved_count = 0
    for f in tape_files + log_files:
        if f.parent == log_dir:  # Only files in root logs/, not baggies/
            dest = baggies_dir / f.name
            try:
                shutil.move(str(f), str(dest))
                moved_count += 1
            except Exception as e:
                print(f"[CASCADE] Could not archive {f.name}: {e}")
    
    if moved_count > 0:
        print(f"[CASCADE] 🧹 Scooped {moved_count} old logs → baggies/")


def main():
    parser = argparse.ArgumentParser(
        prog="cascade",
        description="🌊 Cascade - Real-Time Neural Network Observability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cascade --cmd "python train.py"
  cascade --cmd "python train.py --epochs=10"
  cascade --cmd "python train.py" --cwd /path/to/project

Events are written to tape files in the log directory.
        """
    )
    
    # Support both "cascade --cmd" and "cascade observe --cmd"
    subparsers = parser.add_subparsers(dest="command")
    observe_parser = subparsers.add_parser("observe", help="Observe a training process")
    
    # Add args to both main parser and observe subparser
    for p in [parser, observe_parser]:
        p.add_argument("--cmd", required=True, help="Command to run the target process")
        p.add_argument("--cwd", default=None, help="Working directory for the target (absolute path)")
        p.add_argument("--log-dir", default="./logs", help="Directory for session tapes")
        p.add_argument("--quiet", "-q", action="store_true", help="Suppress console output")
    
    args = parser.parse_args()

    # Resolve working directory to absolute
    if args.cwd:
        work_dir = Path(args.cwd).resolve()
    else:
        work_dir = Path.cwd()
    
    # 0. Setup Session Tape (The Excrement/Product)
    log_dir = Path(args.log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 🧹 Scoop old logs before starting new session
    scoop_the_poop(log_dir)
    
    session_id = int(time.time())
    
    # 1. Machine Tape (JSONL)
    tape_path = log_dir / f"cascade_tape_{session_id}.jsonl"
    tape_file = open(tape_path, "a", encoding="utf-8")
    
    # 2. Human Log (Markdown)
    human_path = log_dir / f"cascade_log_{session_id}.md"
    human_file = open(human_path, "a", encoding="utf-8")
    
    # Header for Human Log
    human_file.write(f"# CASCADE MISSION LOG // SESSION {session_id}\n")
    human_file.write(f"**Target:** `{args.cmd}`\n")
    human_file.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    human_file.write("---\n\n")
    human_file.flush()
    
    print("="*60)
    print("CASCADE // OBSERVER")
    print(f"Target:  {args.cmd}")
    print(f"Tape:    {tape_path.absolute()}")
    print(f"Log:     {human_path.absolute()}")
    print("="*60)

    # Init Monitor
    monitor = Monitor("symbiont_alpha")

    def write_human_entry(evt):
        """Convert an event into an articulate log entry."""
        t_str = time.strftime('%H:%M:%S', time.localtime(evt.timestamp))
        
        # Narrative construction based on event type
        if evt.event_type == "error":
            icon = "🔴"
            narrative = f"CRITICAL FAILURE in **{evt.component}**."
        elif evt.event_type == "warning":
            icon = "⚠️"
            narrative = f"Warning signal detected from **{evt.component}**."
        elif evt.event_type == "state_change":
            icon = "🔄"
            narrative = f"State transition observed in **{evt.component}**."
        elif "loss" in str(evt.data):
             icon = "📉"
             narrative = f"Optimization step completed by **{evt.component}**."
        else:
            icon = "ℹ️"
            narrative = f"Standard event recorded from **{evt.component}**."
            
        # Write readable block
        human_file.write(f"### {icon} {t_str} // {evt.event_type.upper()}\n")
        human_file.write(f"{narrative}\n")
        if evt.data:
            # Format data as a clean list or quote
            human_file.write("```yaml\n")
            for k, v in evt.data.items():
                human_file.write(f"{k}: {v}\n")
            human_file.write("```\n")
        human_file.write("\n")
        human_file.flush()

    # Launch Target
    try:
        # Split command for subprocess if it's a string
        cmd_parts = shlex.split(args.cmd)
        
        process = subprocess.Popen(
            cmd_parts,
            cwd=args.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        print(f"[CASCADE] Linked to target. Recording to tape & log...")
        
        for line in process.stdout:
            line = line.strip()
            if not line: continue
            
            # Feed Adapter
            event = monitor.observe(line)
            
            # Build payload with FULL wealth: metrics + triage + raw
            metrics_summary = monitor.metrics.summary()
            triage_status = monitor.metrics.triage()
            
            payload = {
                "event": {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp,
                    "component": event.component,
                    "event_type": event.event_type,
                    "data": event.data,
                    "raw": line,  # Include original line for drill-down
                },
                "metrics": metrics_summary,
                "triage": triage_status,
            }
            
            # Emit to queue for external consumers
            event_queue.put(payload)
            
            # Write to Tape (Machine)
            tape_file.write(json.dumps(payload) + "\n")
            tape_file.flush()
            
            # Write to Log (Human)
            write_human_entry(event)
            
            # Echo to console (unless quiet)
            if not args.quiet:
                print(f"[RAW] {line}")
            
    except KeyboardInterrupt:
        print("\n[CASCADE] Detaching...")
    except Exception as e:
        print(f"[CASCADE] Error: {e}")
    finally:
        tape_file.close()
        human_file.close()
        if 'process' in locals() and process.poll() is None:
            process.terminate()
        print(f"[CASCADE] Session complete. Tape: {tape_path}")

if __name__ == "__main__":
    main()
