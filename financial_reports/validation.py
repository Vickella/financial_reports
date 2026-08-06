"""Controlled live-site validation for IFRS 18 reports.

All posted vouchers are identifiable by ``IFRS18-VALIDATION`` and are created
only when this module is explicitly invoked from bench on a test site.
"""

from __future__ import annotations

import json
from io import BytesIO

import frappe
from frappe.utils import add_days, flt, getdate
from frappe.utils.xlsxutils import make_xlsx


TAG = "IFRS18-VALIDATION"
REPORTS = (
	"Profit and Loss Statement",
	"Balance Sheet",
	"Cash Flow",
	"IFRS 18 Statement of Comprehensive Income",
	"IFRS 18 Statement of Changes in Equity",
	"IFRS 18 Notes Schedule",
	"IFRS 18 Financial Ratios",
	"IFRS 18 Working Capital Analysis",
	"IFRS 18 Cost Center Profitability",
	"IFRS 18 Management Performance Measures",
	"IFRS 18 Mapping Audit",
)


ACCOUNT_SPECS = (
	("Validation Cash", "Asset", "Current assets", "Validation Cash and cash equivalents", "Cash and cash equivalents"),
	("Validation Receivable", "Asset", "Current assets", "Validation Trade receivables", "Operating"),
	("Validation Inventory", "Asset", "Current assets", "Validation Inventories", "Operating"),
	("Validation PPE", "Asset", "Non-current assets", "Validation Property plant and equipment", "Investing"),
	("Validation Investment", "Asset", "Non-current assets", "Validation Investments", "Investing"),
	("Validation Payable", "Liability", "Current liabilities", "Validation Trade payables", "Operating"),
	("Validation Loan", "Liability", "Non-current liabilities", "Validation Borrowings", "Financing"),
	("Validation Provision", "Liability", "Non-current liabilities", "Validation Provisions", "Operating"),
	("Validation Capital", "Equity", "Equity", "Validation Issued capital", "Financing"),
	("Validation Reserve", "Equity", "Equity", "Validation Other reserves", "Financing"),
	("Validation Revenue", "Income", "Operating", "Validation Revenue", "Operating"),
	("Validation Other Operating Income", "Income", "Operating", "Validation Other operating income", "Operating"),
	("Validation Cost of Sales", "Expense", "Operating", "Validation Cost of sales", "Operating"),
	("Validation Administration", "Expense", "Operating", "Validation Administrative expenses", "Operating"),
	("Validation Depreciation", "Expense", "Operating", "Validation Depreciation", "Non-cash"),
	("Validation Investment Income", "Income", "Investing", "Validation Investment income", "Investing"),
	("Validation Finance Cost", "Expense", "Financing", "Validation Finance costs", "Financing"),
	("Validation Income Tax", "Expense", "Income taxes", "Validation Income tax", "Operating"),
	("Validation Discontinued Income", "Income", "Discontinued operations", "Validation Discontinued result", "Operating"),
	("Validation OCI Reclassifiable", "Income", "Other comprehensive income - reclassifiable", "Validation OCI reclassifiable", "Non-cash"),
	("Validation OCI Non-reclassifiable", "Income", "Other comprehensive income - non-reclassifiable", "Validation OCI non-reclassifiable", "Non-cash"),
)


POSTINGS = (
	("Validation Revenue", "credit", 100),
	("Validation Other Operating Income", "credit", 20),
	("Validation Cost of Sales", "debit", 60),
	("Validation Administration", "debit", 30),
	("Validation Depreciation", "debit", 10),
	("Validation Investment Income", "credit", 15),
	("Validation Finance Cost", "debit", 8),
	("Validation Income Tax", "debit", 6),
	("Validation Discontinued Income", "credit", 5),
	("Validation OCI Reclassifiable", "credit", 4),
	("Validation OCI Non-reclassifiable", "credit", 3),
	("Validation Receivable", "debit", 25),
	("Validation Inventory", "debit", 18),
	("Validation PPE", "debit", 40),
	("Validation Investment", "debit", 22),
	("Validation Payable", "credit", 17),
	("Validation Loan", "credit", 35),
	("Validation Provision", "credit", 9),
	("Validation Reserve", "credit", 12),
)


def inspect_site():
	return {
		"site": frappe.local.site,
		"companies": frappe.get_all("Company", pluck="name"),
		"fiscal_years": frappe.get_all(
			"Fiscal Year", fields=["name", "year_start_date", "year_end_date"], order_by="year_start_date desc"
		),
		"reports": {
			name: frappe.db.get_value("Report", name, ["module", "report_type", "disabled"], as_dict=True)
			for name in REPORTS
		},
		"mapping": frappe.db.sql("""
			select count(*) total,
				sum(case when ifnull(custom_ifrs18_category,'')='' then 1 else 0 end) unmapped,
				sum(case when custom_ifrs18_mapping_confidence='Fallback' then 1 else 0 end) fallback
			from `tabAccount`
		""", as_dict=True)[0],
	}


