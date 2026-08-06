from collections import OrderedDict

from frappe import _
from frappe.utils import flt

from financial_reports.reporting import aggregate_accounts, currency_for, get_columns, prepare_filters


def execute(filters=None):
	filters = prepare_filters(filters)
	periods, _, account_rows = aggregate_accounts(filters)
	currency = currency_for(filters)
	notes = OrderedDict()
	for row, mapping, factor in account_rows:
		note = mapping.custom_ifrs18_note_reference or _("Other disclosures")
		line_item = mapping.custom_ifrs18_line_item or _("Unmapped accounts")
		bucket = notes.setdefault((note, line_item), {"note": note, "line_item": line_item, "currency": currency})
		for period in periods:
			bucket[period.key] = flt(bucket.get(period.key)) + factor * flt(row.get(period.key))
		bucket["total"] = flt(bucket.get("total")) + factor * flt(row.get("total"))
	data = list(notes.values())
	columns = [
		{"fieldname": "note", "label": _("Note / disclosure group"), "fieldtype": "Data", "width": 260},
		{"fieldname": "line_item", "label": _("Line item"), "fieldtype": "Data", "width": 260},
	] + get_columns(filters.periodicity, periods, filters.accumulated_values, filters.company)[1:]
	return columns, data

