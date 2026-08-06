import frappe
from frappe import _
from frappe.utils import flt

from financial_reports.reporting import aggregate_accounts, currency_for, prepare_filters, value_for_category


def execute(filters=None):
	filters = prepare_filters(filters)
	periods, aggregates, account_rows = aggregate_accounts(filters, ("Income", "Expense"))
	currency = currency_for(filters)
	account_values = {}
	for row, _, factor in account_rows:
		account_values[row.account] = factor * flt(row.get("total"))
	category_values = {category: value_for_category(aggregates, category) for category in (
		"Operating", "Investing", "Financing", "Income taxes", "Discontinued operations"
	)}
	subtotals = {
		"Operating profit": category_values["Operating"],
		"Profit before financing and income taxes": category_values["Operating"] + category_values["Investing"],
		"Profit before income tax": category_values["Operating"] + category_values["Investing"] + category_values["Financing"],
		"Profit from continuing operations": category_values["Operating"] + category_values["Investing"] + category_values["Financing"] + category_values["Income taxes"],
		"Profit": sum(category_values.values()),
	}
	data = []
	measures = frappe.get_all(
		"IFRS 18 Management Performance Measure",
		filters={"company": filters.company, "active": 1}, pluck="name",
	)
	for name in measures:
		measure = frappe.get_doc("IFRS 18 Management Performance Measure", name)
		base = flt(subtotals.get(measure.comparable_subtotal))
		data.append({"measure": measure.measure_name, "item": measure.comparable_subtotal, "amount": base, "row_type": _("IFRS subtotal"), "currency": currency})
		total = base
		for adjustment in measure.adjustments:
			account_amount = abs(flt(account_values.get(adjustment.account)))
			amount = account_amount if adjustment.treatment == "Add" else -account_amount
			tax_effect = -amount * flt(adjustment.tax_rate) / 100
			nci_effect = flt(adjustment.nci_effect)
			data.append({
				"measure": measure.measure_name, "item": adjustment.adjustment_label,
				"account": adjustment.account, "amount": amount, "tax_effect": tax_effect,
				"nci_effect": nci_effect, "row_type": _("Reconciling item"), "currency": currency,
			})
			total += amount + tax_effect + nci_effect
		data.append({"measure": measure.measure_name, "item": measure.measure_name, "amount": total, "row_type": _("Management-defined performance measure"), "currency": currency, "reason": measure.reason_for_use})
	columns = [
		{"fieldname":"measure","label":_("Measure"),"fieldtype":"Link","options":"IFRS 18 Management Performance Measure","width":220},
		{"fieldname":"item","label":_("Reconciliation"),"fieldtype":"Data","width":280},
		{"fieldname":"account","label":_("Account"),"fieldtype":"Link","options":"Account","width":200},
		{"fieldname":"amount","label":_("Amount"),"fieldtype":"Currency","options":"currency","width":140},
		{"fieldname":"tax_effect","label":_("Income tax effect"),"fieldtype":"Currency","options":"currency","width":140},
		{"fieldname":"nci_effect","label":_("NCI effect"),"fieldtype":"Currency","options":"currency","width":120},
		{"fieldname":"row_type","label":_("Type"),"fieldtype":"Data","width":170},
		{"fieldname":"reason","label":_("Why management uses it"),"fieldtype":"Data","width":300},
		{"fieldname":"currency","label":_("Currency"),"fieldtype":"Data","hidden":1},
	]
	return columns, data

