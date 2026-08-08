"""End-to-end PDF pipeline validation for the shared IFRS 18 print format."""

import subprocess
import json
import re
from io import BytesIO

import frappe
from frappe.utils.pdf import get_pdf
from frappe.utils.print_format import report_to_pdf


def validate_pdf_pipeline():
	if frappe.local.site != "test.local":
		frappe.throw("Print validation is restricted to test.local")

	app_path = frappe.get_app_path("financial_reports")
	bench_path = app_path.rsplit("/apps/financial_reports/", 1)[0]
	renderer = f"{bench_path}/apps/financial_reports/tools/render_print_template.js"
	completed = subprocess.run(
		["node", renderer],
		cwd=bench_path,
		capture_output=True,
		check=True,
	)
	html = completed.stdout.decode("utf-8")
	for prohibited in ("Fiscal period", "Cost center", "Applied filters", "Prepared from ERPNext", "Review materiality", ">Notes<"):
		if prohibited in html:
			raise AssertionError(f"Rendered print HTML contains prohibited text: {prohibited}")
	if "(138.50)" not in html or "-138.50" in html:
		raise AssertionError("Accounting-parentheses formatting was not rendered")

	pdf = get_pdf(html, options={"orientation": "Landscape", "page-size": "A4"})
	if not pdf.startswith(b"%PDF") or len(pdf) < 1000:
		raise AssertionError("Frappe PDF pipeline did not return a valid PDF")
	report_to_pdf(html, orientation="Landscape")
	endpoint_pdf = frappe.local.response.get("filecontent") or b""
	if frappe.local.response.get("type") != "pdf" or not endpoint_pdf.startswith(b"%PDF"):
		raise AssertionError("The report_to_pdf download endpoint did not return a PDF response")
	return {
		"rendered_html_bytes": len(html.encode()), "pdf_bytes": len(pdf), "pdf_signature": "%PDF",
		"download_endpoint_pdf_bytes": len(endpoint_pdf), "download_endpoint_type": frappe.local.response.get("type"),
		"accounting_parentheses": True, "prohibited_metadata_removed": True,
	}


def validate_farm_live_pdfs():
	"""Render farm.test ledger-backed statements and inspect the resulting PDF bytes."""
	if frappe.local.site != "farm.test":
		frappe.throw("Live statement validation is restricted to farm.test")

	from frappe.desk.query_report import run
	from pypdf import PdfReader
	from pypdf.generic import ContentStream

	app_path = frappe.get_app_path("financial_reports")
	bench_path = app_path.rsplit("/apps/financial_reports/", 1)[0]
	renderer = f"{bench_path}/apps/financial_reports/tools/render_print_template.js"
	filters = {
		"company": "Wind Power LLC", "filter_based_on": "Date Range",
		"period_start_date": "2026-01-01", "period_end_date": "2026-12-31",
		"comparison_enabled": 1, "comparison_from_date": "2025-01-01",
		"comparison_to_date": "2025-12-31", "presentation_currency": "USD",
		"show_opening_and_closing_balance": 1,
	}
	results = {}
	for report_name, filename in (
		("Profit and Loss Statement", "ifrs18-pl-verified.pdf"),
		("Balance Sheet", "ifrs18-bs-verified.pdf"),
		("Cash Flow", "ifrs18-cash-flow-verified.pdf"),
	):
		report = run(report_name, filters=json.dumps(filters))
		context = {
			"filters": filters, "report": {"report_name": report_name},
			"columns": report.get("columns") or [], "data": report.get("result") or [],
		}
		rendered = subprocess.run(
			["node", renderer], cwd=bench_path, input=json.dumps(context, default=str).encode(),
			capture_output=True, check=True,
		).stdout.decode()
		pdf = get_pdf(rendered, options={"orientation": "Landscape", "page-size": "A4"})
		with open(f"/mnt/c/tmp/{filename}", "wb") as output:
			output.write(pdf)
		reader = PdfReader(BytesIO(pdf))
		text = "\n".join(page.extract_text() or "" for page in reader.pages)
		normalised_text = re.sub(r"\s+", " ", text)
		if report_name == "Profit and Loss Statement":
			if re.search(r"(?:\$|USD)?\s*-\s*\d[\d,]*\.\d{2}", text):
				raise AssertionError("P&L PDF still contains a minus-signed monetary amount")
			if "(138,441.60)" not in text:
				raise AssertionError("P&L PDF lacks the expected parenthesised cost of sales")
		if report_name == "Cash Flow":
			rows = {
				str(row.get("section") or row.get("section_name") or "").strip("'"): row
				for row in report.get("result") or []
			}
			activity_total = sum(
				float(rows[label].get("current_period") or 0)
				for label in (
					"Net cash flows from operating activities",
					"Net cash flows from investing activities",
					"Net cash flows from financing activities",
				)
			)
			net_change = float(
				rows["Net increase/(decrease) in cash and cash equivalents"].get(
					"current_period"
				) or 0
			)
			opening = float(
				rows["Cash and cash equivalents at beginning of period"].get(
					"current_period"
				) or 0
			)
			closing = float(
				rows["Cash and cash equivalents at end of period"].get(
					"current_period"
				) or 0
			)
			if abs(activity_total - net_change) > 0.01:
				raise AssertionError("Cash Flow activity totals do not equal net cash movement")
			if abs(opening + net_change - closing) > 0.01:
				raise AssertionError("Cash Flow opening balance does not reconcile to closing")
			for required in ("Operating activities", "Investing activities", "Financing activities", "110,003.00"):
				if required not in normalised_text:
					raise AssertionError(f"Cash Flow PDF lacks required content: {required}")
			if "Cash movements pending activity classification" in normalised_text:
				raise AssertionError("Cash Flow PDF contains unclassified cash movements")
			if normalised_text.count("Investing activities") != 1 or normalised_text.count("Financing activities") != 1:
				raise AssertionError("Cash Flow PDF contains duplicate activity headings")
		rules = []
		for page in reader.pages:
			stream = ContentStream(page.get_contents(), reader)
			for operands, operator in stream.operations:
				if operator == b"re":
					width, height = abs(float(operands[2])), abs(float(operands[3]))
					if width > 5 and height <= 2:
						rules.append(width)
		short_rules = sorted({round(length * 0.75, 2) for length in rules if 115 <= length <= 125})
		if not short_rules:
			raise AssertionError(f"{report_name} PDF lacks fixed-width amount rules")
		results[report_name] = {
			"pages": len(reader.pages), "pdf_bytes": len(pdf),
			"amount_rule_points": short_rules, "output": filename,
		}
	return results


