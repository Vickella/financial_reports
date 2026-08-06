import frappe
from frappe import _
from frappe.utils import flt

from financial_reports.reporting import aggregate_accounts, currency_for, prepare_filters, value_for_category


def execute(filters=None):
	filters = prepare_filters(filters)
	periods, aggregates, account_rows = aggregate_accounts(filters, ("Income", "Expense"))
	currency = currency_for(filters)
	account_values = {}
	for row, mapping, factor in account_rows:
		account_values[row.account] = {period.key: factor * flt(row.get(period.key)) for period in periods}
	category_values = {
		category: {period.key: value_for_category(aggregates, category, period.key) for period in periods}
		for category in ("Operating", "Investing", "Financing", "Income taxes", "Discontinued operations")
	}
	subtotals = {}
	for period in periods:
		key = period.key
		subtotals[key] = {
			"Operating profit": category_values["Operating"][key],
			"Profit before financing and income taxes": category_values["Operating"][key] + category_values["Investing"][key],
			"Profit before income tax": category_values["Operating"][key] + category_values["Investing"][key] + category_values["Financing"][key],
			"Profit from continuing operations": category_values["Operating"][key] + category_values["Investing"][key] + category_values["Financing"][key] + category_values["Income taxes"][key],
			"Profit": sum(values[key] for values in category_values.values()),
		}
	data = []
	for name in frappe.get_all("IFRS 18 Management Performance Measure", filters={"company": filters.company, "active": 1}, pluck="name"):
		measure = frappe.get_doc("IFRS 18 Management Performance Measure", name)
		base_row = {"measure": measure.measure_name, "item": measure.comparable_subtotal, "row_type": _("IFRS subtotal"), "currency": currency}
		totals = {}
		for period in periods:
			base_row[period.key] = flt(subtotals[period.key].get(measure.comparable_subtotal))
			totals[period.key] = base_row[period.key]
		data.append(base_row)
		for adjustment in measure.adjustments:
			row = {"measure": measure.measure_name, "item": adjustment.adjustment_label, "account": adjustment.account, "row_type": _("Reconciling item"), "currency": currency}
			for period in periods:
				account_amount = abs(flt(account_values.get(adjustment.account, {}).get(period.key)))
				amount = account_amount if adjustment.treatment == "Add" else -account_amount
				tax_effect = -amount * flt(adjustment.tax_rate) / 100
				nci_effect = flt(adjustment.nci_effect)
				row[period.key] = amount
				row[f"{period.key}_tax"] = tax_effect
				row[f"{period.key}_nci"] = nci_effect
				totals[period.key] += amount + tax_effect + nci_effect
			data.append(row)
		total_row = {"measure": measure.measure_name, "item": measure.measure_name, "row_type": _("Management-defined performance measure"), "reason": measure.reason_for_use, "currency": currency}
		for period in periods:
			total_row[period.key] = totals[period.key]
		data.append(total_row)
	columns = [
		{"fieldname":"measure","label":_("Measure"),"fieldtype":"Link","options":"IFRS 18 Management Performance Measure","width":210},
		{"fieldname":"item","label":_("Reconciliation"),"fieldtype":"Data","width":260},
		{"fieldname":"account","label":_("Account"),"fieldtype":"Link","options":"Account","width":190},
	]
	for period in periods:
		columns.extend([
			{"fieldname":period.key,"label":period.label,"fieldtype":"Currency","options":"currency","width":180},
			{"fieldname":f"{period.key}_tax","label":_("{0} tax effect").format(period.label),"fieldtype":"Currency","options":"currency","width":160},
			{"fieldname":f"{period.key}_nci","label":_("{0} NCI effect").format(period.label),"fieldtype":"Currency","options":"currency","width":160},
		])
	columns.extend([
		{"fieldname":"row_type","label":_("Type"),"fieldtype":"Data","width":170},
		{"fieldname":"reason","label":_("Why management uses it"),"fieldtype":"Data","width":280},
		{"fieldname":"currency","label":_("Currency"),"fieldtype":"Data","hidden":1},
	])
	return columns, data
