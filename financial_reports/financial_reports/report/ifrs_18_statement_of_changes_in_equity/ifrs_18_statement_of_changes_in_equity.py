import frappe
from frappe import _
from frappe.utils import flt

from financial_reports.reporting import aggregate_accounts, currency_for, get_periods, prepare_filters, value_for_category


def execute(filters=None):
	filters = prepare_filters(filters, accumulated_values=True)
	periods = get_periods(filters)
	from_date, to_date = periods[0].from_date, periods[-1].to_date
	currency = currency_for(filters)
	accounts = frappe.get_all(
		"Account",
		filters={"company": filters.company, "root_type": "Equity", "is_group": 0},
		fields=["name", "account_name", "custom_ifrs18_line_item"],
	)
	data = []
	for account in accounts:
		opening = frappe.db.sql(
			"""select coalesce(sum(credit - debit), 0) from `tabGL Entry`
			where company=%s and account=%s and posting_date < %s and is_cancelled=0""",
			(filters.company, account.name, from_date),
		)[0][0]
		movement = frappe.db.sql(
			"""select coalesce(sum(credit - debit), 0) from `tabGL Entry`
			where company=%s and account=%s and posting_date between %s and %s and is_cancelled=0""",
			(filters.company, account.name, from_date, to_date),
		)[0][0]
		if opening or movement or filters.show_zero_values:
			data.append({
				"component": account.custom_ifrs18_line_item or account.account_name,
				"account": account.name,
				"opening": flt(opening),
				"movements": flt(movement),
				"closing": flt(opening) + flt(movement),
				"currency": currency,
			})

	pl_filters = frappe._dict(filters.copy())
	pl_filters.accumulated_values = 0
	_, aggregates, _ = aggregate_accounts(pl_filters, ("Income", "Expense"))
	profit = sum(value_for_category(aggregates, category) for category in (
		"Operating", "Investing", "Financing", "Income taxes", "Discontinued operations"
	))
	if profit:
		data.append({"component": _("Profit for the period"), "account": "", "opening": 0, "movements": profit, "closing": profit, "currency": currency})

	columns = [
		{"fieldname": "component", "label": _("Equity component"), "fieldtype": "Data", "width": 260},
		{"fieldname": "account", "label": _("Account"), "fieldtype": "Link", "options": "Account", "width": 220},
		{"fieldname": "opening", "label": _("Opening balance"), "fieldtype": "Currency", "options": "currency", "width": 160},
		{"fieldname": "movements", "label": _("Changes during period"), "fieldtype": "Currency", "options": "currency", "width": 180},
		{"fieldname": "closing", "label": _("Closing balance"), "fieldtype": "Currency", "options": "currency", "width": 160},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "hidden": 1},
	]
	return columns, data

