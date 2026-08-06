"""End-to-end PDF pipeline validation for the shared IFRS 18 print format."""

import subprocess

import frappe
from frappe.utils.pdf import get_pdf


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
	if "Current reporting period" not in html or "Comparative reporting period" not in html:
		raise AssertionError("Rendered print HTML is missing selected date-range headings")

	pdf = get_pdf(html, options={"orientation": "Landscape", "page-size": "A4"})
	if not pdf.startswith(b"%PDF") or len(pdf) < 1000:
		raise AssertionError("Frappe PDF pipeline did not return a valid PDF")
	return {"rendered_html_bytes": len(html.encode()), "pdf_bytes": len(pdf), "pdf_signature": "%PDF"}
