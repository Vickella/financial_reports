"""Read-only production-gate checks for permissions and presentation currency."""

import json

import frappe
from frappe.desk.query_report import run


def validate_currency_conversion():
	if frappe.local.site != "test.local":
		frappe.throw("Currency validation is restricted to test.local")
	base = {
		"company": "Test", "filter_based_on": "Date Range",
		"period_start_date": "2026-01-01", "period_end_date": "2026-12-31",
		"periodicity": "Yearly", "accumulated_values": 0,
		"include_default_book_entries": 1, "show_zero_values": 0,
	}

	def report_rows(currency):
		result = run(
			"Profit and Loss Statement",
			filters=json.dumps(dict(base, presentation_currency=currency)),
			ignore_prepared_report=True, are_default_filters=False,
		)
		return {
			str(row.get("account_name") or "").strip("'"): row
			for row in result.get("result") or []
			if row and row.get("currency") == currency and not row.get("is_total")
		}

	usd = report_rows("USD")
	zwg = report_rows("ZWG")
	samples = []
	for label, row in usd.items():
		base_value = float(row.get("total") or 0)
		converted = float((zwg.get(label) or {}).get("total") or 0)
		if base_value and converted:
			samples.append({
				"line": label, "usd": base_value, "zwg": converted,
				"ratio": round(converted / base_value, 6),
			})
	if not samples:
		raise AssertionError("No non-zero lines were available for presentation-currency validation")
	if any(abs(sample["ratio"] - 30) > 0.001 for sample in samples):
		raise AssertionError(f"Unexpected USD/ZWG conversion ratios: {samples[:5]}")
	return {"exchange_rate": 30, "lines_checked": len(samples), "samples": samples[:5]}


def validate_permissions():
	reports = (
		"Profit and Loss Statement", "Balance Sheet", "Cash Flow",
		"IFRS 18 Financial Ratios", "IFRS 18 Mapping Audit",
	)
	result = {}
	for name in reports:
		doc = frappe.get_doc("Report", name)
		result[name] = {
			"roles": [row.role for row in doc.roles],
			"administrator_read": bool(frappe.has_permission("Report", doc=doc, ptype="read", user="Administrator")),
			"guest_read": bool(frappe.has_permission("Report", doc=doc, ptype="read", user="Guest")),
		}
		if not result[name]["administrator_read"] or result[name]["guest_read"]:
			raise AssertionError(f"Unexpected report permission result for {name}: {result[name]}")
	return result
