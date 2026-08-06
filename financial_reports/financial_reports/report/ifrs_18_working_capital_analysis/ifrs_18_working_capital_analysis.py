from frappe import _

from financial_reports.reporting import aggregate_accounts, currency_for, prepare_filters


def execute(filters=None):
	filters = prepare_filters(filters, accumulated_values=True)
	filters.accumulated_values = 1
	periods, aggregates, account_rows = aggregate_accounts(filters, ("Asset", "Liability"))
	currency = currency_for(filters)
	data = []
	for (category, line_item), values in aggregates.items():
		if category not in ("Current assets", "Current liabilities"):
			continue
		row = {"category": category, "line_item": line_item, "currency": currency}
		row.update({p.key: values.get(p.key, 0) for p in periods})
		row["total"] = values.get("total", 0)
		data.append(row)
	columns = [
		{"fieldname":"category","label":_("Category"),"fieldtype":"Data","width":180},
		{"fieldname":"line_item","label":_("Line item"),"fieldtype":"Data","width":260},
	]
	for period in periods:
		columns.append({"fieldname":period.key,"label":period.label,"fieldtype":"Currency","options":"currency","width":150})
	current_assets = sum(row.get(periods[-1].key, 0) for row in data if row["category"] == "Current assets")
	current_liabilities = sum(row.get(periods[-1].key, 0) for row in data if row["category"] == "Current liabilities")
	summary = [
		{"label":_("Working capital"),"value":current_assets-current_liabilities,"datatype":"Currency","currency":currency},
		{"label":_("Current ratio"),"value":current_assets/current_liabilities if current_liabilities else 0,"datatype":"Float"},
	]
	return columns, data, None, None, summary

