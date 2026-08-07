"""End-to-end PDF pipeline validation for the shared IFRS 18 print format."""

import subprocess

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
