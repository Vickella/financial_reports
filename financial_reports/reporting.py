"""Shared IFRS 18 statement engine built on ERPNext's audited GL utilities."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy

import frappe
from frappe import _
from frappe.utils import flt, getdate

from erpnext.accounts.report.financial_statements import get_columns, get_data, get_period_list
from erpnext.accounts.utils import get_fiscal_year


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

LINE_ITEM_ORDER = {
	"Operating": (
		"revenue from contracts", "revenue", "cost of sales", "research and development",
		"other operating income", "selling", "distribution", "administrative",
		"depreciation", "impairment", "foreign exchange", "other operating",
	),
	"Investing": ("share of profit", "rental income", "income from investments", "foreign exchange", "fair value", "other"),
	"Financing": ("interest expense on borrowings", "interest expense", "finance cost", "foreign exchange"),
	"Income taxes": ("income tax",),
	"Discontinued operations": ("discontinued",),
	"Non-current assets": (
		"property, plant", "biological", "investment properties", "intangible", "goodwill", "right-of-use",
		"associate", "investments", "financial assets", "deferred tax",
	),
	"Current assets": (
		"inventories", "right of return", "trade and other receivables", "trade receivables",
		"contract assets", "prepayments", "current tax", "other current", "cash", "held for sale",
	),
	"Equity": ("issued capital", "share premium", "treasury", "capital reserves", "retained earnings", "other reserves", "other equity", "non-controlling"),
	"Non-current liabilities": (
		"interest-bearing", "borrowings", "financial liabilities", "decommissioning",
		"restructuring", "provisions", "government grants", "contract liabilities",
		"employee", "deferred tax",
	),
	"Current liabilities": (
		"trade and other payables", "trade payables", "contract liabilities", "refund liabilities",
		"interest-bearing", "borrowings", "financial liabilities", "dividends payable",
		"restructuring", "provisions", "government grants", "income tax", "other current",
	),
}


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


def _custom_period_label(from_date, to_date):
	if (
		from_date.year == to_date.year
		and from_date.month == 1
		and from_date.day == 1
		and to_date.month == 12
		and to_date.day == 31
	):
		return str(to_date.year)
	if from_date.year == to_date.year:
		separator = f" {chr(8211)} "
		return f"{from_date:%d %b}{separator}{to_date:%d %b %Y}"
	separator = f" {chr(8211)} "
	return f"{from_date:%d %b %Y}{separator}{to_date:%d %b %Y}"


def get_periods(filters):
	if filters.get("comparison_enabled"):
		required = ("period_start_date", "period_end_date", "comparison_from_date", "comparison_to_date")
		if any(not filters.get(field) for field in required):
			frappe.throw(_("Current and comparative start and end dates are required."))
		current_from = getdate(filters.period_start_date)
		current_to = getdate(filters.period_end_date)
		comparison_from = getdate(filters.comparison_from_date)
		comparison_to = getdate(filters.comparison_to_date)
		if current_to < current_from or comparison_to < comparison_from:
			frappe.throw(_("The end of each reporting range must be on or after its start."))
		earliest = min(current_from, comparison_from)
		latest = max(current_to, comparison_to)
		periods = []
		for key, from_date, to_date in (
			("comparative_period", comparison_from, comparison_to),
			("current_period", current_from, current_to),
		):
			fiscal_year = get_fiscal_year(to_date, company=filters.company)
			periods.append(frappe._dict(
				from_date=from_date,
				to_date=to_date,
				key=key,
				label=_custom_period_label(from_date, to_date),
				year_start_date=earliest,
				year_end_date=latest,
				to_date_fiscal_year=fiscal_year[0],
				from_date_fiscal_year_start_date=fiscal_year[1],
			))
		return periods
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


def statement_columns(filters, periods, accumulated_values=False):
	"""Return clean statutory statement columns from ERPNext's period engine."""
	return get_columns(filters.periodicity, periods, accumulated_values, filters.company)


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
	row["total"] = row.get("current_period") if "current_period" in row else sum(flt(item.get("total")) for item in rows)
	return row


def category_rows(aggregates, category, periods, currency):
	rows = []
	for (mapped_category, line_item), values in aggregates.items():
		if mapped_category != category:
			continue
		row = deepcopy(values)
		row.update({
			"account_name": _(line_item),
			"account": _(line_item),
			"indent": 1,
		})
		rows.append(row)
	order = LINE_ITEM_ORDER.get(category, ())
	def rank(item):
		label = str(item.get("line_item") or item.get("account_name") or "").lower()
		return next((index for index, token in enumerate(order) if token in label), len(order)), label
	rows.sort(key=rank)
	return rows


def _section_row(label, indent=0):
	return {"account_name": f"'{_(label)}'", "account": f"'{_(label)}'", "indent": indent}


