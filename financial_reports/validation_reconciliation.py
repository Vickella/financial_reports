"""Read-only GL to Trial Balance to IFRS statement reconciliation."""

from __future__ import annotations

import frappe
from frappe.utils import flt, getdate

from erpnext.accounts.report.trial_balance import trial_balance
from erpnext.accounts.utils import get_fiscal_year

from financial_reports.reporting import aggregate_accounts, financial_position


PPE_LINE_ITEM = "Property, plant and equipment"


def _close(value):
	return round(flt(value), 6)


def _ppe_report_value(rows, period_key):
	return sum(
		flt(row.get(period_key))
		for row in rows
		if PPE_LINE_ITEM.lower() in str(row.get("line_item") or row.get("account_name") or "").lower()
		and not row.get("is_total")
	)


def reconcile_ppe(company=None, from_date=None, to_date=None):
	"""Reconcile PPE and all non-zero asset accounts without changing any records."""
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company")
	to_date = getdate(to_date or frappe.db.get_value(
		"GL Entry", {"company": company, "is_cancelled": 0}, "max(posting_date)"
	))
	fiscal_year = get_fiscal_year(to_date, company=company)
	from_date = getdate(from_date or fiscal_year[1])

	statement_filters = frappe._dict({
		"company": company,
		"filter_based_on": "Date Range",
		"period_start_date": from_date,
		"period_end_date": to_date,
		"periodicity": "Yearly",
		"accumulated_values": 1,
		"include_default_book_entries": 1,
		"show_zero_values": 1,
	})
	periods, aggregates, account_rows = aggregate_accounts(statement_filters, ("Asset",))
	period_key = periods[-1].key
	_, statement_rows, _, _, _ = financial_position(statement_filters)

	asset_accounts = frappe.db.sql(
		"""
		select a.name, a.account_name, a.account_type, a.custom_ifrs18_category category,
			a.custom_ifrs18_line_item line_item,
			coalesce(sum(case when gle.posting_date <= %(to_date)s then gle.debit-gle.credit else 0 end), 0) ledger_balance,
			coalesce(sum(case when gle.posting_date between %(from_date)s and %(to_date)s
				then gle.debit-gle.credit else 0 end), 0) period_movement,
			count(case when gle.posting_date <= %(to_date)s then 1 end) gl_rows
		from `tabAccount` a
		left join `tabGL Entry` gle on gle.account=a.name and gle.company=a.company and gle.is_cancelled=0
		where a.company=%(company)s and a.root_type='Asset' and a.is_group=0
		group by a.name, a.account_name, a.account_type,
			a.custom_ifrs18_category, a.custom_ifrs18_line_item
		having abs(ledger_balance) > 0.000001
		order by a.custom_ifrs18_category, a.custom_ifrs18_line_item, a.name
		""",
		{"company": company, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	tb_filters = frappe._dict({
		"company": company,
		"fiscal_year": fiscal_year[0],
		"from_date": from_date,
		"to_date": to_date,
		"show_zero_values": 1,
		"show_unclosed_fy_pl_balances": 0,
		"include_default_book_entries": 1,
		"with_period_closing_entry_for_current_period": 0,
		"show_net_values": 0,
	})
	_, tb_rows = trial_balance.execute(tb_filters)
	tb_by_account = {
		row.get("account"): flt(row.get("closing_debit")) - flt(row.get("closing_credit"))
		for row in (tb_rows or [])
		if row.get("account")
	}
	engine_by_account = {
		row.get("account"): flt(row.get(period_key))
		for row, _mapping, _factor in account_rows
	}

	for row in asset_accounts:
		row["ledger_balance"] = _close(row.ledger_balance)
		row["period_movement"] = _close(row.period_movement)
		row["trial_balance"] = _close(tb_by_account.get(row.name))
		row["ifrs_engine"] = _close(engine_by_account.get(row.name))
		row["ledger_to_tb_difference"] = _close(row.ledger_balance - row.trial_balance)
		row["tb_to_ifrs_difference"] = _close(row.trial_balance - row.ifrs_engine)

	ppe_accounts = [
		row for row in asset_accounts
		if PPE_LINE_ITEM.lower() in str(row.line_item or "").lower()
	]
	ppe_aggregate = sum(
		flt(values.get(period_key))
		for (_category, line_item), values in aggregates.items()
		if PPE_LINE_ITEM.lower() in str(line_item or "").lower()
	)
	totals = {
		"ledger": _close(sum(row.ledger_balance for row in ppe_accounts)),
		"trial_balance": _close(sum(row.trial_balance for row in ppe_accounts)),
		"ifrs_engine": _close(sum(row.ifrs_engine for row in ppe_accounts)),
		"ifrs_aggregate": _close(ppe_aggregate),
		"displayed_report": _close(_ppe_report_value(statement_rows, period_key)),
	}
	totals["ledger_to_tb_difference"] = _close(totals["ledger"] - totals["trial_balance"])
	totals["tb_to_report_difference"] = _close(totals["trial_balance"] - totals["displayed_report"])

	entries = frappe.db.sql(
		"""
		select gle.posting_date, gle.account, gle.voucher_type, gle.voucher_no,
			gle.debit, gle.credit, gle.is_opening, gle.finance_book
		from `tabGL Entry` gle
		inner join `tabAccount` a on a.name=gle.account
		where gle.company=%(company)s and gle.is_cancelled=0
		and gle.posting_date <= %(to_date)s
		and lower(coalesce(a.custom_ifrs18_line_item, '')) like %(ppe)s
		order by gle.posting_date, gle.account, gle.voucher_no
		""",
		{"company": company, "to_date": to_date, "ppe": f"%{PPE_LINE_ITEM.lower()}%"},
		as_dict=True,
	)
	return {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"fiscal_year": fiscal_year[0],
		"period_key": period_key,
		"ppe_totals": totals,
		"ppe_accounts": ppe_accounts,
		"nonzero_asset_accounts": asset_accounts,
		"ppe_gl_entries": entries,
	}

def _statement_value(rows, label, period_key):
	for row in rows:
		candidate = str(row.get("line_item") or row.get("account_name") or "").strip("'")
		if candidate == label:
			return flt(row.get(period_key))
	raise AssertionError(f"Statement line not found: {label}")


def reconcile_all_statements(company=None, from_date=None, to_date=None):
	"""Reconcile every non-zero account from GL through TB and the primary statements."""
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company")
	to_date = getdate(to_date or frappe.db.get_value(
		"GL Entry", {"company": company, "is_cancelled": 0}, "max(posting_date)"
	))
	fiscal_year = get_fiscal_year(to_date, company=company)
	from_date = getdate(from_date or fiscal_year[1])
	filters = frappe._dict({
		"company": company, "filter_based_on": "Date Range",
		"period_start_date": from_date, "period_end_date": to_date,
		"periodicity": "Yearly", "accumulated_values": 1,
		"include_default_book_entries": 1, "show_zero_values": 1,
	})
	periods, _aggregates, account_rows = aggregate_accounts(filters)
	period_key = periods[-1].key
	engine = {row.get("account"): _factor * flt(row.get(period_key)) for row, _mapping, _factor in account_rows}

	tb_filters = frappe._dict({
		"company": company, "fiscal_year": fiscal_year[0],
		"from_date": from_date, "to_date": to_date,
		"show_zero_values": 1, "show_unclosed_fy_pl_balances": 0,
		"include_default_book_entries": 1,
		"with_period_closing_entry_for_current_period": 0, "show_net_values": 0,
	})
	_, tb_rows = trial_balance.execute(tb_filters)
	tb = {row.get("account"): row for row in (tb_rows or []) if row.get("account")}

	ledger_rows = frappe.db.sql(
		"""
		select a.name, a.root_type,
			coalesce(sum(case when gle.posting_date <= %(to_date)s then gle.debit else 0 end), 0) balance_debit,
			coalesce(sum(case when gle.posting_date <= %(to_date)s then gle.credit else 0 end), 0) balance_credit,
			coalesce(sum(case when gle.posting_date between %(from_date)s and %(to_date)s
				and gle.voucher_type != 'Period Closing Voucher' then gle.debit else 0 end), 0) period_debit,
			coalesce(sum(case when gle.posting_date between %(from_date)s and %(to_date)s
				and gle.voucher_type != 'Period Closing Voucher' then gle.credit else 0 end), 0) period_credit
		from `tabAccount` a
		left join `tabGL Entry` gle on gle.account=a.name and gle.company=a.company and gle.is_cancelled=0
		where a.company=%(company)s and a.is_group=0
		group by a.name, a.root_type
		""",
		{"company": company, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	details = []
	for row in ledger_rows:
		if row.root_type == "Asset":
			ledger_value = flt(row.balance_debit) - flt(row.balance_credit)
		elif row.root_type in ("Liability", "Equity"):
			ledger_value = flt(row.balance_credit) - flt(row.balance_debit)
		else:
			ledger_value = flt(row.period_credit) - flt(row.period_debit)
		tb_row = tb.get(row.name) or {}
		if row.root_type == "Asset":
			tb_value = flt(tb_row.get("closing_debit")) - flt(tb_row.get("closing_credit"))
		elif row.root_type in ("Liability", "Equity"):
			tb_value = flt(tb_row.get("closing_credit")) - flt(tb_row.get("closing_debit"))
		else:
			tb_value = flt(tb_row.get("credit")) - flt(tb_row.get("debit"))
		engine_value = flt(engine.get(row.name))
		if any(abs(value) > 0.000001 for value in (ledger_value, tb_value, engine_value)):
			details.append({
				"account": row.name, "root_type": row.root_type,
				"ledger": _close(ledger_value), "trial_balance": _close(tb_value),
				"ifrs_engine": _close(engine_value),
				"ledger_to_tb_difference": _close(ledger_value - tb_value),
				"tb_to_ifrs_difference": _close(tb_value - engine_value),
			})

	_, position, _, _, _ = financial_position(filters)
	from financial_reports.reporting import profit_or_loss
	_, performance, _, _, _ = profit_or_loss(filters)
	root_totals = {
		root: _close(sum(item["ledger"] for item in details if item["root_type"] == root))
		for root in ("Asset", "Liability", "Equity", "Income", "Expense")
	}
	report_totals = {
		"total_assets": _close(_statement_value(position, "Total assets", period_key)),
		"total_liabilities": _close(_statement_value(position, "Total liabilities", period_key)),
		"total_equity": _close(_statement_value(position, "Total equity", period_key)),
		"profit": _close(_statement_value(performance, "Profit", period_key)),
	}
	return {
		"company": company, "from_date": from_date, "to_date": to_date,
		"accounts_checked": len(details),
		"ledger_to_tb_mismatches": [
			row for row in details if abs(row["ledger_to_tb_difference"]) > 0.000001
		],
		"tb_to_ifrs_mismatches": [
			row for row in details if abs(row["tb_to_ifrs_difference"]) > 0.000001
		],
		"root_totals": root_totals,
		"report_totals": report_totals,
		"checks": {
			"assets_to_report": _close(root_totals["Asset"] - report_totals["total_assets"]),
			"liabilities_to_report": _close(root_totals["Liability"] - report_totals["total_liabilities"]),
			"profit_to_report": _close(
				root_totals["Income"] + root_totals["Expense"] - report_totals["profit"]
			),
			"balance_sheet_equation": _close(
				report_totals["total_assets"] - report_totals["total_liabilities"]
				- report_totals["total_equity"]
			),
		},
	}

