"""Read-only status for the installation and new-account mapping lifecycle."""

import frappe

from financial_reports.validation import _run


def get_mapping_status():
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company")
	result, xlsx_bytes, print_html_bytes = _run(
		"IFRS 18 Mapping Audit", {"company": company, "exceptions_only": 1}
	)
	return {
		"company": company,
		"accounts": frappe.db.count("Account", {"company": company}),
		"unmapped": frappe.db.count(
			"Account", {"company": company, "custom_ifrs18_category": ["in", (None, "")]}
		),
		"new_accounts_awaiting_confirmation": frappe.db.count(
			"Account", {"company": company, "disabled": 0, "custom_ifrs18_mapping_review_required": 1}
		),
		"audit_exception_rows": len(result.get("result") or []),
		"audit_xlsx_bytes": xlsx_bytes,
		"audit_print_html_bytes": print_html_bytes,
	}