def _company(company=None):
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company")
	if not company:
		frappe.throw("A Company is required for live validation")
	return frappe.get_doc("Company", company)


def _root_account(company, root_type):
	name = frappe.db.get_value(
		"Account",
		{"company": company.name, "root_type": root_type, "is_group": 1, "parent_account": ["is", "not set"]},
		"name",
	)
	if not name:
		name = frappe.db.get_value(
			"Account", {"company": company.name, "root_type": root_type, "is_group": 1}, "name", order_by="lft"
		)
	return name


def _ensure_accounts(company):
	accounts = {}
	for account_name, root_type, category, line_item, cash_flow in ACCOUNT_SPECS:
		name = frappe.db.get_value("Account", {"company": company.name, "account_name": account_name})
		if not name:
			doc = frappe.get_doc({
				"doctype": "Account",
				"account_name": account_name,
				"company": company.name,
				"parent_account": _root_account(company, root_type),
				"root_type": root_type,
				"report_type": "Balance Sheet" if root_type in ("Asset", "Liability", "Equity") else "Profit and Loss",
				"is_group": 0,
			})
			doc.insert(ignore_permissions=True)
			name = doc.name
		frappe.db.set_value("Account", name, {
			"custom_ifrs18_category": category,
			"custom_ifrs18_line_item": line_item,
			"custom_ifrs18_cash_flow_activity": cash_flow,
			"custom_ifrs18_note_reference": "Validation note",
			"custom_ifrs18_mapping_source": TAG,
			"custom_ifrs18_mapping_confidence": "Manually reviewed",
			"custom_ifrs18_mapping_locked": 1,
		}, update_modified=False)
		accounts[account_name] = name
	return accounts


def cleanup_transactions():
	"""Cancel submitted test journals; retain cancelled vouchers and linked audit records."""
	names = frappe.get_all(
		"Journal Entry",
		filters={"user_remark": ["like", f"{TAG}%"], "docstatus": 1},
		pluck="name",
	)
	for name in names:
		frappe.get_doc("Journal Entry", name).cancel()
	frappe.db.commit()
	return {"cancelled": names}


def _post(company, accounts, posting_date, multiplier, series):
	default_cost_center = company.cost_center or frappe.db.get_value(
		"Cost Center", {"company": company.name, "is_group": 0}, "name"
	)
	cash = accounts["Validation Cash"]
	vouchers = []

	capital_amount = 1000 * multiplier
	capital = frappe.get_doc({
		"doctype": "Journal Entry", "company": company.name, "posting_date": posting_date,
		"user_remark": f"{TAG}-{series}-CAPITAL",
		"accounts": [
			{"account": cash, "debit_in_account_currency": capital_amount},
			{"account": accounts["Validation Capital"], "credit_in_account_currency": capital_amount},
		],
	})
	capital.insert(ignore_permissions=True)
	capital.submit()
	vouchers.append(capital.name)

	for index, (target_name, side, base_amount) in enumerate(POSTINGS, start=1):
		amount = base_amount * multiplier
		target = accounts[target_name]
		root_type = frappe.get_cached_value("Account", target, "root_type")
		target_row = {"account": target}
		cash_row = {"account": cash}
		if root_type in ("Income", "Expense") and default_cost_center:
			target_row["cost_center"] = default_cost_center
		if root_type == "Expense" and frappe.db.has_column("Journal Entry Account", "tax_nature"):
			target_row["tax_nature"] = "Operating Expense"
		if side == "debit":
			target_row["debit_in_account_currency"] = amount
			cash_row["credit_in_account_currency"] = amount
		else:
			target_row["credit_in_account_currency"] = amount
			cash_row["debit_in_account_currency"] = amount
		doc = frappe.get_doc({
			"doctype": "Journal Entry", "company": company.name, "posting_date": posting_date,
			"user_remark": f"{TAG}-{series}-{index:02d}-{target_name}",
			"accounts": [target_row, cash_row],
		})
		doc.insert(ignore_permissions=True)
		doc.submit()
		vouchers.append(doc.name)
	return vouchers


def _filters(company, current_from, current_to, comparative_from, comparative_to, accumulated=0):
	return {
		"company": company.name,
		"filter_based_on": "Date Range",
		"period_start_date": str(current_from),
		"period_end_date": str(current_to),
		"periodicity": "Yearly",
		"accumulated_values": accumulated,
		"include_default_book_entries": 1,
		"show_zero_values": 1,
		"comparison_enabled": 1,
		"comparison_from_date": str(comparative_from),
		"comparison_to_date": str(comparative_to),
	}


