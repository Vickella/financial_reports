"""Read-only interoperability audit for optional tax and exception-monitoring apps."""

import frappe


def get_interoperability_status():
	apps = set(frappe.get_installed_apps())
	rules = []
	if "veritytax" in apps and frappe.db.exists("DocType", "Zimbabwe Tax Rule"):
		fields = ["name", "tax_year", "currency", "effective_from", "effective_to", "rule_status", "legal_reference", "late_payment_interest_rate", "interest_method"]
		fields = [field for field in fields if frappe.get_meta("Zimbabwe Tax Rule").has_field(field) or field == "name"]
		rules = frappe.get_all("Zimbabwe Tax Rule", fields=fields, order_by="tax_year desc, currency asc")

	return {
		"installed_optional_apps": sorted(apps.intersection({"veritytax", "verityguard"})),
		"approved_tax_rules": [row for row in rules if row.get("rule_status") == "Approved"],
		"all_tax_rules": rules,
		"foreign_payment_log_tax_payment_column": (
			frappe.db.has_column("Foreign Payment Log", "tax_payment")
			if frappe.db.exists("DocType", "Foreign Payment Log") else None
		),
		"tagged_journals": {
			"submitted": frappe.db.count("Journal Entry", {"user_remark": ["like", "IFRS18-VALIDATION%"], "docstatus": 1}),
			"cancelled": frappe.db.count("Journal Entry", {"user_remark": ["like", "IFRS18-VALIDATION%"], "docstatus": 2}),
		},
	}
