from financial_reports.reporting import (
	OCI_CATEGORIES,
	_total_row,
	aggregate_accounts,
	category_rows,
	currency_for,
	prepare_filters,
	profit_or_loss,
)


def execute(filters=None):
	filters = prepare_filters(filters)
	columns, data, _, _, _ = profit_or_loss(filters)
	periods, aggregates, _ = aggregate_accounts(filters, ("Income", "Expense"))
	currency = currency_for(filters)
	profit_total = next((row for row in reversed(data) if row.get("account_name") == "'Profit'"), None)
	oci_rows = []
	data.append({"account_name": "'Other comprehensive income'", "account": "'Other comprehensive income'"})
	for category in OCI_CATEGORIES:
		rows = category_rows(aggregates, category, periods, currency)
		if rows:
			data.append({"account_name": f"'{category}'", "account": f"'{category}'", "indent": 1})
			for row in rows:
				row["indent"] = 2
			data.extend(rows)
			oci_rows.extend(rows)
	oci_total = _total_row("Other comprehensive income, net of tax", oci_rows, periods, currency)
	total_rows = ([profit_total] if profit_total else []) + oci_rows
	total = _total_row("Total comprehensive income", total_rows, periods, currency)
	data.extend([oci_total, {}, total])
	summary = [{"label": "Total comprehensive income", "value": total.get("total", 0), "datatype": "Currency", "currency": currency}]
	return columns, data, None, None, summary

