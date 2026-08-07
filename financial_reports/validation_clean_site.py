"""Controlled setup and status checks for the isolated independence-test site."""

import json

import frappe


SITE = "ifrs18-clean.test"
COMPANY = "IFRS 18 Clean UAT"


def prepare_company():
	if frappe.local.site != SITE:
		frappe.throw(f"Clean-site setup is restricted to {SITE}")
	if frappe.db.exists("Company", COMPANY):
		return {"created": False, "company": COMPANY}
	# A fresh ERPNext site without the setup wizard does not yet have this
	# standard link target required by Company.create_default_warehouses().
	if not frappe.db.exists("Warehouse Type", "Transit"):
		frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"}).insert(ignore_permissions=True)
	doc = frappe.get_doc({
		"doctype": "Company",
		"company_name": COMPANY,
		"abbr": "I18U",
		"default_currency": "USD",
		"country": "Zimbabwe",
		"create_chart_of_accounts_based_on": "Standard Template",
		"chart_of_accounts": "Standard",
	}).insert(ignore_permissions=True)
	return {"created": True, "company": doc.name, "accounts": frappe.db.count("Account", {"company": doc.name})}


def installation_status():
	apps = frappe.get_installed_apps()
	accounting = frappe.get_doc("Workspace", "Accounting") if frappe.db.exists("Workspace", "Accounting") else None
	accounting_content = json.loads(accounting.content or "[]") if accounting else []
	workspace = frappe.get_doc("Workspace", "Financial Reports") if frappe.db.exists("Workspace", "Financial Reports") else None
	workspace_content = json.loads(workspace.content or "[]") if workspace else []
	workspace_targets = [row.link_to for row in workspace.links if row.type == "Link"] if workspace else []
	return {
		"installed_apps": apps,
		"optional_apps_present": sorted(set(apps).intersection({"veritytax", "verityguard"})),
		"financial_reports_installed": "financial_reports" in apps,
		"accounts": frappe.db.count("Account", {"company": COMPANY}) if frappe.db.exists("Company", COMPANY) else 0,
		"unmapped_accounts": frappe.db.count("Account", {"company": COMPANY, "custom_ifrs18_category": ["in", (None, "")]}) if frappe.db.has_column("Account", "custom_ifrs18_category") else None,
		"fallback_accounts": frappe.db.count("Account", {"company": COMPANY, "custom_ifrs18_mapping_confidence": "Fallback"}) if frappe.db.has_column("Account", "custom_ifrs18_mapping_confidence") else None,
		"legacy_workspace_exists": bool(frappe.db.exists("Workspace", "IFRS 18 Financial Reporting")),
		"accounting_extra_card_count": sum(block.get("id") == "financial_reports_accounting_card" for block in accounting_content),
		"native_workspace": {
			"exists": bool(workspace), "module": workspace.module if workspace else None,
			"parent_page": workspace.parent_page if workspace else None,
			"management_cards": sum(block.get("id") == "financial_reports_management_card" for block in workspace_content),
			"controls_cards": sum(block.get("id") == "financial_reports_controls_card" for block in workspace_content),
			"standard_link_counts": {name: workspace_targets.count(name) for name in ("Profit and Loss Statement", "Balance Sheet", "Cash Flow")},
		},
		"standard_report_modules": {
			name: frappe.db.get_value("Report", name, "module")
			for name in ("Profit and Loss Statement", "Balance Sheet", "Cash Flow")
		},
	}
