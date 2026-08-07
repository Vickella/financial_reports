"""Controlled validation of automatic mapping and user confirmation for a new Account."""

import frappe

from financial_reports.mapping import infer_mapping
from financial_reports.validation import _filters, _run, _value


TEST_ACCOUNT_NAME = "IFRS18 Mapping Workflow Test"


def validate_new_account_workflow():
	if frappe.local.site != "test.local":
		frappe.throw("New-account workflow validation is restricted to test.local")

	company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company")
	existing = frappe.db.get_value("Account", {"company": company, "account_name": TEST_ACCOUNT_NAME})

	parent = frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Expense", "is_group": 1},
		"name",
		order_by="lft asc",
	)
	if existing:
		doc = frappe.get_doc("Account", existing)
		doc.disabled = 0
		doc.custom_ifrs18_mapping_locked = 0
		doc.custom_ifrs18_mapping_review_required = 1
		doc.custom_ifrs18_mapping_source = "Automatic new-account suggestion"
		doc.custom_ifrs18_mapping_confidence = infer_mapping(doc).confidence
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({
			"doctype": "Account",
			"account_name": TEST_ACCOUNT_NAME,
			"company": company,
			"parent_account": parent,
			"root_type": "Expense",
			"report_type": "Profit and Loss",
			"account_type": "Expense Account",
			"is_group": 0,
		}).insert(ignore_permissions=True)
	doc.reload()

	suggested = {
		"category": doc.custom_ifrs18_category,
		"line_item": doc.custom_ifrs18_line_item,
		"cash_flow": doc.custom_ifrs18_cash_flow_activity,
		"expense_nature": doc.custom_ifrs18_expense_nature,
		"source": doc.custom_ifrs18_mapping_source,
		"review_required": doc.custom_ifrs18_mapping_review_required,
	}
	if not all((suggested["category"], suggested["line_item"], suggested["cash_flow"])):
		raise AssertionError("New account did not receive a complete IFRS 18 suggestion")
	if suggested["source"] != "Automatic new-account suggestion" or not suggested["review_required"]:
		raise AssertionError("New account was not marked for user mapping confirmation")

	doc.custom_ifrs18_mapping_locked = 1
	doc.save(ignore_permissions=True)
	doc.reload()
	confirmed = {
		"source": doc.custom_ifrs18_mapping_source,
		"confidence": doc.custom_ifrs18_mapping_confidence,
		"review_required": doc.custom_ifrs18_mapping_review_required,
		"locked": doc.custom_ifrs18_mapping_locked,
	}
	if confirmed != {
		"source": "Manual review",
		"confidence": "Manually reviewed",
		"review_required": 0,
		"locked": 1,
	}:
		raise AssertionError(f"Mapping confirmation state is incorrect: {confirmed}")

	current_from, current_to = "2026-03-07", "2026-04-05"
	comparative_from, comparative_to = "2026-01-06", "2026-02-04"
	company_doc = frappe.get_doc("Company", company)
	filters = _filters(company_doc, current_from, current_to, comparative_from, comparative_to)
	baseline, _, _ = _run("Profit and Loss Statement", filters)
	baseline_value = _value(baseline, doc.custom_ifrs18_line_item, "current_period")

	cash = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Cash", "is_group": 0, "disabled": 0},
		"name",
	) or frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Asset", "is_group": 0, "disabled": 0},
		"name",
	)
	cost_center = company_doc.cost_center or frappe.db.get_value(
		"Cost Center", {"company": company, "is_group": 0}, "name"
	)
	expense_row = {
		"account": doc.name,
		"debit_in_account_currency": 13,
		"cost_center": cost_center,
	}
	if frappe.db.has_column("Journal Entry Account", "tax_nature"):
		expense_row["tax_nature"] = "Operating Expense"
	voucher = frappe.get_doc({
		"doctype": "Journal Entry",
		"company": company,
		"posting_date": current_to,
		"user_remark": "IFRS18-NEW-ACCOUNT-MAPPING",
		"accounts": [
			expense_row,
			{"account": cash, "credit_in_account_currency": 13},
		],
	})
	try:
		voucher.insert(ignore_permissions=True)
		voucher.submit()
		after, _, _ = _run("Profit and Loss Statement", filters)
		report_delta = _value(after, doc.custom_ifrs18_line_item, "current_period") - baseline_value
		if abs(abs(report_delta) - 13) > 0.001:
			raise AssertionError(f"New mapped expense affected the report by {report_delta}, expected 13")
	finally:
		if voucher.name and frappe.db.exists("Journal Entry", voucher.name):
			voucher.reload()
			if voucher.docstatus == 1:
				voucher.cancel()

	doc.reload()
	doc.disabled = 1
	doc.save(ignore_permissions=True)
	return {
		"suggested": suggested,
		"confirmed": confirmed,
		"report_line": doc.custom_ifrs18_line_item,
		"report_delta": report_delta,
		"test_voucher_cancelled": True,
		"test_account_disabled": True,
		"audit_note": "Account retained because VerityGuard VG Financial Mapping is linked.",
	}
