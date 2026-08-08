from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import flt

from financial_reports.reporting import (
	aggregate_accounts,
	currency_for,
	get_columns,
	prepare_filters,
)


def execute(filters=None):
	filters = prepare_filters(filters)
	movement_filters = frappe._dict(filters.copy())
	movement_filters.accumulated_values = 0
	periods, _pnl, pnl_accounts = aggregate_accounts(
		movement_filters, ("Income", "Expense")
	)
	position_filters = frappe._dict(filters.copy())
	position_filters.accumulated_values = 1
	_position_periods, _position, position_accounts = aggregate_accounts(
		position_filters, ("Asset", "Liability", "Equity")
	)
	currency = currency_for(filters)
	notes = OrderedDict()
	for row, mapping, factor in pnl_accounts + position_accounts:
		note = mapping.custom_ifrs18_note_reference or _("Other disclosures")
		line_item = mapping.custom_ifrs18_line_item or _("Unmapped accounts")
		bucket = notes.setdefault(
			(note, line_item),
			{"note": note, "line_item": line_item, "currency": currency},
		)
		for period in periods:
			bucket[period.key] = (
				flt(bucket.get(period.key))
				+ factor * flt(row.get(period.key))
			)
		bucket["total"] = (
			flt(bucket.get("total"))
			+ factor * flt(row.get("total"))
		)
	data = list(notes.values())
	columns = [
		{
			"fieldname": "note",
			"label": _("Disclosure group"),
			"fieldtype": "Data",
			"width": 260,
		},
		{
			"fieldname": "line_item",
			"label": _("Line item"),
			"fieldtype": "Data",
			"width": 260,
		},
	] + get_columns(
		filters.periodicity,
		periods,
		filters.accumulated_values,
		filters.company,
	)[1:]
	return columns, data
