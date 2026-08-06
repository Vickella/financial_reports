from copy import deepcopy

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.cash_flow.cash_flow import execute as erpnext_cash_flow

from financial_reports.reporting import aggregate_accounts, currency_for, get_periods, prepare_filters, value_for_category


def _period_value_key(columns, data):
	reserved = {"section", "section_name", "account", "account_name", "currency", "total"}
	for column in columns:
		fieldname = column.get("fieldname") if isinstance(column, dict) else None
		if fieldname and fieldname not in reserved and any(fieldname in row for row in data if row):
			return fieldname
	frappe.throw(_("Unable to identify the cash flow value column."))


def _run_period(filters, from_date, to_date):
	period_filters = frappe._dict(deepcopy(dict(filters)))
	period_filters.comparison_enabled = 0
	period_filters.filter_based_on = "Date Range"
	period_filters.period_start_date = from_date
	period_filters.period_end_date = to_date
	period_filters.periodicity = "Yearly"
	period_filters.accumulated_values = 0
	result = list(erpnext_cash_flow(period_filters))
	return result, _period_value_key(result[0], result[1])


def _comparative_cash_flow(filters):
	comparison, comparison_key = _run_period(
		filters, filters.comparison_from_date, filters.comparison_to_date
	)
	current, current_key = _run_period(filters, filters.period_start_date, filters.period_end_date)
	currency = currency_for(filters)
	data = []
	for index in range(max(len(comparison[1]), len(current[1]))):
		comparison_row = comparison[1][index] if index < len(comparison[1]) else {}
		current_row = current[1][index] if index < len(current[1]) else {}
		row = deepcopy(current_row or comparison_row)
		if row:
			row["comparative_period"] = flt(comparison_row.get(comparison_key))
			row["current_period"] = flt(current_row.get(current_key))
			row["total"] = row["current_period"]
		data.append(row)
	columns = [
		{"fieldname": "section", "label": _("Cash flow"), "fieldtype": "Data", "width": 360},
		{
			"fieldname": "comparative_period",
			"label": _("Comparative ({0} to {1})").format(filters.comparison_from_date, filters.comparison_to_date),
			"fieldtype": "Currency", "options": "currency", "width": 190,
		},
		{
			"fieldname": "current_period",
			"label": _("Current ({0} to {1})").format(filters.period_start_date, filters.period_end_date),
			"fieldtype": "Currency", "options": "currency", "width": 190,
		},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "hidden": 1},
	]
	labels = [row.get("section", "").replace("'", "") for row in data if row.get("section_name") and not row.get("parent_section")]
	values = [row.get("current_period", 0) for row in data if row.get("section_name") and not row.get("parent_section")]
	chart = {"data": {"labels": labels, "datasets": [{"name": _("Current period"), "values": values}]},
		"type": "bar", "fieldtype": "Currency", "currency": currency}
	return [columns, data, None, chart, current[4] if len(current) > 4 else None]


def _reconcile_from_operating_profit(result, filters):
	data = result[1]
	periods, aggregates, account_rows = aggregate_accounts(filters, ("Income", "Expense"))
	profit_row = next(
		(row for row in data if str(row.get("account_name", "")).replace("'", "") == _("Profit for the year")),
		None,
	)
	if not profit_row:
		return
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
	profit_row["total"] = profit_row.get("current_period", sum(flt(profit_row.get(p.key)) for p in periods))
	reconciliation["total"] = reconciliation.get(
		"current_period", sum(flt(reconciliation.get(p.key)) for p in periods)
	)
	profit_row["account_name"] = "'" + _("Operating profit") + "'"
	profit_row["account"] = profit_row["account_name"]
	data.insert(data.index(profit_row) + 1, reconciliation)


def execute(filters=None):
	"""IFRS 18 / amended IAS 7 indirect cash flow beginning with operating profit."""
	filters = prepare_filters(filters)
	result = _comparative_cash_flow(filters) if filters.get("comparison_enabled") else list(
		erpnext_cash_flow(deepcopy(filters))
	)
	_reconcile_from_operating_profit(result, filters)
	return tuple(result)
