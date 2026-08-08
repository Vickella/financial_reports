import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from erpnext.accounts.report.financial_statements import apply_additional_conditions

from financial_reports.reporting import (
	PROFIT_ORDER,
	currency_for,
	get_periods,
	prepare_filters,
)


def _period_rows(filters, period):
	gle = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")
	query = (
		frappe.qb.from_(gle)
		.inner_join(account)
		.on(account.name == gle.account)
		.select(
			gle.cost_center,
			account.custom_ifrs18_category.as_("category"),
			account.root_type,
			Sum(gle.debit - gle.credit).as_("amount"),
		)
		.where(gle.company == filters.company)
		.where(gle.is_cancelled == 0)
		.where(gle.posting_date <= period.to_date)
		.where(account.root_type.isin(("Income", "Expense")))
		.groupby(gle.cost_center, account.custom_ifrs18_category, account.root_type)
	)
	query = apply_additional_conditions(
		"GL Entry", query, period.from_date, True, filters
	)
	return query.run(as_dict=True)


def execute(filters=None):
	filters = prepare_filters(filters)
	periods = get_periods(filters)
	currency = currency_for(filters)
	centres = {}
	for period in periods:
		for item in _period_rows(filters, period):
			if item.category not in PROFIT_ORDER:
				continue
			centre_name = item.cost_center or _("Unallocated")
			centre = centres.setdefault(
				centre_name,
				{"cost_center": centre_name, "currency": currency},
			)
			centre.setdefault(f"{period.key}_revenue", 0)
			centre.setdefault(f"{period.key}_operating_profit", 0)
			centre.setdefault(f"{period.key}_profit", 0)
			statement_amount = -flt(item.amount)
			centre[f"{period.key}_profit"] += statement_amount
			if item.category == "Operating":
				centre[f"{period.key}_operating_profit"] += statement_amount
			if item.root_type == "Income" and item.category == "Operating":
				centre[f"{period.key}_revenue"] += statement_amount

	data = sorted(centres.values(), key=lambda row: row["cost_center"])
	for row in data:
		for period in periods:
			revenue = row.get(f"{period.key}_revenue", 0)
			row[f"{period.key}_operating_margin"] = (
				row.get(f"{period.key}_operating_profit", 0) / revenue * 100
				if revenue else 0
			)
	columns = [
		{
			"fieldname": "cost_center",
			"label": _("Cost Center"),
			"fieldtype": "Data",
			"width": 220,
		}
	]
	for period in periods:
		columns.extend([
			{"fieldname": f"{period.key}_revenue", "label": _("{0} revenue").format(period.label), "fieldtype": "Currency", "options": "currency", "width": 170},
			{"fieldname": f"{period.key}_operating_profit", "label": _("{0} operating profit").format(period.label), "fieldtype": "Currency", "options": "currency", "width": 190},
			{"fieldname": f"{period.key}_operating_margin", "label": _("{0} margin").format(period.label), "fieldtype": "Percent", "width": 150},
			{"fieldname": f"{period.key}_profit", "label": _("{0} profit").format(period.label), "fieldtype": "Currency", "options": "currency", "width": 170},
		])
	columns.append(
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "hidden": 1}
	)
	latest = periods[-1].key
	chart = {
		"data": {
			"labels": [row["cost_center"] for row in data],
			"datasets": [{
				"name": _("Operating profit"),
				"values": [row.get(f"{latest}_operating_profit", 0) for row in data],
			}],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"currency": currency,
	}
	return columns, data, None, chart
