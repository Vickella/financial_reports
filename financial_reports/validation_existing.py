"""Validate the already-posted IFRS18-VALIDATION dataset without mutating GL data."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, flt, getdate

from financial_reports.validation import TAG, _company, _filters, _run, _value


P_AND_L_EXPECTED = {
	"Validation Revenue": (100, 200),
	"Validation Other operating income": (20, 40),
	"Validation Cost of sales": (-60, -120),
	"Validation Administrative expenses": (-30, -60),
	"Validation Depreciation": (-10, -20),
	"Validation Investment income": (15, 30),
	"Validation Finance costs": (-8, -16),
	"Validation Income tax": (-6, -12),
	"Validation Discontinued result": (5, 10),
}

OCI_EXPECTED = {
	"Validation OCI reclassifiable": (4, 8),
	"Validation OCI non-reclassifiable": (3, 6),
}

POSITION_EXPECTED = {
	"Validation Trade receivables": (25, 75),
	"Validation Inventories": (18, 54),
	"Validation Property plant and equipment": (40, 120),
	"Validation Investments": (22, 66),
	"Validation Trade payables": (17, 51),
	"Validation Borrowings": (35, 105),
	"Validation Provisions": (9, 27),
	"Validation Issued capital": (1000, 3000),
	"Validation Other reserves": (12, 36),
}


def _assert_close(actual, expected, context, assertions, tolerance=0.001):
	passed = abs(flt(actual) - flt(expected)) <= tolerance
	assertions.append({"context": context, "expected": expected, "actual": actual, "passed": passed})
	if not passed:
		raise AssertionError(f"{context}: expected {expected}, got {actual}")


def _find_line(result, label):
	for row in result.get("result") or []:
		candidate = str(
			row.get("account_name") or row.get("line_item") or row.get("component")
			or row.get("item") or row.get("metric") or ""
		).strip("'")
		if candidate == label:
			return row
	raise AssertionError(f"Required validation line not found: {label}")


def _assert_profit_structure(result, assertions):
	category_sums = {category: {"comparative_period": 0, "current_period": 0} for category in (
		"Operating", "Investing", "Financing", "Income taxes", "Discontinued operations"
	)}
	current_category = None
	for row in result.get("result") or []:
		label = str(row.get("account_name") or "").strip("'")
		if label in category_sums and not row.get("is_total"):
			current_category = label
			continue
		if row.get("is_total") or not current_category or not label:
			continue
		for period in ("comparative_period", "current_period"):
			category_sums[current_category][period] += flt(row.get(period))
	for period in ("comparative_period", "current_period"):
		operating = category_sums["Operating"][period]
		before_financing = operating + category_sums["Investing"][period]
		before_tax = before_financing + category_sums["Financing"][period]
		continuing = before_tax + category_sums["Income taxes"][period]
		profit = continuing + category_sums["Discontinued operations"][period]
		for label, expected in (
			("Operating profit", operating),
			("Profit before financing and income taxes", before_financing),
			("Profit before income tax", before_tax),
			("Profit from continuing operations", continuing),
			("Profit", profit),
		):
			_assert_close(_value(result, label, period), expected, f"{period} structural {label}", assertions)


def _ensure_mpm(company_name):
	name = f"{TAG} Adjusted Operating Profit"
	if frappe.db.exists("IFRS 18 Management Performance Measure", name):
		return name
	depreciation = frappe.db.get_value("Account", {"company": company_name, "account_name": "Validation Depreciation"})
	doc = frappe.get_doc({
		"doctype": "IFRS 18 Management Performance Measure",
		"measure_name": name,
		"company": company_name,
		"active": 1,
		"comparable_subtotal": "Operating profit",
		"reason_for_use": "Validation of the IFRS 18 MPM reconciliation and related tax effect.",
		"calculation_description": "Operating profit adjusted for validation depreciation.",
		"public_communication_reference": TAG,
		"adjustments": [{
			"adjustment_label": "Validation depreciation add-back",
			"account": depreciation,
			"treatment": "Add",
			"tax_rate": 25,
			"nci_effect": 0,
		}],
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _ensure_budget(company, fiscal_year):
	validation_cost_center = frappe.db.get_value(
		"Cost Center", {"company": company.name, "cost_center_name": f"{TAG} Cost Center"}
	)
	if not validation_cost_center:
		parent = frappe.db.get_value(
			"Cost Center", {"company": company.name, "is_group": 1, "parent_cost_center": ["is", "not set"]}, "name"
		) or frappe.db.get_value("Cost Center", {"company": company.name, "is_group": 1}, "name")
		validation_cost_center = frappe.get_doc({
			"doctype": "Cost Center", "cost_center_name": f"{TAG} Cost Center",
			"company": company.name, "parent_cost_center": parent, "is_group": 0,
		}).insert(ignore_permissions=True).name
	existing = frappe.db.get_value("Budget", {
		"company": company.name, "fiscal_year": fiscal_year, "budget_against": "Cost Center",
		"cost_center": validation_cost_center, "docstatus": 1,
	})
	if existing:
		return existing
	revenue = frappe.db.get_value("Account", {"company": company.name, "account_name": "Validation Revenue"})
	cost = frappe.db.get_value("Account", {"company": company.name, "account_name": "Validation Cost of Sales"})
	doc = frappe.get_doc({
		"doctype": "Budget", "company": company.name, "fiscal_year": fiscal_year,
		"budget_against": "Cost Center", "cost_center": validation_cost_center,
		"accounts": [
			{"account": revenue, "budget_amount": 1200},
			{"account": cost, "budget_amount": 720},
		],
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	frappe.db.commit()
	return doc.name


def validate_posted_dataset(company=None):
	if frappe.local.site != "test.local":
		frappe.throw("Controlled live validation is restricted to test.local")
	company = _company(company)
	vouchers = frappe.get_all(
		"Journal Entry", filters={"user_remark": ["like", f"{TAG}%"], "docstatus": 1}, pluck="name"
	)
	if len(vouchers) != 40:
		raise AssertionError(f"Expected 40 submitted validation vouchers, found {len(vouchers)}")
	fy = frappe.get_all(
		"Fiscal Year", filters={"year_start_date": ["<=", getdate()], "year_end_date": [">=", getdate()]},
		fields=["name", "year_start_date", "year_end_date"], order_by="year_start_date desc", limit=1,
	) or frappe.get_all("Fiscal Year", fields=["name", "year_start_date", "year_end_date"], order_by="year_start_date desc", limit=1)
	start = getdate(fy[0].year_start_date)
	comparative_from, comparative_to = add_days(start, 5), add_days(start, 34)
	current_from, current_to = add_days(start, 65), add_days(start, 94)
	filters = _filters(company, current_from, current_to, comparative_from, comparative_to)
	assertions = []
	report_results = {}

	pnl, xlsx_size, print_size = _run("Profit and Loss Statement", filters)
	report_results["Profit and Loss Statement"] = {"rows": len(pnl["result"]), "xlsx_bytes": xlsx_size, "print_html_bytes": print_size}
	for label, (comparative, current) in P_AND_L_EXPECTED.items():
		row = _find_line(pnl, label)
		_assert_close(row.get("comparative_period"), comparative, f"P&L comparative {label}", assertions)
		_assert_close(row.get("current_period"), current, f"P&L current {label}", assertions)
	_assert_profit_structure(pnl, assertions)

	comprehensive, xlsx_size, print_size = _run("IFRS 18 Statement of Comprehensive Income", filters)
	report_results["IFRS 18 Statement of Comprehensive Income"] = {"rows": len(comprehensive["result"]), "xlsx_bytes": xlsx_size, "print_html_bytes": print_size}
	for label, (comparative, current) in OCI_EXPECTED.items():
		row = _find_line(comprehensive, label)
		_assert_close(row.get("comparative_period"), comparative, f"OCI comparative {label}", assertions)
		_assert_close(row.get("current_period"), current, f"OCI current {label}", assertions)
	for period in ("comparative_period", "current_period"):
		profit = _value(comprehensive, "Profit", period)
		oci = _value(comprehensive, "Other comprehensive income, net of tax", period)
		total = _value(comprehensive, "Total comprehensive income", period)
		_assert_close(total, profit + oci, f"{period} total comprehensive income", assertions)

	position_filters = dict(filters, accumulated_values=1)
	position, xlsx_size, print_size = _run("Balance Sheet", position_filters)
	report_results["Balance Sheet"] = {"rows": len(position["result"]), "xlsx_bytes": xlsx_size, "print_html_bytes": print_size}
	for label, (comparative, current) in POSITION_EXPECTED.items():
		row = _find_line(position, label)
		_assert_close(row.get("comparative_period"), comparative, f"Position comparative {label}", assertions)
		_assert_close(row.get("current_period"), current, f"Position current {label}", assertions)
	for period in ("comparative_period", "current_period"):
		assets = _value(position, "Total assets", period)
		liabilities = _value(position, "Total liabilities", period)
		equity = _value(position, "Total equity", period)
		_assert_close(assets, liabilities + equity, f"{period} accounting equation", assertions)

	_ensure_mpm(company.name)
	_ensure_budget(company, fy[0].name)

	standard_reports = (
		"Cash Flow", "IFRS 18 Statement of Changes in Equity", "IFRS 18 Notes Schedule",
		"IFRS 18 Financial Ratios", "IFRS 18 Working Capital Analysis",
		"IFRS 18 Cost Center Profitability", "IFRS 18 Management Performance Measures",
		"IFRS 18 Mapping Audit",
	)
	for report_name in standard_reports:
		report_filters = position_filters if report_name == "IFRS 18 Working Capital Analysis" else filters
		result, xlsx_size, print_size = _run(report_name, report_filters)
		report_results[report_name] = {
			"rows": len(result.get("result") or []), "columns": len(result.get("columns") or []),
			"xlsx_bytes": xlsx_size, "print_html_bytes": print_size,
		}
		if report_name != "IFRS 18 Mapping Audit":
			column_names = {column.get("fieldname") for column in result.get("columns") or []}
			if not ({"comparative_period", "current_period"} & column_names) and report_name not in (
				"IFRS 18 Statement of Changes in Equity", "IFRS 18 Cost Center Profitability"
			):
				raise AssertionError(f"{report_name}: comparative/current columns missing")

	budget_filters = {
		"company": company.name, "fiscal_year": fy[0].name,
		"from_date": str(current_from), "to_date": str(current_to),
		"comparison_enabled": 1,
		"comparison_from_date": str(comparative_from), "comparison_to_date": str(comparative_to),
	}
	budget, xlsx_size, print_size = _run("IFRS 18 Budget Variance", budget_filters)
	report_results["IFRS 18 Budget Variance"] = {"rows": len(budget["result"]), "xlsx_bytes": xlsx_size, "print_html_bytes": print_size}
	if not budget.get("result"):
		raise AssertionError("Budget variance report returned no validation rows")

	return {
		"site": frappe.local.site,
		"company": company.name,
		"submitted_validation_vouchers": len(vouchers),
		"current_range": [current_from, current_to],
		"comparative_range": [comparative_from, comparative_to],
		"assertions_passed": len(assertions),
		"reports": report_results,
		"note": "Tagged validation vouchers are retained as cancelled records so VerityTax and VerityGuard audit links remain intact.",
	}