def inspect_farm_cashflow_and_mpm():
	"""Return printable row structure for targeted live-report review."""
	if frappe.local.site != "farm.test":
		frappe.throw("Live report inspection is restricted to farm.test")

	from frappe.desk.query_report import run

	filters = {
		"company": "Wind Power LLC", "filter_based_on": "Date Range",
		"period_start_date": "2026-01-01", "period_end_date": "2026-12-31",
		"comparison_enabled": 1, "comparison_from_date": "2025-01-01",
		"comparison_to_date": "2025-12-31", "presentation_currency": "USD",
	}
	output = {}
	for report_name in ("Cash Flow", "IFRS 18 Management Performance Measures"):
		report = run(report_name, filters=json.dumps(filters))
		output[report_name] = {
			"columns": [column.get("fieldname") for column in report.get("columns") or []],
			"rows": [{key: row.get(key) for key in ("section", "section_name", "account_name", "measure", "item", "row_type", "comparative_period", "current_period", "is_total", "indent") if row.get(key) is not None} for row in report.get("result") or []],
		}
	return output


def inspect_farm_cash_ledger():
	if frappe.local.site != "farm.test":
		frappe.throw("Cash-ledger inspection is restricted to farm.test")
	accounts = frappe.get_all(
		"Account", filters={"company": "Wind Power LLC", "is_group": 0},
		fields=["name", "account_type", "custom_ifrs18_line_item"],
	)
	cash_accounts = [account.name for account in accounts if account.account_type in ("Cash", "Bank") or "cash and cash equivalent" in str(account.custom_ifrs18_line_item or "").lower()]
	return frappe.get_all(
		"GL Entry",
		filters={"company": "Wind Power LLC", "posting_date": ["between", ["2026-01-01", "2026-12-31"]], "is_cancelled": 0, "account": ["in", cash_accounts]},
		fields=["posting_date", "voucher_type", "voucher_no", "account", "against", "debit", "credit"],
		order_by="posting_date, voucher_type, voucher_no",
	)

def validate_farm_mpm_presets():
	if frappe.local.site != "farm.test":
		frappe.throw("MPM preset validation is restricted to farm.test")
	from financial_reports.financial_reports.doctype.ifrs_18_management_performance_measure.ifrs_18_management_performance_measure import (
		MPM_PRESETS,
		get_mpm_preset,
	)

	results = {}
	for measure_template in MPM_PRESETS:
		preset = get_mpm_preset("Wind Power LLC", measure_template)
		results[measure_template] = {
			"comparable_subtotal": preset["comparable_subtotal"],
			"suggested_adjustments": len(preset["adjustments"]),
		}
	if not results["EBITDA"]["suggested_adjustments"]:
		raise AssertionError("EBITDA did not suggest depreciation/amortisation accounts")
	return {
		"presets": results,
		"adjustments_editable_grid": bool(
			frappe.get_meta("IFRS 18 MPM Adjustment").editable_grid
		),
	}

