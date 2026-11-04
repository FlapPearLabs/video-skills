#!/usr/bin/env python3
"""Thin guarded runner for *documented* NodeTool CLI operations.

This wrapper does NOT invoke/edit native MCP timelines; the agent must inspect the
installed version's MCP tools and schemas at runtime for edit_timeline/apply_take.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def command(argv, timeout=60):
    binary = os.environ.get("NODETOOL_BIN", "nodetool")
    if not shutil.which(binary):
        raise RuntimeError("nodetool binary missing; install/setup NodeTool, then verify `nodetool timeline --help`")
    r = subprocess.run([binary, *argv], capture_output=True, text=True, timeout=timeout, check=False)
    return {"argv": [binary, *argv], "exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr}


def main():
    p = argparse.ArgumentParser(description="Guarded NodeTool CLI (timeline operations only)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe")
    val = sub.add_parser("validate")
    val.add_argument("timeline", help="real saved timeline ID OR exported native JSON path")
    snap = sub.add_parser("snapshot")
    snap.add_argument("timeline_id")
    snap.add_argument("--name", default="change-impact-before")
    rest = sub.add_parser("rollback")
    rest.add_argument("timeline_id")
    rest.add_argument("version", help="known snapshot/version ID from NodeTool (not local hash)")
    rest.add_argument("--confirmed-timeline-id", required=True, help="must equal timeline_id")
    args = p.parse_args()
    try:
        if args.cmd == "probe":
            result = command(["timeline", "--help"])
        elif args.cmd == "validate":
            result = command(["timeline", "validate", args.timeline, "--json", "--warnings-as-errors"])
        else:
            if os.environ.get("NODETOOL_ALLOW_MUTATION") != "yes":
                raise RuntimeError("mutation disabled; set NODETOOL_ALLOW_MUTATION=yes after verifying real timeline ID, rights and snapshot policy")
            if not args.timeline_id or args.timeline_id in ("example", "DEMO_30S"):
                raise RuntimeError("refusing example or missing timeline ID")
            if args.cmd == "snapshot":
                result = command(["timeline", "versions", "create", args.timeline_id, "--name", args.name, "--json"])
            else:
                if args.confirmed_timeline_id != args.timeline_id:
                    raise RuntimeError("timeline id verification mismatch")
                result = command(["timeline", "versions", "restore", args.timeline_id, args.version, "--json"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["exit_code"] == 0 else 2
    except (subprocess.TimeoutExpired, RuntimeError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
