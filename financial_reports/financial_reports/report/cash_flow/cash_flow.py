from copy import deepcopy

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.cash_flow.cash_flow import execute as erpnext_cash_flow
from erpnext.accounts.report.financial_statements import get_cost_centers_with_children

from financial_reports.reporting import aggregate_accounts, currency_for, get_periods, prepare_filters, value_for_category


def _period_value_key(columns, data):
	reserved = {"section", "section_name", "account", "account_name", "currency", "total"}
	for column in columns:
		fieldname = column.get("fieldname") if isinstance(column, dict) else None
		if fieldname and fieldname not in reserved and any(fieldname in row for row in data if row):
			return fieldname
	frappe.throw(_("Unable to identify the cash flow value column."))


def _run_period(filters, from_date, to_date):
	period_filters = frappe._dict(deepcopy(dict(filters)))
	period_filters.comparison_enabled = 0
	period_filters.filter_based_on = "Date Range"
	period_filters.period_start_date = from_date
	period_filters.period_end_date = to_date
	period_filters.periodicity = "Yearly"
	period_filters.accumulated_values = 0
	period_filters.show_opening_and_closing_balance = 0
	result = list(erpnext_cash_flow(period_filters))
	return result, _period_value_key(result[0], result[1])


def _row_key(row):
	label = str(
		row.get("account_name") or row.get("section_name") or row.get("section") or ""
	).strip("'")
	parent = str(row.get("parent_section") or "").strip("'")
	return (label, parent) if label else None


def _period_rows(rows, value_key):
	"""Collapse ERPNext spacer/duplicate rows into a stable keyed statement."""
	ordered_keys = []
	normalised = {}
	for source in rows:
		if not source:
			continue
		key = _row_key(source)
		if not key:
			continue
		value = flt(source.get(value_key))
		if key not in normalised:
			normalised[key] = deepcopy(source)
			normalised[key][value_key] = value
			ordered_keys.append(key)
		elif abs(value) > abs(flt(normalised[key].get(value_key))):
			normalised[key].update(deepcopy(source))
			normalised[key][value_key] = value
	return ordered_keys, normalised


def _comparative_cash_flow(filters):
	comparison, comparison_key = _run_period(
		filters, filters.comparison_from_date, filters.comparison_to_date
	)
	current, current_key = _run_period(filters, filters.period_start_date, filters.period_end_date)
	currency = currency_for(filters)
	period_labels = {period.key: period.label for period in get_periods(filters)}
	comparison_order, comparison_rows = _period_rows(comparison[1], comparison_key)
	current_order, current_rows = _period_rows(current[1], current_key)
	ordered_keys = current_order + [key for key in comparison_order if key not in current_rows]
	data = []
	for key in ordered_keys:
		comparison_row = comparison_rows.get(key, {})
		current_row = current_rows.get(key, {})
		row = deepcopy(current_row or comparison_row)
		row["comparative_period"] = flt(comparison_row.get(comparison_key))
		row["current_period"] = flt(current_row.get(current_key))
		row["total"] = row["current_period"]
		data.append(row)
	columns = [
		{"fieldname": "section", "label": _("Cash flow"), "fieldtype": "Data", "width": 360},
		{
			"fieldname": "comparative_period",
			"label": period_labels["comparative_period"],
			"fieldtype": "Currency", "options": "currency", "width": 190,
		},
		{
			"fieldname": "current_period",
			"label": period_labels["current_period"],
			"fieldtype": "Currency", "options": "currency", "width": 190,
		},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "hidden": 1},
	]
	labels = [row.get("section", "").replace("'", "") for row in data if row.get("section_name") and not row.get("parent_section")]
	values = [row.get("current_period", 0) for row in data if row.get("section_name") and not row.get("parent_section")]
	chart = {"data": {"labels": labels, "datasets": [{"name": _("Current period"), "values": values}]},
		"type": "bar", "fieldtype": "Currency", "currency": currency}
	return [columns, data, None, chart, current[4] if len(current) > 4 else None]


def _reconcile_from_operating_profit(result, filters):
	data = result[1]
	periods, aggregates, account_rows = aggregate_accounts(filters, ("Income", "Expense"))
	profit_row = next(
		(row for row in data if str(row.get("account_name", "")).replace("'", "") == _("Profit for the year")),
		None,
	)
	if not profit_row:
		return
	reconciliation = deepcopy(profit_row)
	reconciliation_label = _("Results outside the operating category")
	reconciliation.update({
		"account_name": reconciliation_label,
		"account": reconciliation_label,
		"section": reconciliation_label,
		"indent": 1,
	})
	for period in periods:
		operating = value_for_category(aggregates, "Operating", period.key)
		reconciliation[period.key] = flt(profit_row.get(period.key)) - operating
		profit_row[period.key] = operating
	profit_row["total"] = profit_row.get("current_period", sum(flt(profit_row.get(p.key)) for p in periods))
	reconciliation["total"] = reconciliation.get(
		"current_period", sum(flt(reconciliation.get(p.key)) for p in periods)
	)
	profit_row["account_name"] = _("Operating profit")
	profit_row["account"] = profit_row["account_name"]
	profit_row["section"] = profit_row["account_name"]
	profit_row["is_emphasis"] = 1
	data.insert(data.index(profit_row) + 1, reconciliation)


