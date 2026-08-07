"""Installation, migration and safe restoration of ERPNext report links."""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from financial_reports.mapping import ALL_CATEGORIES, CASH_FLOW_ACTIVITIES, map_all_accounts


REPLACED_REPORTS = ("Profit and Loss Statement", "Balance Sheet", "Cash Flow")
LEGACY_WORKSPACE = "IFRS 18 Financial Reporting"
ACCOUNTING_CARD_ID = "financial_reports_accounting_card"
ACCOUNTING_LINKS = (
	("Profit and Loss Statement", "Profit and Loss Statement", "Report", 1),
	("Balance Sheet", "Balance Sheet", "Report", 1),
	("Cash Flow", "Cash Flow", "Report", 1),
	("Statement of Comprehensive Income", "IFRS 18 Statement of Comprehensive Income", "Report", 1),
	("Statement of Changes in Equity", "IFRS 18 Statement of Changes in Equity", "Report", 1),
	("Notes Schedule", "IFRS 18 Notes Schedule", "Report", 1),
	("Financial Ratios", "IFRS 18 Financial Ratios", "Report", 1),
	("Working Capital Analysis", "IFRS 18 Working Capital Analysis", "Report", 1),
	("Budget Variance", "IFRS 18 Budget Variance", "Report", 1),
	("Cost Center Profitability", "IFRS 18 Cost Center Profitability", "Report", 1),
	("Management Performance Measures", "IFRS 18 Management Performance Measures", "Report", 1),
	("Mapping Audit", "IFRS 18 Mapping Audit", "Report", 1),
	("Reporting Settings", "IFRS 18 Reporting Settings", "DocType", 0),
	("Management Performance Measure Definitions", "IFRS 18 Management Performance Measure", "DocType", 0),
)


