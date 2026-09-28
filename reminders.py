"""Find overdue invoices in a CSV export and draft (or send) polite reminders.

Usage:
    python reminders.py invoices.csv                 # dry run: prints what it would send
    python reminders.py invoices.csv --send          # sends via SMTP (settings from env)
    python reminders.py invoices.csv --today 2026-10-01 --min-days 7

CSV columns (header names are case-insensitive):
    invoice, client, email, amount, currency, due_date (YYYY-MM-DD), status
Rows with status "paid" or "void" are ignored.
"""

import argparse
import csv
import os
import smtplib
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage

REQUIRED = {"invoice", "client", "email", "amount", "currency", "due_date", "status"}
CLOSED = {"paid", "void", "cancelled"}

TIERS = [  # (minimum days overdue, tone)
    (30, "final"),
    (14, "second"),
    (1, "first"),
]


@dataclass
class Overdue:
    invoice: str
    client: str
    email: str
    amount: Decimal
    currency: str
    due: date
    days: int

    @property
    def tier(self) -> str:
        return next(tone for minimum, tone in TIERS if self.days >= minimum)


class InputError(Exception):
    pass


def load(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        headers = {h.strip().lower() for h in (reader.fieldnames or [])}
        missing = REQUIRED - headers
        if missing:
            raise InputError(f"missing columns: {', '.join(sorted(missing))}")
        return [{k.strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]


def find_overdue(rows: list[dict], today: date, min_days: int = 1) -> tuple[list[Overdue], list[str]]:
    """Return overdue invoices (oldest first) and human-readable problems for bad rows."""
    found, problems = [], []
    for n, row in enumerate(rows, start=2):  # line 1 is the header
        if row["status"].lower() in CLOSED:
            continue
        try:
            due = date.fromisoformat(row["due_date"])
            amount = Decimal(row["amount"].replace(",", ""))
        except (ValueError, InvalidOperation):
            problems.append(f"line {n}: bad due_date or amount ({row['due_date']!r}, {row['amount']!r})")
            continue
        if "@" not in row["email"]:
            problems.append(f"line {n}: invoice {row['invoice']} has no valid email")
            continue
        days = (today - due).days
        if days >= min_days and amount > 0:
            found.append(Overdue(row["invoice"], row["client"], row["email"], amount,
                                 row["currency"].upper(), due, days))
    found.sort(key=lambda o: o.days, reverse=True)
    return found, problems


def draft(o: Overdue, sender: str) -> EmailMessage:
    opening = {
        "first": "This is a friendly reminder that the invoice below is now past due.",
        "second": "We haven't received payment for the invoice below yet.",
        "final": "This invoice is now more than 30 days overdue. Please arrange payment or contact us this week.",
    }[o.tier]
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = o.email
    msg["Subject"] = f"Invoice {o.invoice}: {o.amount:,.2f} {o.currency} past due"
    msg.set_content(
        f"Hi {o.client},\n\n{opening}\n\n"
        f"Invoice: {o.invoice}\nAmount: {o.amount:,.2f} {o.currency}\n"
        f"Due date: {o.due.isoformat()} ({o.days} days ago)\n\n"
        "If you've already paid, thank you and please ignore this message.\n"
    )
    return msg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv")
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    ap.add_argument("--min-days", type=int, default=1)
    ap.add_argument("--send", action="store_true", help="actually send (default is a dry run)")
    args = ap.parse_args(argv)

    try:
        rows = load(args.csv)
    except (OSError, InputError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    overdue, problems = find_overdue(rows, args.today, args.min_days)
    for p in problems:
        print(f"skipped {p}", file=sys.stderr)

    sender = os.environ.get("REMINDER_FROM", "billing@example.com")
    messages = [draft(o, sender) for o in overdue]
    total = sum(o.amount for o in overdue)
    print(f"{len(overdue)} overdue invoice(s), {total:,.2f} outstanding; {len(problems)} row(s) skipped")

    if not args.send:
        for o, m in zip(overdue, messages):
            print(f"  [dry run] {o.tier:6} {o.days:>3}d  {m['To']:<28} {m['Subject']}")
        return 0

    host = os.environ.get("SMTP_HOST")
    if not host:
        print("error: set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD to send", file=sys.stderr)
        return 2
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        for m in messages:
            smtp.send_message(m)
    print(f"sent {len(messages)} reminder(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
