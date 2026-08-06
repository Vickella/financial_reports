"""Read-only status checks for the controlled validation environment."""

import frappe


def get_status():
	return {
		"tax_payment_column": frappe.db.has_column("Foreign Payment Log", "tax_payment")
		if frappe.db.exists("DocType", "Foreign Payment Log") else None,
		"validation_journal_entries": frappe.db.count(
			"Journal Entry", {"user_remark": ["like", "IFRS18-VALIDATION%"], "docstatus": 1}
		),
		"financial_reports_installed": "financial_reports" in frappe.get_installed_apps(),
		"failed_veritytax_patch_logged": bool(frappe.db.exists(
			"Patch Log", "veritytax.patches.v1_0_1.separate_qpd_and_final_reconciliation"
		)),
	}
