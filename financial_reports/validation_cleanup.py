"""Audit-safe cleanup helpers for controlled IFRS 18 validation entries."""

import frappe


VALIDATION_REMARK = "IFRS18-VALIDATION%"


def cancel_validation_transactions():
	"""Cancel submitted validation journals while retaining linked tax audit records."""
	names = frappe.get_all(
		"Journal Entry",
		filters={"user_remark": ["like", VALIDATION_REMARK], "docstatus": 1},
		pluck="name",
		order_by="posting_date desc, creation desc",
	)
	for name in names:
		frappe.get_doc("Journal Entry", name).cancel()

	return {
		"cancelled": len(names),
		"submitted_remaining": frappe.db.count(
			"Journal Entry", {"user_remark": ["like", VALIDATION_REMARK], "docstatus": 1}
		),
		"cancelled_retained": frappe.db.count(
			"Journal Entry", {"user_remark": ["like", VALIDATION_REMARK], "docstatus": 2}
		),
	}