def validate_farm_all_report_data():
	"""Validate every installed report against farm.test data and core tie-outs."""
	if frappe.local.site != "farm.test":
		frappe.throw("Full live validation is restricted to farm.test")

	from frappe.desk.query_report import run
	from frappe.query_builder.functions import Sum
	from erpnext.accounts.utils import get_fiscal_year

	company = "Wind Power LLC"
	base_filters = {
		"company": company,
		"filter_based_on": "Date Range",
		"period_start_date": "2026-01-01",
		"period_end_date": "2026-12-31",
		"comparison_enabled": 1,
		"comparison_from_date": "2025-01-01",
		"comparison_to_date": "2025-12-31",
		"presentation_currency": "USD",
		"include_default_book_entries": 1,
		"show_opening_and_closing_balance": 1,
	}
	fiscal_year = get_fiscal_year("2026-12-31", company=company)[0]
	report_filters = {
		"IFRS 18 Budget Variance": {
			"company": company,
			"fiscal_year": fiscal_year,
			"from_date": "2026-01-01",
			"to_date": "2026-12-31",
			"comparison_enabled": 1,
			"comparison_from_date": "2025-01-01",
			"comparison_to_date": "2025-12-31",
			"include_default_book_entries": 1,
		},
		"IFRS 18 Mapping Audit": {"company": company},
	}
	report_names = (
		"Profit and Loss Statement",
		"Balance Sheet",
		"Cash Flow",
		"IFRS 18 Statement of Comprehensive Income",
		"IFRS 18 Statement of Changes in Equity",
		"IFRS 18 Notes Schedule",
		"IFRS 18 Financial Ratios",
		"IFRS 18 Working Capital Analysis",
		"IFRS 18 Budget Variance",
		"IFRS 18 Cost Center Profitability",
		"IFRS 18 Management Performance Measures",
		"IFRS 18 Mapping Audit",
	)
	reports = {}
	for report_name in report_names:
		report = run(
			report_name,
			filters=json.dumps(report_filters.get(report_name, base_filters)),
		)
		if not report.get("columns") or report.get("result") is None:
			raise AssertionError(f"{report_name} did not return a report table")
		reports[report_name] = report

	def keyed(report_name):
		return {
			str(
				row.get("account_name")
				or row.get("section")
				or row.get("component")
				or row.get("metric")
				or ""
			).strip("'"): row
			for row in reports[report_name].get("result") or []
		}

	def current(row):
		return float(row.get("current_period") or 0)

	pnl = keyed("Profit and Loss Statement")
	position = keyed("Balance Sheet")
	cash = keyed("Cash Flow")
	comprehensive = keyed("IFRS 18 Statement of Comprehensive Income")
	if abs(current(position["Total assets"]) - current(position["Total equity and liabilities"])) > 0.01:
		raise AssertionError("Statement of financial position does not balance")
	if abs(
		sum(
			current(cash[label])
			for label in (
				"Net cash flows from operating activities",
				"Net cash flows from investing activities",
				"Net cash flows from financing activities",
			)
		)
		- current(cash["Net increase/(decrease) in cash and cash equivalents"])
	) > 0.01:
		raise AssertionError("Cash-flow activities do not reconcile")
	if abs(
		current(cash["Cash and cash equivalents at beginning of period"])
		+ current(cash["Net increase/(decrease) in cash and cash equivalents"])
		- current(cash["Cash and cash equivalents at end of period"])
	) > 0.01:
		raise AssertionError("Cash-flow opening and closing balances do not reconcile")
	if abs(
		current(comprehensive["Profit"])
		+ current(comprehensive["Other comprehensive income, net of tax"])
		- current(comprehensive["Total comprehensive income"])
	) > 0.01:
		raise AssertionError("Total comprehensive income does not reconcile")

	for row in reports["IFRS 18 Statement of Changes in Equity"].get("result") or []:
		opening = float(row.get("current_period_opening") or 0)
		movements = float(row.get("current_period_movements") or 0)
		closing = float(row.get("current_period_closing") or 0)
		if abs(opening + movements - closing) > 0.01:
			raise AssertionError("An equity component does not reconcile")

	cost_centre_profit = sum(
		float(row.get("current_period_profit") or 0)
		for row in reports["IFRS 18 Cost Center Profitability"].get("result") or []
	)
	if abs(cost_centre_profit - current(pnl["Profit"])) > 0.01:
		raise AssertionError("Cost-centre profit does not reconcile to statement profit")

	gle = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")
	direct_profit = (
		frappe.qb.from_(gle)
		.inner_join(account)
		.on(account.name == gle.account)
		.select(Sum(gle.credit - gle.debit))
		.where(gle.company == company)
		.where(gle.posting_date >= "2026-01-01")
		.where(gle.posting_date <= "2026-12-31")
		.where(gle.is_cancelled == 0)
		.where(gle.voucher_type != "Period Closing Voucher")
		.where(account.root_type.isin(("Income", "Expense")))
		.where(account.custom_ifrs18_category.isin((
			"Operating", "Investing", "Financing", "Income taxes",
			"Discontinued operations",
		)))
	).run()[0][0]
	if abs(float(direct_profit or 0) - current(pnl["Profit"])) > 0.01:
		raise AssertionError("Statement profit does not tie to mapped GL entries")

	dimension_checks = {}
	for fieldname in ("cost_center", "project"):
		value = frappe.db.get_value(
			"GL Entry",
			{
				"company": company,
				"posting_date": ["between", ["2026-01-01", "2026-12-31"]],
				"is_cancelled": 0,
				fieldname: ["is", "set"],
			},
			fieldname,
		)
		if value:
			dimension_filters = dict(base_filters)
			dimension_filters[fieldname] = [value]
			dimension_report = run(
				"Profit and Loss Statement",
				filters=json.dumps(dimension_filters),
			)
			dimension_checks[fieldname] = {
				"value": value,
				"rows": len(dimension_report.get("result") or []),
			}

	quarter_filters = dict(base_filters)
	quarter_filters.update({
		"period_start_date": "2026-04-01",
		"period_end_date": "2026-06-30",
		"comparison_from_date": "2025-04-01",
		"comparison_to_date": "2025-06-30",
	})
	quarter = run(
		"Profit and Loss Statement",
		filters=json.dumps(quarter_filters),
	)
	if not quarter.get("result"):
		raise AssertionError("Custom-quarter report did not return data")

	return {
		"reports": {
			name: len(report.get("result") or [])
			for name, report in reports.items()
		},
		"tie_outs": {
			"profit": current(pnl["Profit"]),
			"total_assets": current(position["Total assets"]),
			"total_equity_and_liabilities": current(position["Total equity and liabilities"]),
			"net_cash_movement": current(cash["Net increase/(decrease) in cash and cash equivalents"]),
			"ending_cash": current(cash["Cash and cash equivalents at end of period"]),
			"cost_centre_profit": cost_centre_profit,
		},
		"dimension_checks": dimension_checks,
		"custom_quarter_rows": len(quarter.get("result") or []),
	}

