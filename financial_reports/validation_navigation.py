"""Read-only validation of Accounting navigation and Account-field UX."""

import json

import frappe


def get_status():
	accounting = frappe.get_doc("Workspace", "Accounting")
	content = json.loads(accounting.content or "[]")
	labels = [row.label for row in accounting.links]
	field_order = [
		field.fieldname for field in frappe.get_meta("Account").fields
		if field.fieldname.startswith("custom_ifrs18_")
	]
	return {
		"legacy_workspace_exists": bool(frappe.db.exists("Workspace", "IFRS 18 Financial Reporting")),
		"accounting_card_count": sum(block.get("id") == "financial_reports_accounting_card" for block in content),
		"accounting_financial_reports_sections": labels.count("Financial Reports"),
		"accounting_managed_links": sum(label in labels for label in (
			"Profit and Loss Statement", "Balance Sheet", "Cash Flow",
			"Statement of Comprehensive Income", "Statement of Changes in Equity",
			"Notes Schedule", "Financial Ratios", "Working Capital Analysis",
			"Budget Variance", "Cost Center Profitability",
			"Management Performance Measures", "Mapping Audit",
			"Reporting Settings", "Management Performance Measure Definitions",
		)),
		"account_ifrs18_field_order": field_order,
	}
