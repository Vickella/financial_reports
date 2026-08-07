"""Installation, migration and safe restoration of ERPNext report links."""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from financial_reports.mapping import ALL_CATEGORIES, CASH_FLOW_ACTIVITIES, map_all_accounts


REPLACED_REPORTS = ("Profit and Loss Statement", "Balance Sheet", "Cash Flow")
LEGACY_WORKSPACE = "IFRS 18 Financial Reporting"
FINANCIAL_REPORTS_WORKSPACE = "Financial Reports"
ACCOUNTING_CARD_ID = "financial_reports_accounting_card"
MANAGEMENT_CARD_ID = "financial_reports_management_card"
CONTROLS_CARD_ID = "financial_reports_controls_card"

NEW_STATEMENT_LINKS = (
	("Statement of Comprehensive Income", "IFRS 18 Statement of Comprehensive Income", "Report", 1),
	("Statement of Changes in Equity", "IFRS 18 Statement of Changes in Equity", "Report", 1),
	("Notes Schedule", "IFRS 18 Notes Schedule", "Report", 1),
)
MANAGEMENT_LINKS = (
	("Financial Ratios", "IFRS 18 Financial Ratios", "Report", 1),
	("Working Capital Analysis", "IFRS 18 Working Capital Analysis", "Report", 1),
	("Budget Variance", "IFRS 18 Budget Variance", "Report", 1),
	("Cost Center Profitability", "IFRS 18 Cost Center Profitability", "Report", 1),
	("Management Performance Measures", "IFRS 18 Management Performance Measures", "Report", 1),
)
CONTROL_LINKS = (
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
	"""Remove the obsolete card previously added directly to Accounting."""
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


def remove_accounting_workspace_section():
	if not frappe.db.exists("Workspace", "Accounting"):
		return
	doc = frappe.get_doc("Workspace", "Accounting")
	content = [block for block in json.loads(doc.content or "[]") if block.get("id") != ACCOUNTING_CARD_ID]
	doc.content = json.dumps(content, separators=(",", ":"))
	doc.set("links", _without_financial_reports_section(doc.links))
	doc.flags.ignore_validate = True
	doc.save(ignore_permissions=True)


def _without_app_financial_report_links(rows):
	managed_sections = {"IFRS 18 Management Reports", "IFRS 18 Controls"}
	new_statement_targets = {link_to for _, link_to, _, _ in NEW_STATEMENT_LINKS}
	result = []
	skipping = False
	for row in rows:
		if row.type == "Card Break":
			skipping = row.label in managed_sections
			if skipping:
				continue
		if skipping:
			continue
		if row.type == "Link" and row.link_to in new_statement_targets:
			continue
		result.append(row)
	return result


def _workspace_row_dict(row):
	"""Return a clean child-row payload while preserving native Workspace fields."""
	data = row.as_dict()
	for key in (
		"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
		"parent", "parentfield", "parenttype", "doctype",
	):
		data.pop(key, None)
	return data


def _link_rows(links):
	return [{
		"type": "Link", "label": label, "link_to": link_to, "link_type": link_type,
		"is_query_report": is_query_report, "hidden": 0, "onboard": 0,
	} for label, link_to, link_type, is_query_report in links]


def integrate_financial_reports_workspace():
	"""Extend ERPNext's native Financial Reports sub-workspace without duplicating its reports."""
	if not frappe.db.exists("Workspace", FINANCIAL_REPORTS_WORKSPACE):
		return
	doc = frappe.get_doc("Workspace", FINANCIAL_REPORTS_WORKSPACE)
	content = [
		block for block in json.loads(doc.content or "[]")
		if block.get("id") not in {MANAGEMENT_CARD_ID, CONTROLS_CARD_ID}
	]
	content.extend([
		{"id": MANAGEMENT_CARD_ID, "type": "card", "data": {"card_name": "IFRS 18 Management Reports", "col": 4}},
		{"id": CONTROLS_CARD_ID, "type": "card", "data": {"card_name": "IFRS 18 Controls", "col": 4}},
	])
	doc.content = json.dumps(content, separators=(",", ":"))

	base_links = _without_app_financial_report_links(doc.links)
	ordered_links = []
	statements_inserted = False
	for row in base_links:
		ordered_links.append(_workspace_row_dict(row))
		if row.type == "Link" and row.link_to == "Cash Flow":
			ordered_links.extend(_link_rows(NEW_STATEMENT_LINKS))
			statements_inserted = True
	if not statements_inserted:
		ordered_links.append({"type": "Card Break", "label": "Financial Statements", "hidden": 0, "onboard": 0})
		ordered_links.extend(_link_rows(NEW_STATEMENT_LINKS))

	ordered_links.append({"type": "Card Break", "label": "IFRS 18 Management Reports", "hidden": 0, "onboard": 0})
	ordered_links.extend(_link_rows(MANAGEMENT_LINKS))
	ordered_links.append({"type": "Card Break", "label": "IFRS 18 Controls", "hidden": 0, "onboard": 0})
	ordered_links.extend(_link_rows(CONTROL_LINKS))
	doc.set("links", ordered_links)
	doc.flags.ignore_validate = True
	doc.save(ignore_permissions=True)


def remove_financial_reports_workspace_additions():
	if not frappe.db.exists("Workspace", FINANCIAL_REPORTS_WORKSPACE):
		return
	doc = frappe.get_doc("Workspace", FINANCIAL_REPORTS_WORKSPACE)
	content = [
		block for block in json.loads(doc.content or "[]")
		if block.get("id") not in {MANAGEMENT_CARD_ID, CONTROLS_CARD_ID}
	]
	doc.content = json.dumps(content, separators=(",", ":"))
	doc.set("links", _without_app_financial_report_links(doc.links))
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
	remove_accounting_workspace_section()
	integrate_financial_reports_workspace()
	frappe.db.commit()


def after_migrate():
	ensure_custom_fields()
	map_all_accounts()
	replace_standard_reports()
	remove_legacy_workspace()
	remove_accounting_workspace_section()
	integrate_financial_reports_workspace()
	frappe.clear_cache()


def before_uninstall():
	restore_standard_reports()
	remove_accounting_workspace_section()
	remove_financial_reports_workspace_additions()
	remove_legacy_workspace()
	remove_custom_fields()
	frappe.db.commit()

