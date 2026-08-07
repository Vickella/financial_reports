import frappe
from frappe import _
from frappe.utils import flt

from financial_reports.reporting import aggregate_accounts, currency_for, get_periods, prepare_filters, value_for_category


def execute(filters=None):
	filters = prepare_filters(filters, accumulated_values=True)
	periods = get_periods(filters)
	currency = currency_for(filters)
	accounts = frappe.get_all(
		"Account",
		filters={"company": filters.company, "root_type": "Equity", "is_group": 0, "disabled": 0},
		fields=["name", "account_name", "custom_ifrs18_line_item", "custom_ifrs18_note_reference"],
		order_by="lft",
	)
	data = []
	for account in accounts:
		row = {
			"component": account.custom_ifrs18_line_item or account.account_name,
			"account": account.name,
			"note_reference": account.custom_ifrs18_note_reference or "",
			"currency": currency,
		}
		has_value = False
		for period in periods:
			opening = frappe.db.sql(
				"""select coalesce(sum(credit-debit),0) from `tabGL Entry`
				where company=%s and account=%s and posting_date < %s and is_cancelled=0""",
				(filters.company, account.name, period.from_date),
			)[0][0]
			movement = frappe.db.sql(
				"""select coalesce(sum(credit-debit),0) from `tabGL Entry`
				where company=%s and account=%s and posting_date between %s and %s and is_cancelled=0""",
				(filters.company, account.name, period.from_date, period.to_date),
			)[0][0]
			row[f"{period.key}_opening"] = flt(opening)
			row[f"{period.key}_movements"] = flt(movement)
			row[f"{period.key}_closing"] = flt(opening) + flt(movement)
			has_value = has_value or bool(opening or movement)
		if has_value or filters.show_zero_values:
			data.append(row)

	pl_filters = frappe._dict(filters.copy())
	pl_filters.accumulated_values = 0
	pnl_periods, aggregates, pnl_accounts = aggregate_accounts(pl_filters, ("Income", "Expense"))
	profit_row = {"component": _("Profit for the reporting period"), "account": "", "currency": currency}
	for period in periods:
		profit = sum(value_for_category(aggregates, category, period.key) for category in (
			"Operating", "Investing", "Financing", "Income taxes", "Discontinued operations"
		))
		profit_row[f"{period.key}_opening"] = 0
		profit_row[f"{period.key}_movements"] = profit
		profit_row[f"{period.key}_closing"] = profit
	if any(profit_row.get(f"{period.key}_movements") for period in periods):
		data.append(profit_row)

	columns = [
		{"fieldname": "component", "label": _("Equity component"), "fieldtype": "Data", "width": 250},
		{"fieldname": "note_reference", "label": _("Notes"), "fieldtype": "Data", "width": 90},
		{"fieldname": "account", "label": _("Account"), "fieldtype": "Link", "options": "Account", "width": 210},
	]
	for period in periods:
		columns.extend([
			{"fieldname": f"{period.key}_opening", "label": _("{0} opening").format(period.label), "fieldtype": "Currency", "options": "currency", "width": 180},
			{"fieldname": f"{period.key}_movements", "label": _("{0} changes").format(period.label), "fieldtype": "Currency", "options": "currency", "width": 180},
			{"fieldname": f"{period.key}_closing", "label": _("{0} closing").format(period.label), "fieldtype": "Currency", "options": "currency", "width": 180},
		])
	columns.append({"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "hidden": 1})
	return columns, data