def profit_or_loss(filters):
	filters = prepare_filters(filters)
	periods, aggregates, account_rows = aggregate_accounts(filters, ("Income", "Expense"))
	currency = currency_for(filters)
	operating = category_rows(aggregates, "Operating", periods, currency)
	investing = category_rows(aggregates, "Investing", periods, currency)
	financing = category_rows(aggregates, "Financing", periods, currency)
	tax = category_rows(aggregates, "Income taxes", periods, currency)
	discontinued = category_rows(aggregates, "Discontinued operations", periods, currency)

	data = [_section_row("Continuing operations")]
	gross_rows = [
		row for row in operating
		if "revenue" in str(row.get("line_item", "")).lower()
		or "cost of sales" in str(row.get("line_item", "")).lower()
	]
	other_operating = [row for row in operating if row not in gross_rows]
	data.extend(gross_rows)
	if gross_rows:
		data.extend([_total_row("Gross profit", gross_rows, periods, currency), {}])
	data.extend(other_operating)
	operating_total = _total_row("Operating profit", operating, periods, currency)
	data.extend([operating_total, {}])

	cumulative = list(operating)
	cumulative.extend(investing)
	data.extend(investing)
	before_financing = _total_row("Profit before financing and income taxes", cumulative, periods, currency)
	data.extend([before_financing, {}])
	cumulative.extend(financing)
	data.extend(financing)
	before_tax = _total_row("Profit before income tax", cumulative, periods, currency)
	data.extend([before_tax, {}])
	cumulative.extend(tax)
	data.extend(tax)
	continuing_total = _total_row("Profit from continuing operations", cumulative, periods, currency)
	data.extend([continuing_total, {}])
	if discontinued:
		data.append(_section_row("Discontinued operations"))
		data.extend(discontinued)
		cumulative.extend(discontinued)
	profit_total = _total_row("Profit", cumulative, periods, currency)
	data.append(profit_total)

	columns = statement_columns(filters, periods, filters.accumulated_values)
	chart = {
		"data": {
			"labels": [p.label for p in periods],
			"datasets": [
				{"name": _("Operating profit"), "values": [operating_total.get(p.key, 0) for p in periods]},
				{"name": _("Profit"), "values": [profit_total.get(p.key, 0) for p in periods]},
			],
		},
		"type": "bar", "fieldtype": "Currency", "currency": currency,
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
	periods, aggregates, account_rows = aggregate_accounts(filters, ("Asset", "Liability", "Equity"))
	currency = currency_for(filters)
	category_data = {category: category_rows(aggregates, category, periods, currency) for category in POSITION_ORDER}

	profit_row = {
		"account_name": _("Unclosed and current-period earnings"),
		"account": _("Unclosed and current-period earnings"),
		"line_item": _("Unclosed and current-period earnings"), "currency": currency, "indent": 1,
	}
	for period in periods:
		asset_balance = sum(
			flt(row.get(period.key))
			for category in ("Non-current assets", "Current assets")
			for row in category_data[category]
		)
		liability_balance = sum(
			flt(row.get(period.key))
			for category in ("Non-current liabilities", "Current liabilities")
			for row in category_data[category]
		)
		mapped_equity = sum(flt(row.get(period.key)) for row in category_data["Equity"])
		profit_row[period.key] = asset_balance - liability_balance - mapped_equity
	profit_row["total"] = profit_row.get("current_period", profit_row.get(periods[-1].key, 0))
	category_data["Equity"].append(profit_row)

	section_totals = {
		category: _total_row(f"Total {category.lower()}", rows, periods, currency)
		for category, rows in category_data.items()
	}
	data = [_section_row("Assets")]
	for category in ("Non-current assets", "Current assets"):
		data.append(_section_row(category))
		data.extend(category_data[category])
		data.extend([section_totals[category], {}])
	total_assets = _total_row(
		"Total assets", [section_totals["Non-current assets"], section_totals["Current assets"]],
		periods, currency,
	)
	data.extend([total_assets, {}, _section_row("Equity and liabilities")])

	data.append(_section_row("Equity"))
	data.extend(category_data["Equity"])
	total_equity = section_totals["Equity"]
	data.extend([total_equity, {}])
	for category in ("Non-current liabilities", "Current liabilities"):
		data.append(_section_row(category))
		data.extend(category_data[category])
		data.extend([section_totals[category], {}])
	total_liabilities = _total_row(
		"Total liabilities", [section_totals["Non-current liabilities"], section_totals["Current liabilities"]],
		periods, currency,
	)
	total_equity_and_liabilities = _total_row(
		"Total equity and liabilities", [total_equity, total_liabilities], periods, currency,
	)
	data.extend([total_liabilities, total_equity_and_liabilities])

	columns = statement_columns(filters, periods, True)
	latest = periods[-1].key
	summary = [
		{"label": _("Total assets"), "value": total_assets.get(latest, 0), "datatype": "Currency", "currency": currency},
		{"label": _("Total liabilities"), "value": total_liabilities.get(latest, 0), "datatype": "Currency", "currency": currency},
		{"label": _("Total equity"), "value": total_equity.get(latest, 0), "datatype": "Currency", "currency": currency},
	]
	chart = {"data": {"labels": [p.label for p in periods], "datasets": [
		{"name": _("Assets"), "values": [total_assets.get(p.key, 0) for p in periods]},
		{"name": _("Liabilities"), "values": [total_liabilities.get(p.key, 0) for p in periods]},
	]}, "type": "bar", "fieldtype": "Currency", "currency": currency}
	return columns, data, None, chart, summary

def value_for_category(aggregates, category, period_key="total"):
	return sum(flt(row.get(period_key)) for (cat, _), row in aggregates.items() if cat == category)