_CASH_FLOW_LABELS = {
	"Cash Flow from Operations": "Operating activities",
	"Net Cash from Operations": "Net cash flows from operating activities",
	"Cash Flow from Investing": "Investing activities",
	"Net Cash from Investing": "Net cash flows from investing activities",
	"Cash Flow from Financing": "Financing activities",
	"Net Cash from Financing": "Net cash flows from financing activities",
	"Net Change in Cash": "Net increase/(decrease) in cash and cash equivalents",
	"Opening": "Cash and cash equivalents at beginning of period",
	"Closing (Opening + Total)": "Cash and cash equivalents at end of period",
	"Net Change in Accounts Receivable": "Decrease/(increase) in trade and other receivables",
	"Net Change in Accounts Payable": "Increase/(decrease) in trade and other payables",
	"Net Change in Inventory": "Decrease/(increase) in inventories",
	"Net Change in Fixed Asset": "Net cash movement in property, plant and equipment",
	"Net Change in Equity": "Net cash movement in equity",
}
_CASH_FLOW_TOTALS = {
	"Net Cash from Operations", "Net Cash from Investing", "Net Cash from Financing",
	"Net Change in Cash", "Closing (Opening + Total)",
}


def _set_visible_label(row, label, quoted=False):
	value = f"'{label}" if quoted else label
	for fieldname in ("section", "section_name", "account_name", "account"):
		if row.get(fieldname):
			row[fieldname] = value


def _polish_cash_flow(result):
	data = result[1]
	for row in data:
		original = str(row.get("section") or row.get("account_name") or "").strip("'")
		if original in _CASH_FLOW_LABELS:
			is_section = original.startswith("Cash Flow from ")
			_set_visible_label(row, _(_CASH_FLOW_LABELS[original]), quoted=is_section)
		if original in _CASH_FLOW_TOTALS:
			row["is_total"] = 1
			row["indent"] = 0

	profit_index = next((index for index, row in enumerate(data) if row.get("is_emphasis")), None)
	if profit_index is not None:
		data.insert(profit_index + 1, {
			"section": "'" + _("Adjustments to reconcile operating profit to net cash flows:"),
			"account_name": "'" + _("Adjustments to reconcile operating profit to net cash flows:"),
		})
	working_capital_index = next((
		index for index, row in enumerate(data)
		if str(row.get("section", "")).strip("'") == _("Decrease/(increase) in trade and other receivables")
	), None)
	if working_capital_index is not None:
		data.insert(working_capital_index, {
			"section": "'" + _("Working capital changes:"),
			"account_name": "'" + _("Working capital changes:"),
		})


def _cash_accounts(filters):
	accounts = []
	for account in frappe.get_all(
		"Account", filters={"company": filters.company, "is_group": 0},
		fields=["name", "account_type", "custom_ifrs18_line_item"],
		limit_page_length=0,
	):
		line_item = str(account.custom_ifrs18_line_item or "").lower()
		if account.account_type in ("Cash", "Bank") or "cash and cash equivalent" in line_item:
			accounts.append(account.name)
	return accounts


def _cash_balance(filters, posting_date):
	accounts = _cash_accounts(filters)
	if not accounts:
		return 0
	# Aggregate in SQL so historic balance checks remain bounded on large ledgers.
	balances = frappe.get_all(
		"GL Entry",
		filters={
			"company": filters.company, "posting_date": ["<=", posting_date],
			"is_cancelled": 0, "account": ["in", accounts],
		},
		fields=["finance_book", "sum(debit) as debit", "sum(credit) as credit"],
		group_by="finance_book",
		limit_page_length=0,
	)
	allowed_books = _allowed_finance_books(filters)
	return sum(
		flt(balance.debit) - flt(balance.credit)
		for balance in balances if balance.finance_book in allowed_books
	)


def _account_cash_flow_activity(account):
	if account.custom_ifrs18_cash_flow_activity in ("Operating", "Investing", "Financing"):
		return account.custom_ifrs18_cash_flow_activity
	if account.custom_ifrs18_category in ("Operating", "Investing", "Financing"):
		return account.custom_ifrs18_category
	if account.account_type == "Fixed Asset" or account.root_type == "Equity":
		return "Investing" if account.root_type == "Asset" else "Financing"
	if account.account_type in ("Receivable", "Payable", "Stock", "Tax"):
		return "Operating"
	if account.root_type == "Liability":
		return "Financing"
	if account.root_type in ("Income", "Expense"):
		return "Operating"
	return "Unclassified"


