from copy import deepcopy

from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.cash_flow.cash_flow import execute as erpnext_cash_flow

from financial_reports.reporting import aggregate_accounts, prepare_filters, value_for_category


def execute(filters=None):
	"""ERPNext indirect cash flow, reconciled from IFRS 18 operating profit."""
	filters = prepare_filters(filters)
	result = list(erpnext_cash_flow(deepcopy(filters)))
	columns, data = result[0], result[1]
	periods, aggregates, _ = aggregate_accounts(filters, ("Income", "Expense"))

	profit_row = next((row for row in data if row.get("account_name") == "'Profit for the year'"), None)
	if profit_row:
		reconciliation = deepcopy(profit_row)
		reconciliation.update({
			"account_name": _("Investing, financing, tax and discontinued results"),
			"account": _("Investing, financing, tax and discontinued results"),
			"section": _("Non-operating result reconciliation"),
			"indent": 1,
		})
		for period in periods:
			operating = value_for_category(aggregates, "Operating", period.key)
			reconciliation[period.key] = flt(profit_row.get(period.key)) - operating
			profit_row[period.key] = operating
		profit_row["total"] = sum(flt(profit_row.get(p.key)) for p in periods)
		reconciliation["total"] = sum(flt(reconciliation.get(p.key)) for p in periods)
		profit_row["account_name"] = "'" + _("Operating profit") + "'"
		profit_row["account"] = profit_row["account_name"]
		data.insert(data.index(profit_row) + 1, reconciliation)
	return tuple(result)

