# INBOX

This folder is for **unprocessed notes**.

## How It Works

1. Daemons/workers dump notes here
2. On startup, Claude checks for new files
3. Claude processes them into proper vault notes
4. Processed files get deleted or moved

## Why?

Workers don't know vault structure. They just dump files here.
Claude (the main instance) organizes them properly.

## Processing Notes

When you find a note here:
1. Read it
2. Decide where it belongs (Knowledge? Session Notes? Projects?)
3. Create/update the proper note with [[links]]
4. Delete the inbox file

---

*If this folder is empty, nothing to process.*
