#!/usr/bin/env python3
"""
BACKUP PROTECTION HOOK
Blocks EDITING existing numbered backup files.
Allows CREATING new backup files (Write to non-existing file is OK).
Pattern: *-NNNN.ext (4+ digits before extension)

Exit code 2 = BLOCK the operation
Exit code 0 = Allow the operation
"""
import json
import sys
import re
import os

def is_backup_file(file_path):
    """Check if file matches backup pattern like index-0055.html or sessionbot-0109.py"""
    filename = os.path.basename(file_path)
    # Pattern: anything-NNNN.extension where NNNN is 4+ digits
    return bool(re.search(r'-\d{4,}\.\w+$', filename))

try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    # If we can't parse input, allow the operation
    sys.exit(0)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
file_path = tool_input.get("file_path", "")

# Edit tool = always modifying existing file, block if backup
if tool_name == "Edit" and is_backup_file(file_path):
    filename = os.path.basename(file_path)
    error_msg = f"""
BLOCKED: Cannot EDIT backup file '{filename}'

This file matches the numbered backup pattern (*-NNNN.ext).
Backup files are READ-ONLY snapshots - never edit them.

CORRECT WORKFLOW:
1. Edit the ORIGINAL file only (not the numbered backup)
2. Backups preserve the pre-edit state

You were trying to edit a backup. Edit the original file instead.
"""
    print(error_msg, file=sys.stderr)
    sys.exit(2)  # Exit code 2 = blocking error

# Write tool = block only if backup file ALREADY EXISTS (overwriting)
if tool_name == "Write" and is_backup_file(file_path) and os.path.exists(file_path):
    filename = os.path.basename(file_path)
    error_msg = f"""
BLOCKED: Cannot OVERWRITE existing backup '{filename}'

This backup file already exists. Overwriting would cause data loss.

CORRECT WORKFLOW:
1. GLOB FIRST to find highest backup number
2. Create NEW backup at highest + 1
3. Never overwrite existing backups

Use the next available number instead.
"""
    print(error_msg, file=sys.stderr)
    sys.exit(2)  # Exit code 2 = blocking error

# Allow the operation
sys.exit(0)