def validate_farm_all_report_pdfs():
	"""Generate and inspect the printable output of every financial report."""
	if frappe.local.site != "farm.test":
		frappe.throw("Full PDF validation is restricted to farm.test")

	from frappe.desk.query_report import run
	from erpnext.accounts.utils import get_fiscal_year
	from pypdf import PdfReader
	from pypdf.generic import ContentStream

	app_path = frappe.get_app_path("financial_reports")
	bench_path = app_path.rsplit("/apps/financial_reports/", 1)[0]
	renderer = f"{bench_path}/apps/financial_reports/tools/render_print_template.js"
	company = "Wind Power LLC"
	base_filters = {
		"company": company,
		"filter_based_on": "Date Range",
		"period_start_date": "2026-01-01",
		"period_end_date": "2026-12-31",
		"comparison_enabled": 1,
		"comparison_from_date": "2025-01-01",
		"comparison_to_date": "2025-12-31",
		"presentation_currency": "USD",
		"include_default_book_entries": 1,
		"show_opening_and_closing_balance": 1,
	}
	fiscal_year = get_fiscal_year("2026-12-31", company=company)[0]
	special_filters = {
		"IFRS 18 Budget Variance": {
			"company": company,
			"fiscal_year": fiscal_year,
			"from_date": "2026-01-01",
			"to_date": "2026-12-31",
			"comparison_enabled": 1,
			"comparison_from_date": "2025-01-01",
			"comparison_to_date": "2025-12-31",
			"presentation_currency": "USD",
			"include_default_book_entries": 1,
		},
		"IFRS 18 Mapping Audit": {"company": company},
	}
	report_names = (
		"Profit and Loss Statement",
		"Balance Sheet",
		"Cash Flow",
		"IFRS 18 Statement of Comprehensive Income",
		"IFRS 18 Statement of Changes in Equity",
		"IFRS 18 Notes Schedule",
		"IFRS 18 Financial Ratios",
		"IFRS 18 Working Capital Analysis",
		"IFRS 18 Budget Variance",
		"IFRS 18 Cost Center Profitability",
		"IFRS 18 Management Performance Measures",
		"IFRS 18 Mapping Audit",
	)
	prohibited = (
		"Fiscal period",
		"Applied filters",
		"Prepared from ERPNext",
		"Review materiality",
	)
	primary_statements = {
		"Profit and Loss Statement",
		"Balance Sheet",
		"Cash Flow",
		"IFRS 18 Statement of Comprehensive Income",
		"IFRS 18 Statement of Changes in Equity",
	}
	results = {}
	for report_name in report_names:
		filters = special_filters.get(report_name, base_filters)
		report = run(report_name, filters=json.dumps(filters))
		columns = report.get("columns") or []
		rows = report.get("result") or []
		if report_name in primary_statements and any(
			str(column.get("label") or "").strip().lower() == "notes"
			for column in columns
		):
			raise AssertionError(f"{report_name} still contains a Notes column")
		context = {
			"filters": filters,
			"report": {"report_name": report_name},
			"columns": columns,
			"data": rows,
		}
		rendered = subprocess.run(
			["node", renderer],
			cwd=bench_path,
			input=json.dumps(context, default=str).encode(),
			capture_output=True,
			check=True,
		).stdout.decode()
		for text in prohibited:
			if text in rendered:
				raise AssertionError(f"{report_name} contains prohibited metadata")
		pdf = get_pdf(
			rendered,
			options={"orientation": "Landscape", "page-size": "A4"},
		)
		slug = re.sub(r"[^a-z0-9]+", "-", report_name.lower()).strip("-")
		with open(f"/mnt/c/tmp/ifrs18-{slug}-verified.html", "w") as output:
			output.write(rendered)
		filename = f"ifrs18-{slug}-verified.pdf"
		with open(f"/mnt/c/tmp/{filename}", "wb") as output:
			output.write(pdf)
		reader = PdfReader(BytesIO(pdf))
		extracted = chr(10).join(
			page.extract_text() or "" for page in reader.pages
		)
		normalised = " ".join(extracted.split())
		if company not in normalised:
			raise AssertionError(f"{report_name} PDF lacks the company heading")
		if re.search(r"(?:[$]|USD)? *- *[0-9][0-9,]*[.][0-9]{2}", extracted):
			raise AssertionError(f"{report_name} PDF contains minus-signed amounts")
		currency_columns = sum(
			1
			for column in columns
			if not column.get("hidden")
			and not column.get("print_hide")
			and column.get("fieldtype") == "Currency"
		)
		if extracted.count("$") > currency_columns:
			raise AssertionError(f"{report_name} repeats currency symbols per amount")
		rules = []
		for page in reader.pages:
			stream = ContentStream(page.get_contents(), reader)
			for operands, operator in stream.operations:
				if operator == b"re":
					width, height = abs(float(operands[2])), abs(float(operands[3]))
					if width > 5 and height <= 2:
						rules.append(width)
		if currency_columns and not any(115 <= width <= 125 for width in rules):
			raise AssertionError(f"{report_name} lacks fixed-width amount rules")
		results[report_name] = {
			"rows": len(rows),
			"pages": len(reader.pages),
			"pdf_bytes": len(pdf),
			"currency_columns": currency_columns,
			"output": filename,
		}
	return results

def inspect_farm_position_accounts():
	if frappe.local.site != "farm.test":
		frappe.throw("Position inspection is restricted to farm.test")
	from frappe.query_builder.functions import Sum

	gle = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")
	rows = (
		frappe.qb.from_(gle)
		.inner_join(account)
		.on(account.name == gle.account)
		.select(
			account.name,
			account.account_name,
			account.account_type,
			account.custom_ifrs18_category,
			account.custom_ifrs18_line_item,
			Sum(gle.debit - gle.credit).as_("balance"),
		)
		.where(gle.company == "Wind Power LLC")
		.where(gle.posting_date <= "2026-12-31")
		.where(gle.is_cancelled == 0)
		.where(account.root_type == "Asset")
		.groupby(
			account.name,
			account.account_name,
			account.account_type,
			account.custom_ifrs18_category,
			account.custom_ifrs18_line_item,
		)
	).run(as_dict=True)
	return sorted(
		[row for row in rows if abs(float(row.balance or 0)) > 0.005],
		key=lambda row: abs(float(row.balance)),
		reverse=True,
	)
