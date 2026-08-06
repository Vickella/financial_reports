"""Installation, migration and safe restoration of ERPNext report links."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from financial_reports.mapping import ALL_CATEGORIES, CASH_FLOW_ACTIVITIES, map_all_accounts


REPLACED_REPORTS = ("Profit and Loss Statement", "Balance Sheet", "Cash Flow")


def get_custom_fields():
	return {
		"Account": [
			{
				"fieldname": "custom_ifrs18_mapping_section",
				"label": "IFRS 18 Mapping",
				"fieldtype": "Section Break",
				"insert_after": "include_in_gross",
			},
			{
				"fieldname": "custom_ifrs18_category",
				"label": "IFRS 18 Category",
				"fieldtype": "Select",
				"options": "\n" + "\n".join(ALL_CATEGORIES),
				"insert_after": "custom_ifrs18_mapping_section",
				"in_list_view": 1,
			},
			{
				"fieldname": "custom_ifrs18_line_item",
				"label": "Statement Line Item",
				"fieldtype": "Data",
				"insert_after": "custom_ifrs18_category",
			},
			{
				"fieldname": "custom_ifrs18_mapping_column",
				"fieldtype": "Column Break",
				"insert_after": "custom_ifrs18_line_item",
			},
			{
				"fieldname": "custom_ifrs18_cash_flow_activity",
				"label": "Cash Flow Activity",
				"fieldtype": "Select",
				"options": "\n" + "\n".join(CASH_FLOW_ACTIVITIES),
				"insert_after": "custom_ifrs18_mapping_column",
			},
			{
				"fieldname": "custom_ifrs18_expense_nature",
				"label": "Expense by Nature",
				"fieldtype": "Data",
				"insert_after": "custom_ifrs18_cash_flow_activity",
			},
			{
				"fieldname": "custom_ifrs18_note_reference",
				"label": "Note / Disclosure Group",
				"fieldtype": "Data",
				"insert_after": "custom_ifrs18_expense_nature",
			},
			{
				"fieldname": "custom_ifrs18_mapping_source",
				"label": "Mapping Source",
				"fieldtype": "Data",
				"read_only": 1,
				"insert_after": "custom_ifrs18_note_reference",
			},
			{
				"fieldname": "custom_ifrs18_mapping_confidence",
				"label": "Mapping Confidence",
				"fieldtype": "Select",
				"options": "Rule based\nFallback\nManually reviewed",
				"read_only": 1,
				"insert_after": "custom_ifrs18_mapping_source",
			},
			{
				"fieldname": "custom_ifrs18_mapping_locked",
				"label": "Lock Manual Mapping",
				"fieldtype": "Check",
				"default": "0",
				"insert_after": "custom_ifrs18_mapping_confidence",
				"description": "Prevents automatic remapping during migrations.",
			},
		]
	}


def ensure_custom_fields():
	create_custom_fields(get_custom_fields(), update=True)
	frappe.clear_cache(doctype="Account")


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
	frappe.db.commit()


def after_migrate():
	ensure_custom_fields()
	map_all_accounts()
	replace_standard_reports()
	frappe.clear_cache()


def before_uninstall():
	restore_standard_reports()
	frappe.db.commit()

