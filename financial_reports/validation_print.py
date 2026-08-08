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
	}
	results = {}
	for report_name, filename in (
		("Profit and Loss Statement", "ifrs18-pl-verified.pdf"),
		("Balance Sheet", "ifrs18-bs-verified.pdf"),
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
		if report_name == "Profit and Loss Statement":
			if re.search(r"(?:\$|USD)?\s*-\s*\d[\d,]*\.\d{2}", text):
				raise AssertionError("P&L PDF still contains a minus-signed monetary amount")
			if "(138,441.60)" not in text:
				raise AssertionError("P&L PDF lacks the expected parenthesised cost of sales")
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