def get_custom_fields():
	return {
		"Account": [
			{"fieldname": "custom_ifrs18_mapping_section", "label": "IFRS 18 Mapping", "fieldtype": "Section Break", "insert_after": "include_in_gross"},
			{"fieldname": "custom_ifrs18_category", "label": "IFRS 18 Category", "fieldtype": "Select", "options": "\n" + "\n".join(ALL_CATEGORIES), "insert_after": "custom_ifrs18_mapping_section", "in_list_view": 1},
			{"fieldname": "custom_ifrs18_line_item", "label": "Statement Line Item", "fieldtype": "Data", "insert_after": "custom_ifrs18_category"},
			{"fieldname": "custom_ifrs18_expense_nature", "label": "Expense by Nature", "fieldtype": "Data", "insert_after": "custom_ifrs18_line_item", "depends_on": "eval:doc.root_type=='Expense'"},
			{"fieldname": "custom_ifrs18_mapping_column", "fieldtype": "Column Break", "insert_after": "custom_ifrs18_expense_nature"},
			{"fieldname": "custom_ifrs18_cash_flow_activity", "label": "Cash Flow Activity", "fieldtype": "Select", "options": "\n" + "\n".join(CASH_FLOW_ACTIVITIES), "insert_after": "custom_ifrs18_mapping_column"},
			{"fieldname": "custom_ifrs18_note_reference", "label": "Note / Disclosure Group", "fieldtype": "Data", "insert_after": "custom_ifrs18_cash_flow_activity"},
			{"fieldname": "custom_ifrs18_governance_section", "label": "Mapping Review", "fieldtype": "Section Break", "insert_after": "custom_ifrs18_note_reference", "collapsible": 1},
			{"fieldname": "custom_ifrs18_mapping_source", "label": "Mapping Source", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_ifrs18_governance_section"},
			{"fieldname": "custom_ifrs18_mapping_confidence", "label": "Mapping Confidence", "fieldtype": "Select", "options": "Rule based\nFallback\nManually reviewed", "read_only": 1, "insert_after": "custom_ifrs18_mapping_source"},
			{"fieldname": "custom_ifrs18_governance_column", "fieldtype": "Column Break", "insert_after": "custom_ifrs18_mapping_confidence"},
			{"fieldname": "custom_ifrs18_mapping_review_required", "label": "Mapping Review Required", "fieldtype": "Check", "default": "0", "read_only": 1, "insert_after": "custom_ifrs18_governance_column", "description": "Enabled for a new account until its suggested mapping is confirmed."},
			{"fieldname": "custom_ifrs18_mapping_locked", "label": "Confirm and Lock Mapping", "fieldtype": "Check", "default": "0", "insert_after": "custom_ifrs18_mapping_review_required", "description": "Confirms entity review and prevents automatic remapping."},
		]
	}

def ensure_custom_fields():
	create_custom_fields(get_custom_fields(), update=True)
	frappe.clear_cache(doctype="Account")


def remove_custom_fields():
	"""Remove only the Account fields owned by this app during uninstall."""
	for field in get_custom_fields()["Account"]:
		name = f"Account-{field['fieldname']}"
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
	frappe.clear_cache(doctype="Account")


def remove_legacy_workspace():
	if frappe.db.exists("Workspace", LEGACY_WORKSPACE):
		frappe.delete_doc("Workspace", LEGACY_WORKSPACE, ignore_permissions=True, force=True)


def _without_financial_reports_section(rows):
	"""Remove only links belonging to this app's Accounting card section."""
	result = []
	skipping = False
	for row in rows:
		if row.type == "Card Break":
			skipping = row.label == "Financial Reports"
			if skipping:
				continue
		if not skipping:
			result.append(row)
	return result


def integrate_accounting_workspace():
	if not frappe.db.exists("Workspace", "Accounting"):
		return
	doc = frappe.get_doc("Workspace", "Accounting")
	content = json.loads(doc.content or "[]")
	if not any(block.get("id") == ACCOUNTING_CARD_ID for block in content):
		content.append({
			"id": ACCOUNTING_CARD_ID,
			"type": "card",
			"data": {"card_name": "Financial Reports", "col": 4},
		})
	doc.content = json.dumps(content, separators=(",", ":"))

	doc.set("links", _without_financial_reports_section(doc.links))
	doc.append("links", {"type": "Card Break", "label": "Financial Reports", "hidden": 0, "onboard": 0})
	for label, link_to, link_type, is_query_report in ACCOUNTING_LINKS:
		doc.append("links", {
			"type": "Link", "label": label, "link_to": link_to, "link_type": link_type,
			"is_query_report": is_query_report, "hidden": 0, "onboard": 0,
		})
	doc.flags.ignore_validate = True
	doc.save(ignore_permissions=True)


def remove_accounting_workspace_section():
	if not frappe.db.exists("Workspace", "Accounting"):
		return
	doc = frappe.get_doc("Workspace", "Accounting")
	content = [block for block in json.loads(doc.content or "[]") if block.get("id") != ACCOUNTING_CARD_ID]
	doc.content = json.dumps(content, separators=(",", ":"))
	doc.set("links", _without_financial_reports_section(doc.links))
	doc.flags.ignore_validate = True
	doc.save(ignore_permissions=True)

def replace_standard_reports():
	for report_name in REPLACED_REPORTS:
		if frappe.db.exists("Report", report_name):
			frappe.db.set_value(
				"Report", report_name,
				{"module": "Financial Reports", "report_type": "Script Report", "is_standard": "Yes", "disabled": 0},
				update_modified=False,
			)


def restore_standard_reports():
	for report_name in REPLACED_REPORTS:
		if frappe.db.exists("Report", report_name):
			frappe.db.set_value("Report", report_name, "module", "Accounts", update_modified=False)


def after_install():
	ensure_custom_fields()
	map_all_accounts()
	replace_standard_reports()
	remove_legacy_workspace()
	integrate_accounting_workspace()
	frappe.db.commit()


def after_migrate():
	ensure_custom_fields()
	map_all_accounts()
	replace_standard_reports()
	remove_legacy_workspace()
	integrate_accounting_workspace()
	frappe.clear_cache()


def before_uninstall():
	restore_standard_reports()
	remove_accounting_workspace_section()
	remove_legacy_workspace()
	remove_custom_fields()
	frappe.db.commit()

