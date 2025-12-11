#!/usr/bin/env python3
"""
SYSTEM STATUS HOOK - Runs on SessionStart
Checks system health by looking at activity indicators (file timestamps, heartbeats)
Since we can't reliably detect which Python script is running, we check their outputs
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# Activity indicators for each system
DAEMON_HEARTBEAT = Path(r"C:\Users\wetwi\OneDrive\AI\.claude\daemon_heartbeat.log")
DAEMON_OUTBOX = Path(r"C:\Users\wetwi\OneDrive\AI\.claude\outbox")
BRAINAI_VAULT = Path.home() / ".ai_brain_chat" / "memory_vault"

# Thresholds (in minutes)
MAX_HEARTBEAT_AGE = 30  # Daemon heartbeats every 15 min
MAX_BRAINAI_ACTIVITY = 60  # BRAINAI should show activity within an hour if being used

def check_file_age(file_path, max_age_minutes):
    """Check if file was modified within threshold"""
    if not file_path.exists():
        return None, "NOT FOUND"

    try:
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        age_minutes = (datetime.now() - mtime).total_seconds() / 60

        if age_minutes > max_age_minutes:
            return age_minutes, "STALE"
        return age_minutes, "OK"
    except Exception as e:
        return None, f"ERROR: {e}"

def check_daemon():
    """Check if daemon is active via heartbeat"""
    age, status = check_file_age(DAEMON_HEARTBEAT, MAX_HEARTBEAT_AGE)
    if age is not None:
        return f"{status} ({int(age)} min ago)"
    return status

def check_brainai():
    """Check if BRAINAI vault shows recent activity (only matters if you're using it)"""
    if not BRAINAI_VAULT.exists():
        return "VAULT NOT FOUND - May need to run BRAINAI once"

    # Check any file in the vault for recent activity
    try:
        latest_mtime = None
        for f in BRAINAI_VAULT.rglob("*"):
            if f.is_file():
                mtime = f.stat().st_mtime
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime

        if latest_mtime:
            age_minutes = (datetime.now() - datetime.fromtimestamp(latest_mtime)).total_seconds() / 60
            if age_minutes > MAX_BRAINAI_ACTIVITY:
                return f"No recent activity ({int(age_minutes)} min ago)"
            return f"Active ({int(age_minutes)} min ago)"
        return "No activity files found"
    except Exception as e:
        return f"ERROR: {e}"

def main():
    print("=" * 60)
    print("SYSTEM STATUS CHECK")
    print("=" * 60)

    warnings = []

    # Check daemon
    daemon_status = check_daemon()
    print(f"  Claude Daemon: {daemon_status}")
    if "STALE" in daemon_status or "NOT FOUND" in daemon_status or "ERROR" in daemon_status:
        warnings.append("Claude Daemon - " + daemon_status)

    # Check BRAINAI (informational only - it's a GUI you run manually)
    brainai_status = check_brainai()
    print(f"  BRAINAI Vault: {brainai_status}")

    # Show warnings
    if warnings:
        print()
        print("WARNINGS:")
        for w in warnings:
            print(f"  ! {w}")
        print()
        print("START COMMANDS:")
        print("  Daemon: py -3.12 \"C:\\Users\\wetwi\\OneDrive\\AI\\.claude\\claude_daemon.py\"")
        print("  BRAINAI: py -3.12 \"C:\\Users\\wetwi\\OneDrive\\AI\\BRAINAI\\BRAINAI.py\"")
    else:
        print()
        print("Systems OK.")

    print("=" * 60)

    sys.exit(0)

if __name__ == "__main__":
    main()
