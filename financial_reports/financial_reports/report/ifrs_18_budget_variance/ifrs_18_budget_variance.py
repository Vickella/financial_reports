import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

from erpnext.accounts.report.financial_statements import get_accounting_entries


def _actuals(filters, from_date, to_date):
	"""Return account-level P&L movements using ERPNext's standard GL filters."""
	entries = get_accounting_entries(
		"GL Entry",
		from_date,
		to_date,
		filters,
		root_type=None,
		ignore_closing_entries=True,
		group_by_account=True,
	)
	return {
		entry.account: flt(entry.credit) - flt(entry.debit)
		for entry in entries
	}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company") or not filters.get("fiscal_year"):
		frappe.throw(_("Company and Fiscal Year are required"))
	filters.setdefault("include_default_book_entries", 1)
	fy = frappe.get_cached_doc("Fiscal Year", filters.fiscal_year)
	from_date = getdate(filters.get("from_date") or fy.year_start_date)
	to_date = getdate(filters.get("to_date") or fy.year_end_date)
	if to_date < from_date:
		frappe.throw(_("To Date cannot be before From Date"))
	if filters.get("comparison_enabled"):
		if not filters.get("comparison_from_date") or not filters.get("comparison_to_date"):
			frappe.throw(_("Comparative From and To dates are required"))
		if getdate(filters.comparison_to_date) < getdate(filters.comparison_from_date):
			frappe.throw(_("Comparative To Date cannot be before Comparative From Date"))

	fy_days = date_diff(fy.year_end_date, fy.year_start_date) + 1
	selected_days = date_diff(to_date, from_date) + 1
	budget_factor = selected_days / fy_days
	budgets = frappe.db.sql(
		"""select ba.account, sum(ba.budget_amount) as annual_budget
		from `tabBudget Account` ba inner join `tabBudget` b on b.name=ba.parent
		where b.docstatus=1 and b.company=%s and b.fiscal_year=%s
		group by ba.account""",
		(filters.company, filters.fiscal_year), as_dict=True,
	)
	current_actuals = _actuals(filters, from_date, to_date)
	comparative_actuals = {}
	if filters.get("comparison_enabled"):
		comparative_actuals = _actuals(
			filters,
			getdate(filters.comparison_from_date),
			getdate(filters.comparison_to_date),
		)

	data = []
	for item in budgets:
		account = frappe.get_cached_value(
			"Account",
			item.account,
			[
				"account_name",
				"root_type",
				"custom_ifrs18_category",
				"custom_ifrs18_line_item",
			],
			as_dict=True,
		)
		budget = flt(item.annual_budget) * budget_factor
		actual = flt(current_actuals.get(item.account))
		variance = actual - budget
		favourable = variance >= 0 if account.root_type == "Income" else variance <= 0
		row = {
			"account": item.account,
			"account_name": account.account_name,
			"category": account.custom_ifrs18_category,
			"line_item": account.custom_ifrs18_line_item,
			"budget": budget,
			"actual": actual,
			"variance": variance,
			"variance_percent": variance / budget * 100 if budget else 0,
			"status": _("Favourable") if favourable else _("Adverse"),
		}
		if filters.get("comparison_enabled"):
			row["comparative_actual"] = flt(comparative_actuals.get(item.account))
			row["year_on_year_change"] = actual - row["comparative_actual"]
		data.append(row)
	columns = [
		{"fieldname": "account", "label": _("Account"), "fieldtype": "Link", "options": "Account", "width": 210},
		{"fieldname": "category", "label": _("IFRS 18 category"), "fieldtype": "Data", "width": 150},
		{"fieldname": "line_item", "label": _("Line item"), "fieldtype": "Data", "width": 210},
		{"fieldname": "budget", "label": _("Prorated budget"), "fieldtype": "Currency", "width": 140},
		{"fieldname": "actual", "label": _("Current actual"), "fieldtype": "Currency", "width": 140},
	]
	if filters.get("comparison_enabled"):
		columns.extend([
			{"fieldname": "comparative_actual", "label": _("Comparative actual"), "fieldtype": "Currency", "width": 150},
			{"fieldname": "year_on_year_change", "label": _("Period change"), "fieldtype": "Currency", "width": 140},
		])
	columns.extend([
		{"fieldname": "variance", "label": _("Budget variance"), "fieldtype": "Currency", "width": 140},
		{"fieldname": "variance_percent", "label": _("Variance %"), "fieldtype": "Percent", "width": 110},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
	])
	return columns, data
