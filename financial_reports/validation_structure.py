"""Read-only checks for the PDF-derived primary-statement hierarchy."""

import json

import frappe
from frappe.desk.query_report import run
from frappe.utils import flt


def _run(name, accumulated=0):
	filters = {
		"company": frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company"),
		"filter_based_on": "Date Range", "period_start_date": "2026-01-01",
		"period_end_date": "2026-12-31", "periodicity": "Yearly",
		"accumulated_values": accumulated, "include_default_book_entries": 1,
		"show_zero_values": 1, "comparison_enabled": 1,
		"comparison_from_date": "2025-01-01", "comparison_to_date": "2025-12-31",
	}
	return run(name, filters=json.dumps(filters), ignore_prepared_report=True, are_default_filters=False)


def _labels(result):
	return [str(row.get("account_name") or row.get("section") or "").strip("'") for row in result.get("result") or []]


def _assert_order(labels, required):
	positions = []
	for label in required:
		if label not in labels:
			raise AssertionError(f"Required statement row is missing: {label}")
		positions.append(labels.index(label))
	if positions != sorted(positions):
		raise AssertionError(f"Statement rows are out of reference order: {dict(zip(required, positions))}")


def validate_primary_statement_structure():
	pnl = _run("Profit and Loss Statement")
	position = _run("Balance Sheet", accumulated=1)
	for result in (pnl, position):
		if any(column.get("fieldname") == "note_reference" for column in result.get("columns") or []):
			raise AssertionError("Primary statements must not display a Notes column")

	pnl_required = [
		"Continuing operations", "Gross profit", "Operating profit",
		"Profit before financing and income taxes", "Profit before income tax",
		"Profit from continuing operations", "Profit",
	]
	position_required = [
		"Assets", "Non-current assets", "Total non-current assets",
		"Current assets", "Total current assets", "Total assets",
		"Equity and liabilities", "Equity", "Total equity",
		"Non-current liabilities", "Total non-current liabilities",
		"Current liabilities", "Total current liabilities",
		"Total liabilities", "Total equity and liabilities",
	]
	pnl_labels = _labels(pnl)
	position_labels = _labels(position)
	_assert_order(pnl_labels, pnl_required)
	_assert_order(position_labels, position_required)

	rows = {str(row.get("account_name") or "").strip("'"): row for row in position.get("result") or []}
	amount_fields = [column.get("fieldname") for column in position.get("columns") or [] if column.get("fieldtype") == "Currency"]
	for fieldname in amount_fields:
		assets = flt(rows["Total assets"].get(fieldname))
		equity_and_liabilities = flt(rows["Total equity and liabilities"].get(fieldname))
		if abs(assets - equity_and_liabilities) > 0.001:
			raise AssertionError(f"Balance sheet does not balance for {fieldname}: {assets} != {equity_and_liabilities}")
	return {
		"profit_or_loss_rows": len(pnl_labels), "financial_position_rows": len(position_labels),
		"profit_or_loss_hierarchy": pnl_required, "financial_position_hierarchy": position_required,
		"notes_column_removed": True, "balance_equation_fields_checked": amount_fields,
	}
