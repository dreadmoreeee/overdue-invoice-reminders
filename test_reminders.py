from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import reminders

SAMPLE = Path(__file__).with_name("sample_invoices.csv")
TODAY = date(2026, 10, 1)


def test_sample_finds_expected_overdue_invoices():
    overdue, problems = reminders.find_overdue(reminders.load(SAMPLE), TODAY)
    assert [o.invoice for o in overdue] == ["INV-1001", "INV-1002", "INV-1003"]  # oldest first
    assert sum(o.amount for o in overdue) == Decimal("1820.50")
    assert len(problems) == 2  # missing email, bad amount


def test_tiers_by_days_overdue():
    overdue, _ = reminders.find_overdue(reminders.load(SAMPLE), TODAY)
    assert {o.invoice: o.tier for o in overdue} == {
        "INV-1001": "final",   # 47 days
        "INV-1002": "second",  # 21 days
        "INV-1003": "first",   # 6 days
    }


def test_paid_and_future_invoices_are_ignored():
    overdue, _ = reminders.find_overdue(reminders.load(SAMPLE), TODAY)
    ids = {o.invoice for o in overdue}
    assert "INV-1004" not in ids and "INV-1006" not in ids


def test_min_days_filter():
    overdue, _ = reminders.find_overdue(reminders.load(SAMPLE), TODAY, min_days=14)
    assert [o.invoice for o in overdue] == ["INV-1001", "INV-1002"]


def test_problems_point_to_the_csv_line():
    _, problems = reminders.find_overdue(reminders.load(SAMPLE), TODAY)
    assert any(p.startswith("line 6:") and "INV-1005" in p for p in problems)
    assert any(p.startswith("line 8:") for p in problems)


def test_email_content():
    o = reminders.Overdue("INV-9", "Ana", "ana@x.example", Decimal("1234.5"), "CAD", date(2026, 9, 1), 30)
    msg = reminders.draft(o, "billing@me.example")
    assert msg["Subject"] == "Invoice INV-9: 1,234.50 CAD past due"
    body = msg.get_content()
    assert "more than 30 days overdue" in body and "If you've already paid" in body


def test_missing_columns_rejected(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("invoice,client\nA,B\n", encoding="utf-8")
    with pytest.raises(reminders.InputError, match="missing columns"):
        reminders.load(bad)


def test_dry_run_never_sends(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("SMTP must not be used in a dry run")
    monkeypatch.setattr(reminders.smtplib, "SMTP", boom)
    assert reminders.main([str(SAMPLE), "--today", "2026-10-01"]) == 0
    out = capsys.readouterr().out
    assert "3 overdue invoice(s), 1,820.50 outstanding; 2 row(s) skipped" in out
    assert out.count("[dry run]") == 3


def test_send_requires_smtp_settings(monkeypatch, capsys):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert reminders.main([str(SAMPLE), "--today", "2026-10-01", "--send"]) == 2
