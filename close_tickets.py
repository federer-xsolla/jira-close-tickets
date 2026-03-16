#!/usr/bin/env python3
"""Bulk-close Jira tickets using acli CLI."""

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

JIRA_URL_PREFIX = "https://xsolla.atlassian.net/browse/"

PREFERRED_STATUSES = [
    "Won't Do",
    "Cancelled",
    "Declined",
    "Rejected",
    "Closed",
    "Done",
    "Complete",
]


@dataclass
class Result:
    key: str
    previous_status: str
    new_status: str
    outcome: str  # "skipped", "transitioned", "failed"


def parse_tickets(path: str) -> list[str]:
    keys = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(JIRA_URL_PREFIX):
                line = line[len(JIRA_URL_PREFIX):]
            # Strip trailing slashes or query params just in case
            line = line.split("?")[0].strip("/")
            keys.append(line)
    return keys


def run_acli(*args: str) -> str:
    proc = subprocess.run(
        ["acli", "jira", "workitem", *args],
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def get_status(key: str) -> tuple[str, str]:
    """Return (status_name, status_category_key) for a ticket."""
    output = run_acli("view", key, "--fields", "status", "--json")
    try:
        data = json.loads(output)
        status = data["fields"]["status"]
        return status["name"], status["statusCategory"]["key"]
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"Failed to parse status for {key}: {output!r}") from e


def add_comment(key: str, comment: str) -> bool:
    output = run_acli("comment", "create", "--key", key, "--body", comment, "--json")
    try:
        data = json.loads(output)
        return data.get("id") is not None
    except json.JSONDecodeError:
        # Non-JSON output likely means success for comment create
        return "error" not in output.lower()


def try_transition(key: str, status: str) -> bool:
    output = run_acli("transition", "--key", key, "--status", status, "--yes", "--json")
    try:
        data = json.loads(output)
        results = data.get("results", [])
        return results and results[0].get("status") == "SUCCESS"
    except json.JSONDecodeError:
        return False


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def process_ticket(key: str, comment: str) -> Result:
    try:
        status_name, category_key = get_status(key)
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        return Result(key, "?", "", "failed")

    if category_key == "done":
        print(f"  Already closed ({status_name}), skipping")
        return Result(key, status_name, status_name, "skipped")

    for target in PREFERRED_STATUSES:
        if try_transition(key, target):
            print(f"  {status_name} -> {target}")
            if add_comment(key, comment):
                print(f"  Comment added")
            else:
                print(f"  WARNING: failed to add comment")
            return Result(key, status_name, target, "transitioned")

    print(f"  FAILED: no valid transition from '{status_name}'")
    return Result(key, status_name, "", "failed")


def main():
    parser = argparse.ArgumentParser(description="Bulk-close Jira tickets via acli")
    parser.add_argument("file", nargs="?", default="tickets.txt", help="File with ticket keys/URLs (default: tickets.txt)")
    args = parser.parse_args()

    config = load_config()
    comment = config["comment"]

    keys = parse_tickets(args.file)
    if not keys:
        print("No tickets found in input file.")
        sys.exit(0)

    print(f"Processing {len(keys)} ticket(s)...\n")

    results: list[Result] = []
    for key in keys:
        print(f"[{key}]")
        results.append(process_ticket(key, comment))

    # Write CSV log
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = log_dir / f"close_log_{timestamp}.csv"

    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ticket", "previous_status", "new_status", "result", "timestamp"])
        for r in results:
            writer.writerow([r.key, r.previous_status, r.new_status, r.outcome, timestamp])

    # Summary
    print(f"\n{'='*60}")
    print(f"{'Ticket':<20} {'Previous':<15} {'New':<15} {'Result'}")
    print(f"{'-'*60}")
    for r in results:
        print(f"{r.key:<20} {r.previous_status:<15} {r.new_status:<15} {r.outcome}")

    skipped = sum(1 for r in results if r.outcome == "skipped")
    transitioned = sum(1 for r in results if r.outcome == "transitioned")
    failed = sum(1 for r in results if r.outcome == "failed")
    print(f"\nTotal: {len(results)} | Transitioned: {transitioned} | Skipped: {skipped} | Failed: {failed}")
    print(f"Log saved to: {log_path}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
