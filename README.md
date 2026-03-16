# Jira Bulk Close Tickets

Bulk-close Jira tickets assigned to deactivated employees. Handles different workflows across projects by dynamically finding the correct closing status for each ticket.

## Prerequisites

- Python 3.10+
- [acli](https://acli.dev) CLI installed and authenticated via OAuth (`~/.config/acli/jira_config.yaml`)

## Usage

```bash
# Using default input file (tickets.txt)
python3 close_tickets.py

# Using a custom input file
python3 close_tickets.py my_tickets.txt
```

## Input file format

One ticket per line. Supports full URLs and plain keys. Blank lines and `#` comments are ignored.

```text
# Sprint 42 cleanup
https://xsolla.atlassian.net/browse/XTRAIN-19938
PROJ-123
WEB-456
```

## How it works

1. Reads the input file and extracts ticket keys
2. For each ticket, checks current status via `acli`
3. Skips tickets that are already in a "done" status category
4. Attempts to transition to a closing status, trying in order:
   - Won't Do
   - Cancelled
   - Declined
   - Rejected
   - Closed
   - Done
   - Complete
5. Stops at the first successful transition per ticket

## Logs

Each run writes a CSV log to `logs/close_log_<timestamp>.csv`:

| ticket | previous_status | new_status | result | timestamp |
|--------|-----------------|------------|--------|-----------|
| PROJ-123 | Open | Won't Do | transitioned | 2026-03-16_14-30-00 |
| WEB-456 | Done | Done | skipped | 2026-03-16_14-30-00 |

## Exit codes

- `0` — all tickets transitioned or skipped
- `1` — one or more tickets failed to transition
