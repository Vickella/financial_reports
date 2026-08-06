from frappe import _
from frappe.utils import flt

from financial_reports.reporting import aggregate_accounts, get_periods, prepare_filters, value_for_category


def _line(aggregates, text, period_key):
	return sum(flt(row.get(period_key)) for (_, line), row in aggregates.items() if text.lower() in line.lower())


def _ratio(numerator, denominator, multiplier=1):
	return numerator / denominator * multiplier if denominator else None


def _metrics(pnl, position, period_key):
	revenue = _line(pnl, "Revenue from contracts", period_key)
	cost_of_sales = _line(pnl, "Cost of sales", period_key)
	operating_profit = value_for_category(pnl, "Operating", period_key)
	profit = sum(value_for_category(pnl, category, period_key) for category in (
		"Operating", "Investing", "Financing", "Income taxes", "Discontinued operations"
	))
	current_assets = value_for_category(position, "Current assets", period_key)
	current_liabilities = value_for_category(position, "Current liabilities", period_key)
	assets = current_assets + value_for_category(position, "Non-current assets", period_key)
	liabilities = current_liabilities + value_for_category(position, "Non-current liabilities", period_key)
	equity = value_for_category(position, "Equity", period_key) + profit
	inventory = _line(position, "Inventories", period_key)
	return {
		"Working capital": current_assets - current_liabilities,
		"Current ratio": _ratio(current_assets, current_liabilities),
		"Quick ratio": _ratio(current_assets - inventory, current_liabilities),
		"Debt to equity": _ratio(liabilities, equity),
		"Gross margin": _ratio(revenue + cost_of_sales, revenue, 100),
		"Operating margin": _ratio(operating_profit, revenue, 100),
		"Net profit margin": _ratio(profit, revenue, 100),
		"Return on assets": _ratio(profit, assets, 100),
		"Return on equity": _ratio(profit, equity, 100),
		"Asset turnover": _ratio(revenue, assets),
	}


def execute(filters=None):
	filters = prepare_filters(filters)
	periods = get_periods(filters)
	pl_filters = filters.copy()
	pl_filters.accumulated_values = 0
	pnl_periods, pnl, pnl_accounts = aggregate_accounts(pl_filters, ("Income", "Expense"))
	bs_filters = filters.copy()
	bs_filters.accumulated_values = 1
	position_periods, position, position_accounts = aggregate_accounts(bs_filters, ("Asset", "Liability", "Equity"))
	period_metrics = {period.key: _metrics(pnl, position, period.key) for period in periods}
	definitions = {
		"Working capital": ("Currency", "Current assets - current liabilities"),
		"Current ratio": ("Ratio", "Current assets / current liabilities"),
		"Quick ratio": ("Ratio", "(Current assets - inventory) / current liabilities"),
		"Debt to equity": ("Ratio", "Total liabilities / equity including current earnings"),
		"Gross margin": ("%", "Gross profit / revenue"),
		"Operating margin": ("%", "Operating profit / revenue"),
		"Net profit margin": ("%", "Profit / revenue"),
		"Return on assets": ("%", "Profit / total assets"),
		"Return on equity": ("%", "Profit / equity including current earnings"),
		"Asset turnover": ("Ratio", "Revenue / total assets"),
	}
	data = []
	for metric, (unit, formula) in definitions.items():
		row = {"metric": _(metric), "unit": unit, "formula": formula}
		for period in periods:
			row[period.key] = period_metrics[period.key][metric]
		if len(periods) == 2:
			current = row.get(periods[-1].key)
			comparative = row.get(periods[0].key)
			row["change"] = current - comparative if current is not None and comparative is not None else None
		data.append(row)
	columns = [{"fieldname":"metric","label":_("Metric"),"fieldtype":"Data","width":220}]
	columns.extend({"fieldname":period.key,"label":period.label,"fieldtype":"Float","precision":2,"width":190} for period in periods)
	if len(periods) == 2:
		columns.append({"fieldname":"change","label":_("Change"),"fieldtype":"Float","precision":2,"width":120})
	columns.extend([
		{"fieldname":"unit","label":_("Unit"),"fieldtype":"Data","width":90},
		{"fieldname":"formula","label":_("Formula"),"fieldtype":"Data","width":360},
	])
	return columns, data
