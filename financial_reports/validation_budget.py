"""Smoke validation for the IFRS 18 budget-variance report."""

import frappe

from financial_reports.validation import _run


def validate_budget_report():
	if frappe.local.site != "test.local":
		frappe.throw("Budget validation is restricted to test.local")
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company")
	fiscal_year = frappe.db.get_value("Fiscal Year", {"year_start_date": ["<=", "2026-03-07"], "year_end_date": [">=", "2026-04-05"]})
	filters = {
		"company": company,
		"fiscal_year": fiscal_year,
		"from_date": "2026-03-07",
		"to_date": "2026-04-05",
		"comparison_enabled": 1,
		"comparison_from_date": "2026-01-06",
		"comparison_to_date": "2026-02-04",
	}
	result, xlsx_bytes, print_html_bytes = _run("IFRS 18 Budget Variance", filters)
	return {
		"rows": len(result.get("result") or []),
		"columns": len(result.get("columns") or []),
		"xlsx_bytes": xlsx_bytes,
		"print_html_bytes": print_html_bytes,
	}