def _run(report_name, filters):
	from frappe.desk.query_report import get_script, run

	result = run(
		report_name,
		filters=json.dumps(filters),
		ignore_prepared_report=True,
		are_default_filters=False,
	)
	script = get_script(report_name)
	if not script.get("html_format"):
		raise AssertionError(f"{report_name}: professional print HTML was not loaded")
	rows = [[column.get("label") for column in result["columns"]]]
	for item in result.get("result") or []:
		rows.append([item.get(column.get("fieldname")) for column in result["columns"]])
	workbook = make_xlsx(rows, report_name[:30])
	if not workbook or len(workbook.getvalue()) < 500:
		raise AssertionError(f"{report_name}: XLSX export generation failed")
	return result, len(workbook.getvalue()), len(script.get("html_format"))


def _value(result, label, period_key):
	for row in result.get("result") or []:
		candidate = str(row.get("account_name") or row.get("account") or "").strip("'")
		if candidate == label:
			return flt(row.get(period_key))
	raise AssertionError(f"Required row not found: {label}")


def run_full_validation(company=None, keep_transactions=1):
	if frappe.local.site != "test.local":
		frappe.throw("Controlled live validation is restricted to test.local")
	company = _company(company)
	cleanup_transactions()
	accounts = _ensure_accounts(company)
	fy = frappe.get_all(
		"Fiscal Year",
		filters={"year_start_date": ["<=", getdate()], "year_end_date": [">=", getdate()]},
		fields=["year_start_date", "year_end_date"],
		order_by="year_start_date desc",
		limit=1,
	)
	if not fy:
		fy = frappe.get_all("Fiscal Year", fields=["year_start_date", "year_end_date"], order_by="year_start_date desc", limit=1)
	start = getdate(fy[0].year_start_date)
	comparative_from, comparative_to = add_days(start, 5), add_days(start, 34)
	current_from, current_to = add_days(start, 65), add_days(start, 94)
	filters = _filters(company, current_from, current_to, comparative_from, comparative_to)

	baseline, _, _ = _run("Profit and Loss Statement", filters)
	baseline_values = {
		period: {label: _value(baseline, label, period) for label in (
			"Operating profit", "Profit before financing and income taxes", "Profit before income tax",
			"Profit from continuing operations", "Profit",
		)}
		for period in ("comparative_period", "current_period")
	}

	vouchers = []
	vouchers.extend(_post(company, accounts, comparative_to, 1, "COMPARATIVE"))
	vouchers.extend(_post(company, accounts, current_to, 2, "CURRENT"))
	frappe.db.commit()

	results = {}
	for report_name in REPORTS:
		report_filters = dict(filters)
		if report_name in ("Balance Sheet", "IFRS 18 Working Capital Analysis"):
			report_filters["accumulated_values"] = 1
		result, xlsx_bytes, print_html_bytes = _run(report_name, report_filters)
		results[report_name] = {
			"rows": len(result.get("result") or []),
			"columns": len(result.get("columns") or []),
			"xlsx_bytes": xlsx_bytes,
			"print_html_bytes": print_html_bytes,
		}

	pnl, _, _ = _run("Profit and Loss Statement", filters)
	expected = {
		"comparative_period": {
			"Operating profit": 20, "Profit before financing and income taxes": 35,
			"Profit before income tax": 27, "Profit from continuing operations": 21, "Profit": 26,
		},
		"current_period": {
			"Operating profit": 40, "Profit before financing and income taxes": 70,
			"Profit before income tax": 54, "Profit from continuing operations": 42, "Profit": 52,
		},
	}
	assertions = []
	for period, values in expected.items():
		for label, expected_delta in values.items():
			actual_delta = _value(pnl, label, period) - baseline_values[period][label]
			passed = abs(actual_delta - expected_delta) < 0.001
			assertions.append({"period": period, "subtotal": label, "expected_delta": expected_delta, "actual_delta": actual_delta, "passed": passed})
			if not passed:
				raise AssertionError(f"{period} {label}: expected {expected_delta}, got {actual_delta}")

	if not keep_transactions:
		cleanup_transactions()
	return {
		"site": frappe.local.site,
		"company": company.name,
		"current_range": [current_from, current_to],
		"comparative_range": [comparative_from, comparative_to],
		"vouchers": vouchers if keep_transactions else [],
		"accounts_tested": len(accounts),
		"subtotal_assertions": assertions,
		"reports": results,
		"mapping_audit": inspect_site()["mapping"],
	}