def _allowed_finance_books(filters):
	selected = filters.get("finance_book") or ""
	default_book = (
		frappe.get_cached_value("Company", filters.company, "default_finance_book")
		or ""
	)
	if (
		filters.get("include_default_book_entries")
		and selected
		and default_book
		and selected != default_book
	):
		frappe.throw(
			_("To use a different finance book, uncheck Include Default FB Entries.")
		)
	allowed = {selected, "", None}
	if filters.get("include_default_book_entries"):
		allowed.add(default_book)
	return allowed


def _direct_cash_by_activity(filters, from_date, to_date):
	accounts = frappe.get_all(
		"Account", filters={"company": filters.company, "is_group": 0},
		fields=[
			"name", "account_name", "root_type", "account_type", "custom_ifrs18_category",
			"custom_ifrs18_line_item", "custom_ifrs18_cash_flow_activity",
		],
		limit_page_length=0,
	)
	account_by_name = {account.name: account for account in accounts}
	cash_accounts = {
		account.name for account in accounts
		if account.account_type in ("Cash", "Bank")
		or "cash and cash equivalent" in str(account.custom_ifrs18_line_item or "").lower()
	}
	movements = {"Operating": 0, "Investing": 0, "Financing": 0, "Unclassified": 0}
	details = {}
	if not cash_accounts:
		return movements, details
	allowed_books = _allowed_finance_books(filters)
	fields = [
		"voucher_type", "voucher_no", "account", "debit", "credit",
		"cost_center", "project", "finance_book",
	]
	cash_entries = frappe.get_all(
		"GL Entry", filters={
			"company": filters.company, "posting_date": ["between", [from_date, to_date]],
			"is_cancelled": 0, "account": ["in", cash_accounts],
		}, fields=fields, limit_page_length=0,
	)
	cash_entries = [
		entry for entry in cash_entries if entry.finance_book in allowed_books
	]
	voucher_keys = {(entry.voucher_type, entry.voucher_no) for entry in cash_entries}
	if not voucher_keys:
		return movements, details

	# Query only counterpart rows of vouchers that moved cash. Chunks avoid
	# oversized SQL IN clauses for high-volume, long-range reports.
	counterparts = {}
	voucher_numbers = sorted({voucher_no for _voucher_type, voucher_no in voucher_keys})
	for start in range(0, len(voucher_numbers), 500):
		entries = frappe.get_all(
			"GL Entry",
			filters={
				"company": filters.company,
				"posting_date": ["between", [from_date, to_date]],
				"is_cancelled": 0,
				"voucher_no": ["in", voucher_numbers[start:start + 500]],
			},
			fields=fields,
			limit_page_length=0,
		)
		for entry in entries:
			key = (entry.voucher_type, entry.voucher_no)
			if key not in voucher_keys or entry.account in cash_accounts:
				continue
			if entry.finance_book not in allowed_books:
				continue
			counterparts.setdefault(key, []).append(entry)
	cost_centers = filters.get("cost_center") or []
	if cost_centers:
		cost_centers = get_cost_centers_with_children(cost_centers)
	projects = filters.get("project") or []
	if isinstance(projects, str):
		projects = frappe.parse_json(projects)
		if isinstance(projects, str):
			projects = [projects]
	for cash_entry in cash_entries:
		rows = counterparts.get((cash_entry.voucher_type, cash_entry.voucher_no), [])
		total_weight = sum(abs(flt(row.debit) - flt(row.credit)) for row in rows)
		selected_rows = [
			row for row in rows
			if (not cost_centers or row.cost_center in cost_centers)
			and (not projects or row.project in projects)
		]
		selected_weight = sum(abs(flt(row.debit) - flt(row.credit)) for row in selected_rows)
		cash_movement = flt(cash_entry.debit) - flt(cash_entry.credit)
		if not total_weight or not selected_weight:
			if not cost_centers and not projects:
				movements["Unclassified"] += cash_movement
			continue
		selected_cash = cash_movement * selected_weight / total_weight
		for row in selected_rows:
			account = account_by_name[row.account]
			activity = _account_cash_flow_activity(account)
			weight = abs(flt(row.debit) - flt(row.credit))
			allocated_cash = selected_cash * weight / selected_weight
			movements[activity] += allocated_cash
			line_item = (
				account.custom_ifrs18_line_item
				or account.account_name
				or account.name
			)
			key = (activity, line_item)
			details[key] = details.get(key, 0) + allocated_cash
	return movements, details


