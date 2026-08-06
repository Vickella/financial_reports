import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	query_filters = {"company": filters.company} if filters.get("company") else {}
	accounts = frappe.get_all(
		"Account", filters=query_filters,
		fields=["name", "company", "root_type", "account_type", "is_group", "custom_ifrs18_category",
			"custom_ifrs18_line_item", "custom_ifrs18_cash_flow_activity", "custom_ifrs18_note_reference",
			"custom_ifrs18_mapping_confidence", "custom_ifrs18_mapping_locked"],
		order_by="company, lft",
	)
	data = []
	for row in accounts:
		issues = []
		if not row.custom_ifrs18_category:
			issues.append(_("Missing category"))
		if not row.custom_ifrs18_line_item:
			issues.append(_("Missing line item"))
		if not row.custom_ifrs18_cash_flow_activity:
			issues.append(_("Missing cash flow mapping"))
		if row.custom_ifrs18_mapping_confidence == "Fallback":
			issues.append(_("Fallback mapping requires review"))
		row["status"] = "; ".join(issues) or _("Complete")
		if not filters.get("exceptions_only") or issues:
			data.append(row)
	columns = [
		{"fieldname": "name", "label": _("Account"), "fieldtype": "Link", "options": "Account", "width": 250},
		{"fieldname": "company", "label": _("Company"), "fieldtype": "Link", "options": "Company", "width": 150},
		{"fieldname": "root_type", "label": _("Root type"), "fieldtype": "Data", "width": 100},
		{"fieldname": "custom_ifrs18_category", "label": _("IFRS 18 category"), "fieldtype": "Data", "width": 180},
		{"fieldname": "custom_ifrs18_line_item", "label": _("Statement line item"), "fieldtype": "Data", "width": 240},
		{"fieldname": "custom_ifrs18_cash_flow_activity", "label": _("Cash flow"), "fieldtype": "Data", "width": 120},
		{"fieldname": "custom_ifrs18_note_reference", "label": _("Note"), "fieldtype": "Data", "width": 180},
		{"fieldname": "custom_ifrs18_mapping_confidence", "label": _("Confidence"), "fieldtype": "Data", "width": 110},
		{"fieldname": "custom_ifrs18_mapping_locked", "label": _("Reviewed"), "fieldtype": "Check", "width": 80},
		{"fieldname": "status", "label": _("Audit status"), "fieldtype": "Data", "width": 240},
	]
	complete = sum(1 for row in data if row.status == _("Complete"))
	summary = [{"label": _("Complete mappings"), "value": complete, "datatype": "Int"},
		{"label": _("Exceptions"), "value": len(data) - complete, "datatype": "Int", "indicator": "Red" if len(data) - complete else "Green"}]
	return columns, data, None, None, summary

