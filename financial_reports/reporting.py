"""Shared IFRS 18 statement engine built on ERPNext's audited GL utilities."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.financial_statements import get_columns, get_data, get_period_list


PROFIT_ORDER = (
	"Operating",
	"Investing",
	"Financing",
	"Income taxes",
	"Discontinued operations",
)
POSITION_ORDER = (
	"Non-current assets",
	"Current assets",
	"Equity",
	"Non-current liabilities",
	"Current liabilities",
)
OCI_CATEGORIES = (
	"Other comprehensive income - reclassifiable",
	"Other comprehensive income - non-reclassifiable",
)


def prepare_filters(filters, accumulated_values=False):
	filters = frappe._dict(filters or {})
	filters.setdefault("company", frappe.defaults.get_user_default("Company"))
	filters.setdefault("filter_based_on", "Fiscal Year")
	filters.setdefault("periodicity", "Yearly")
	filters.setdefault("accumulated_values", accumulated_values)
	filters.setdefault("include_default_book_entries", 1)
	filters.setdefault("show_zero_values", 0)
	if filters.filter_based_on == "Fiscal Year":
		default_fy = frappe.defaults.get_user_default("fiscal_year") or frappe.db.get_default("fiscal_year")
		filters.setdefault("from_fiscal_year", default_fy)
		filters.setdefault("to_fiscal_year", filters.from_fiscal_year)
	return filters


def get_periods(filters):
	return get_period_list(
		filters.from_fiscal_year,
		filters.to_fiscal_year,
		filters.period_start_date,
		filters.period_end_date,
		filters.filter_based_on,
		filters.periodicity,
		company=filters.company,
	)


def currency_for(filters):
	return filters.get("presentation_currency") or frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)


def account_mappings(company):
	fields = [
		"name", "root_type", "account_type", "custom_ifrs18_category",
		"custom_ifrs18_line_item", "custom_ifrs18_cash_flow_activity",
		"custom_ifrs18_expense_nature", "custom_ifrs18_note_reference",
	]
	return {d.name: d for d in frappe.get_all("Account", filters={"company": company}, fields=fields)}


def aggregate_accounts(filters, root_types=("Income", "Expense", "Asset", "Liability", "Equity")):
	"""Return leaf-account balances aggregated by IFRS category and statement line."""
	filters = prepare_filters(filters)
	periods = get_periods(filters)
	mappings = account_mappings(filters.company)
	aggregates = OrderedDict()
	account_rows = []

	for root_type in root_types:
		balance_must_be = "Credit" if root_type in ("Income", "Liability", "Equity") else "Debit"
		rows = get_data(
			filters.company,
			root_type,
			balance_must_be,
			periods,
			filters=filters,
			accumulated_values=filters.accumulated_values,
			only_current_fiscal_year=root_type in ("Income", "Expense"),
			ignore_closing_entries=root_type in ("Income", "Expense"),
			total=False,
		) or []
		for row in rows:
			if row.get("is_group"):
				continue
			mapping = mappings.get(row.get("account"))
			if not mapping:
				continue
			category = mapping.custom_ifrs18_category or "Unmapped"
			line_item = mapping.custom_ifrs18_line_item or "Unmapped accounts"
			key = (category, line_item)
			bucket = aggregates.setdefault(
				key,
				{
					"category": category,
					"line_item": line_item,
					"accounts": [],
					"currency": currency_for(filters),
				},
			)
			factor = -1 if root_type == "Expense" else 1
			for period in periods:
				bucket[period.key] = flt(bucket.get(period.key)) + factor * flt(row.get(period.key))
			bucket["total"] = flt(bucket.get("total")) + factor * flt(row.get("total"))
			bucket["accounts"].append(row.get("account"))
			account_rows.append((row, mapping, factor))

	return periods, aggregates, account_rows


def _total_row(label, rows, periods, currency, indent=0):
	row = {
		"account_name": f"'{_(label)}'",
		"account": f"'{_(label)}'",
		"line_item": f"'{_(label)}'",
		"currency": currency,
		"indent": indent,
		"is_total": 1,
	}
	for period in periods:
		row[period.key] = sum(flt(item.get(period.key)) for item in rows)
	row["total"] = sum(flt(item.get("total")) for item in rows)
	return row


def category_rows(aggregates, category, periods, currency):
	rows = []
	for (mapped_category, line_item), values in aggregates.items():
		if mapped_category != category:
			continue
		row = deepcopy(values)
		row.update({"account_name": _(line_item), "account": _(line_item), "indent": 1})
		rows.append(row)
	return rows


def profit_or_loss(filters):
	filters = prepare_filters(filters)
	periods, aggregates, _ = aggregate_accounts(filters, ("Income", "Expense"))
	currency = currency_for(filters)
	data = []
	cumulative = []

	def add_category(category, subtotal=None):
		rows = category_rows(aggregates, category, periods, currency)
		if rows:
			data.append({"account_name": f"'{_(category)}'", "account": f"'{_(category)}'", "indent": 0})
			data.extend(rows)
		cumulative.extend(rows)
		if subtotal:
			data.append(_total_row(subtotal, cumulative, periods, currency))
			data.append({})
		return rows

	operating = add_category("Operating", "Operating profit")
	add_category("Investing", "Profit before financing and income taxes")
	add_category("Financing", "Profit before income tax")
	add_category("Income taxes", "Profit from continuing operations")
	add_category("Discontinued operations", "Profit")

	columns = get_columns(filters.periodicity, periods, filters.accumulated_values, filters.company)
	operating_total = _total_row("Operating profit", operating, periods, currency)
	profit_total = _total_row("Profit", cumulative, periods, currency)
	chart = {
		"data": {
			"labels": [p.label for p in periods],
			"datasets": [
				{"name": _("Operating profit"), "values": [operating_total.get(p.key, 0) for p in periods]},
				{"name": _("Profit"), "values": [profit_total.get(p.key, 0) for p in periods]},
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"currency": currency,
	}
	summary = [
		{"label": _("Operating profit"), "value": operating_total.get("total", 0), "datatype": "Currency", "currency": currency},
		{"label": _("Profit"), "value": profit_total.get("total", 0), "datatype": "Currency", "currency": currency,
		 "indicator": "Green" if profit_total.get("total", 0) >= 0 else "Red"},
	]
	return columns, data, None, chart, summary


def financial_position(filters):
	filters = prepare_filters(filters, accumulated_values=True)
	filters.accumulated_values = 1
	periods, aggregates, _ = aggregate_accounts(filters, ("Asset", "Liability", "Equity"))
	currency = currency_for(filters)
	data = []
	section_totals = {}
	for category in POSITION_ORDER:
		rows = category_rows(aggregates, category, periods, currency)
		data.append({"account_name": f"'{_(category)}'", "account": f"'{_(category)}'", "indent": 0})
		data.extend(rows)
		total = _total_row(f"Total {category}", rows, periods, currency)
		data.extend([total, {}])
		section_totals[category] = total

	columns = get_columns(filters.periodicity, periods, True, filters.company)
	asset_rows = [section_totals[c] for c in ("Non-current assets", "Current assets")]
	liability_rows = [section_totals[c] for c in ("Non-current liabilities", "Current liabilities")]
	total_assets = _total_row("Total assets", asset_rows, periods, currency)
	total_liabilities = _total_row("Total liabilities", liability_rows, periods, currency)
	data.extend([total_assets, total_liabilities])
	latest = periods[-1].key
	summary = [
		{"label": _("Total assets"), "value": total_assets.get(latest, 0), "datatype": "Currency", "currency": currency},
		{"label": _("Total liabilities"), "value": total_liabilities.get(latest, 0), "datatype": "Currency", "currency": currency},
		{"label": _("Total equity"), "value": section_totals["Equity"].get(latest, 0), "datatype": "Currency", "currency": currency},
	]
	chart = {"data": {"labels": [p.label for p in periods], "datasets": [
		{"name": _("Assets"), "values": [total_assets.get(p.key, 0) for p in periods]},
		{"name": _("Liabilities"), "values": [total_liabilities.get(p.key, 0) for p in periods]},
	]}, "type": "bar", "fieldtype": "Currency", "currency": currency}
	return columns, data, None, chart, summary


def value_for_category(aggregates, category, period_key="total"):
	return sum(flt(row.get(period_key)) for (cat, _), row in aggregates.items() if cat == category)

