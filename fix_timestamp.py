#!/usr/bin/env python3
import argparse
import re
from datetime import timedelta
from pathlib import Path
import sys

# Match a WebVTT cue timing line, preserving any trailing settings (e.g., "align:start line:0")
TIME_RE = re.compile(
    r'^(\s*)(?P<start>(?:\d{2}:)?\d{2}:\d{2}\.\d{3})\s*-->\s*(?P<end>(?:\d{2}:)?\d{2}:\d{2}\.\d{3})(?P<rest>.*)$'
)

def parse_hhmmss_mmm(s: str) -> timedelta:
    """
    Parse 'HH:MM:SS.mmm' or 'MM:SS.mmm' into timedelta.
    """
    try:
        hms, ms = s.split(".")
        parts = hms.split(":")
        if len(parts) == 3:
            hh, mm, ss = map(int, parts)
        elif len(parts) == 2:
            hh = 0
            mm, ss = map(int, parts)
        else:
            raise ValueError
        millis = int(ms)
        return timedelta(hours=hh, minutes=mm, seconds=ss, milliseconds=millis)
    except Exception as e:
        raise ValueError(f"Invalid time format '{s}'. Expected HH:MM:SS.mmm or MM:SS.mmm") from e

def format_hhmmss_mmm(td: timedelta) -> str:
    """
    Format timedelta as 'HH:MM:SS.mmm' (hours zero-padded to 2; hours may exceed 23).
    """
    total_ms = int(round(td.total_seconds() * 1000))
    if total_ms < 0:
        total_ms = 0
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60  # allow >24h
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"

def compute_shift(args) -> timedelta:
    if args.seconds is not None:
        shift = timedelta(seconds=args.seconds)
    elif args.offset is not None:
        shift = parse_hhmmss_mmm(args.offset)
    else:
        # default 22 minutes 58 seconds
        shift = timedelta(minutes=22, seconds=58)
    return -shift if args.subtract else shift

def shift_line(line: str, shift: timedelta) -> str:
    m = TIME_RE.match(line)
    if not m:
        return line
    start_td = parse_hhmmss_mmm(m.group("start"))
    end_td = parse_hhmmss_mmm(m.group("end"))

    new_start = start_td + shift
    new_end = end_td + shift

    # Clamp negatives to zero
    if new_start.total_seconds() < 0:
        new_start = timedelta(0)
    if new_end.total_seconds() < 0:
        new_end = timedelta(0)

    return (
        f"{m.group(1)}{format_hhmmss_mmm(new_start)} --> "
        f"{format_hhmmss_mmm(new_end)}{m.group('rest')}\n"
    )

def main():
    p = argparse.ArgumentParser(
        description="Shift timestamps in a WebVTT (.vtt) file."
    )
    p.add_argument("input", help="Path to input .vtt file")
    p.add_argument(
        "-o", "--output",
        help="Path to output .vtt file (default: <input>_shifted.vtt)"
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "-t", "--offset",
        help="Time offset as HH:MM:SS.mmm (or MM:SS.mmm). Default: 00:22:58.000"
    )
    g.add_argument(
        "-s", "--seconds", type=float,
        help="Time offset in seconds (can be fractional)."
    )
    p.add_argument(
        "--subtract", action="store_true",
        help="Shift backward instead of forward."
    )

    args = p.parse_args()
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Error: input file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output) if args.output else in_path.with_name(in_path.stem + "_shifted.vtt")

    try:
        shift = compute_shift(args)
    except ValueError as e:
        print(f"Error parsing offset: {e}", file=sys.stderr)
        sys.exit(2)

    with in_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = [shift_line(line, shift) for line in lines]

    with out_path.open("w", encoding="utf-8") as f:
        f.writelines(new_lines)

    direction = "backward" if args.subtract else "forward"
    print(f"Shifted '{in_path.name}' {direction} by {format_hhmmss_mmm(abs(shift))} → '{out_path.name}'")

if __name__ == "__main__":
    main()
