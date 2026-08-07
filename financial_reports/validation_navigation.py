"""Read-only validation of native Financial Reports navigation and Account-field UX."""

import json

import frappe

from financial_reports.install import CONTROL_LINKS, MANAGEMENT_LINKS, NEW_STATEMENT_LINKS


def get_status():
	accounting = frappe.get_doc("Workspace", "Accounting")
	accounting_content = json.loads(accounting.content or "[]")
	accounting_labels = [row.label for row in accounting.links]
	workspace = frappe.get_doc("Workspace", "Financial Reports")
	content = json.loads(workspace.content or "[]")
	link_targets = [row.link_to for row in workspace.links if row.type == "Link"]
	section = None
	sections_by_target = {}
	for row in workspace.links:
		if row.type == "Card Break":
			section = row.label
		elif row.type == "Link":
			sections_by_target[row.link_to] = section
	managed_targets = {link_to for _, link_to, _, _ in (*NEW_STATEMENT_LINKS, *MANAGEMENT_LINKS, *CONTROL_LINKS)}
	field_order = [
		field.fieldname for field in frappe.get_meta("Account").fields
		if field.fieldname.startswith("custom_ifrs18_")
	]
	return {
		"legacy_workspace_exists": bool(frappe.db.exists("Workspace", "IFRS 18 Financial Reporting")),
		"accounting_extra_card_count": sum(block.get("id") == "financial_reports_accounting_card" for block in accounting_content),
		"accounting_extra_section_count": accounting_labels.count("Financial Reports"),
		"workspace_name": workspace.name, "workspace_module": workspace.module,
		"workspace_parent_page": workspace.parent_page,
		"native_standard_link_counts": {name: link_targets.count(name) for name in (
			"Profit and Loss Statement", "Balance Sheet", "Cash Flow",
		)},
		"management_card_count": sum(block.get("id") == "financial_reports_management_card" for block in content),
		"controls_card_count": sum(block.get("id") == "financial_reports_controls_card" for block in content),
		"added_link_count": sum(target in managed_targets for target in link_targets),
		"added_link_targets": [target for target in link_targets if target in managed_targets],
		"added_link_sections": {
			target: sections_by_target.get(target) for target in managed_targets
		},
		"new_statements_in_financial_statements": all(
			sections_by_target.get(target) == "Financial Statements"
			for _, target, _, _ in NEW_STATEMENT_LINKS
		),
		"management_links_in_management_section": all(
			sections_by_target.get(target) == "IFRS 18 Management Reports"
			for _, target, _, _ in MANAGEMENT_LINKS
		),
		"control_links_in_controls_section": all(
			sections_by_target.get(target) == "IFRS 18 Controls"
			for _, target, _, _ in CONTROL_LINKS
		),
		"account_ifrs18_field_order": field_order,
	}