def _replace_direct_activity_rows(
	data, total_rows, periods, detail_rows, currency
):
	for activity in ("Investing", "Financing"):
		heading_label = _("{0} activities").format(activity)
		heading = next(
			(
				row
				for row in data
				if str(row.get("section", "")).strip("'") == heading_label
			),
			None,
		)
		total_row = total_rows[activity]
		if not heading or total_row not in data:
			continue
		start = data.index(heading) + 1
		end = data.index(total_row)
		del data[start:end]
		rows = []
		for (row_activity, line_item), values in sorted(detail_rows.items()):
			if row_activity != activity:
				continue
			row = {
				"section": _(line_item),
				"section_name": _(line_item),
				"indent": 1,
				"currency": currency,
			}
			for period in periods:
				row[period.key] = values.get(period.key, 0)
			rows.append(row)
		for offset, row in enumerate(rows):
			data.insert(start + offset, row)


def _reconcile_cash_balances(result, filters):
	data = result[1]
	periods = get_periods(filters)
	currency = currency_for(filters)
	labels = {
		"Operating": _("Net cash flows from operating activities"),
		"Investing": _("Net cash flows from investing activities"),
		"Financing": _("Net cash flows from financing activities"),
	}
	total_rows = {
		activity: next((
			row for row in data if str(row.get("section", "")).strip("'") == label
		), None)
		for activity, label in labels.items()
	}
	net_label = _("Net increase/(decrease) in cash and cash equivalents")
	net_row = next((row for row in data if str(row.get("section", "")).strip("'") == net_label), None)
	if not net_row or any(row is None for row in total_rows.values()):
		return
	adjustments = {
		activity: {
			"section": _("Other {0} cash movements and reconciliation adjustments").format(activity.lower()),
			"section_name": _("Other {0} cash movements and reconciliation adjustments").format(activity.lower()),
			"indent": 1, "currency": currency,
		}
		for activity in labels
	}
	adjustments["Operating"]["section"] = _("Other non-cash and operating working capital movements")
	adjustments["Operating"]["section_name"] = adjustments["Operating"]["section"]
	detail_rows = {}
	pending = {
		"section": _("Cash movements pending activity classification"),
		"section_name": _("Cash movements pending activity classification"),
		"indent": 1, "currency": currency,
	}
	opening = {
		"section": _("Cash and cash equivalents at beginning of period"),
		"section_name": _("Cash and cash equivalents at beginning of period"),
		"currency": currency,
	}
	closing = {
		"section": _("Cash and cash equivalents at end of period"),
		"section_name": _("Cash and cash equivalents at end of period"),
		"currency": currency, "is_total": 1,
	}
	segmented = bool(filters.get("cost_center") or filters.get("project"))
	for period in periods:
		direct, details = _direct_cash_by_activity(filters, period.from_date, period.to_date)
		for detail_key, amount in details.items():
			detail_rows.setdefault(detail_key, {})[period.key] = amount
		for activity, total_row in total_rows.items():
			adjustments[activity][period.key] = direct[activity] - flt(total_row.get(period.key))
			total_row[period.key] = direct[activity]
		pending[period.key] = direct["Unclassified"]
		if segmented:
			net_row[period.key] = sum(direct.values())
			continue
		opening_amount = _cash_balance(filters, frappe.utils.add_days(period.from_date, -1))
		closing_amount = _cash_balance(filters, period.to_date)
		net_row[period.key] = closing_amount - opening_amount
		opening[period.key] = opening_amount
		closing[period.key] = closing_amount
	_replace_direct_activity_rows(
		data, total_rows, periods, detail_rows, currency
	)
	row = adjustments["Operating"]
	if any(abs(flt(row.get(period.key))) > 0.005 for period in periods):
		data.insert(data.index(total_rows["Operating"]), row)
	if any(abs(flt(pending.get(period.key))) > 0.005 for period in periods):
		data.insert(data.index(net_row), pending)
	if filters.get("show_opening_and_closing_balance") and not segmented:
		data.extend([opening, closing])


def execute(filters=None):
	"""IFRS 18 / amended IAS 7 indirect cash flow beginning with operating profit."""
	filters = prepare_filters(filters)
	filters.setdefault("show_opening_and_closing_balance", 1)
	result = _comparative_cash_flow(filters) if filters.get("comparison_enabled") else list(
		erpnext_cash_flow(deepcopy(filters))
	)
	if not filters.get("comparison_enabled"):
		value_key = _period_value_key(result[0], result[1])
		order, rows = _period_rows(result[1], value_key)
		result[1] = [rows[key] for key in order]
	_reconcile_from_operating_profit(result, filters)
	_polish_cash_flow(result)
	_reconcile_cash_balances(result, filters)
	return tuple(result)
