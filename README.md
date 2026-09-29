# overdue-invoice-reminders

A small Python tool for small businesses: point it at an invoices CSV export (from QuickBooks, Wave, a spreadsheet…) and it finds overdue invoices, picks the right tone for each reminder (first, second, final) and either shows you what it would send or sends it by email.

- **Safe by default:** runs as a dry run unless you pass `--send`.
- **Tells you what it skipped and why**, pointing to the exact CSV line (missing email, bad amount or date).
- **No dependencies** beyond the Python standard library. Money is handled with `Decimal`, not floats.

## Measured result

```
$ python reminders.py sample_invoices.csv --today 2026-10-01
skipped line 6: invoice INV-1005 has no valid email
skipped line 8: bad due_date or amount ('2026-09-01', 'not-a-number')
3 overdue invoice(s), 1,820.50 outstanding; 2 row(s) skipped
  [dry run] final   47d  owner@harbourview.example    Invoice INV-1001: 450.00 CAD past due
  [dry run] second  21d  billing@northshore.example   Invoice INV-1002: 1,280.50 CAD past due
  [dry run] first    6d  hello@luma.example           Invoice INV-1003: 90.00 CAD past due

$ python -m pytest -q
.........
9 passed in 0.03s
```

The sample CSV has 7 invoices: 3 overdue, 1 paid, 1 not yet due, 1 without an email and 1 with an invalid amount. The tests check exactly that split, the reminder tier for each invoice, the total outstanding, the email text, the error for missing columns, that a dry run never opens an SMTP connection, and that `--send` refuses to run without SMTP settings.

## Usage

```bash
python reminders.py invoices.csv                      # dry run
python reminders.py invoices.csv --min-days 14        # only 14+ days overdue
set SMTP_HOST=... & set SMTP_USER=... & set SMTP_PASSWORD=... & set REMINDER_FROM=billing@example.com
python reminders.py invoices.csv --send
```

CSV columns: `invoice, client, email, amount, currency, due_date (YYYY-MM-DD), status`. Rows with status `paid`, `void` or `cancelled` are ignored.

Schedule it weekly with Windows Task Scheduler or cron to never chase a late payment by hand again.

## Author

Marvin Palencia, founder of [DeMark Studio](https://demarkstudio.ca), Miramichi, New Brunswick, Canada. I build Python automations and web tools for small businesses. Portfolio: [marvin.demarkstudio.ca](https://marvin.demarkstudio.ca)

MIT License.
