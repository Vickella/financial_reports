from frappe import _
from frappe.utils import flt

from financial_reports.reporting import aggregate_accounts, prepare_filters, value_for_category


def _line(aggregates, text):
	return sum(flt(row.get("total")) for (_, line), row in aggregates.items() if text.lower() in line.lower())


def _ratio(numerator, denominator, multiplier=1):
	return numerator / denominator * multiplier if denominator else None


def execute(filters=None):
	filters = prepare_filters(filters)
	pl_filters = filters.copy()
	pl_filters.accumulated_values = 0
	_, pnl, _ = aggregate_accounts(pl_filters, ("Income", "Expense"))
	bs_filters = filters.copy()
	bs_filters.accumulated_values = 1
	_, position, _ = aggregate_accounts(bs_filters, ("Asset", "Liability", "Equity"))
	revenue = _line(pnl, "Revenue from contracts")
	cost_of_sales = _line(pnl, "Cost of sales")
	operating_profit = value_for_category(pnl, "Operating")
	profit = sum(value_for_category(pnl, c) for c in ("Operating", "Investing", "Financing", "Income taxes", "Discontinued operations"))
	current_assets = value_for_category(position, "Current assets")
	current_liabilities = value_for_category(position, "Current liabilities")
	assets = current_assets + value_for_category(position, "Non-current assets")
	liabilities = current_liabilities + value_for_category(position, "Non-current liabilities")
	equity = value_for_category(position, "Equity")
	inventory = _line(position, "Inventories")
	metrics = [
		("Working capital", current_assets - current_liabilities, "Currency", "Current assets - current liabilities"),
		("Current ratio", _ratio(current_assets, current_liabilities), "Ratio", "Current assets / current liabilities"),
		("Quick ratio", _ratio(current_assets - inventory, current_liabilities), "Ratio", "(Current assets - inventory) / current liabilities"),
		("Debt to equity", _ratio(liabilities, equity), "Ratio", "Total liabilities / equity"),
		("Gross margin", _ratio(revenue + cost_of_sales, revenue, 100), "%", "Gross profit / revenue"),
		("Operating margin", _ratio(operating_profit, revenue, 100), "%", "Operating profit / revenue"),
		("Net profit margin", _ratio(profit, revenue, 100), "%", "Profit / revenue"),
		("Return on assets", _ratio(profit, assets, 100), "%", "Profit / total assets"),
		("Return on equity", _ratio(profit, equity, 100), "%", "Profit / equity"),
		("Asset turnover", _ratio(revenue, assets), "Ratio", "Revenue / total assets"),
	]
	data = [{"metric": _(name), "value": value, "unit": unit, "formula": formula} for name, value, unit, formula in metrics]
	columns = [
		{"fieldname":"metric","label":_("Metric"),"fieldtype":"Data","width":220},
		{"fieldname":"value","label":_("Value"),"fieldtype":"Float","precision":2,"width":140},
		{"fieldname":"unit","label":_("Unit"),"fieldtype":"Data","width":100},
		{"fieldname":"formula","label":_("Formula"),"fieldtype":"Data","width":360}
	]
	return columns, data

