"""
Cascade Tape Utilities - JSONL event storage and playback.

This module provides utilities for working with tape files:
- load_tape_file: Load events from a JSONL tape file
- find_latest_tape: Find the most recent tape file in a directory
- list_tape_files: List all available tape files
- write_tape_event: Write an event to a tape file
- create_tape_path: Generate a timestamped tape file path
- PlaybackBuffer: Buffer for playback with timing control

For visualization, use your preferred tools to consume the tape files
or connect to the event_queue in observe.py/listen.py.
"""

from cascade.viz.tape import (
    load_tape_file,
    find_latest_tape,
    list_tape_files,
    write_tape_event,
    create_tape_path,
    PlaybackBuffer,
)

__all__ = [
    "load_tape_file",
    "find_latest_tape",
    "list_tape_files",
    "write_tape_event",
    "create_tape_path",
    "PlaybackBuffer",
]
