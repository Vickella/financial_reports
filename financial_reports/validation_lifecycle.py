"""One-command controlled validation with audit-safe cancellation."""

from financial_reports.validation import run_full_validation


def run_and_cancel():
	return run_full_validation(keep_transactions=0)
