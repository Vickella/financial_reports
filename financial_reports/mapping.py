"""IFRS 18 account classification and deterministic chart-of-accounts defaults."""

from __future__ import annotations

import re
from dataclasses import dataclass

import frappe


BALANCE_CATEGORIES = (
	"Non-current assets",
	"Current assets",
	"Equity",
	"Non-current liabilities",
	"Current liabilities",
)
PERFORMANCE_CATEGORIES = (
	"Operating",
	"Investing",
	"Financing",
	"Income taxes",
	"Discontinued operations",
	"Other comprehensive income - reclassifiable",
	"Other comprehensive income - non-reclassifiable",
)
ALL_CATEGORIES = BALANCE_CATEGORIES + PERFORMANCE_CATEGORIES
CASH_FLOW_ACTIVITIES = ("Operating", "Investing", "Financing", "Cash and cash equivalents", "Non-cash")


@dataclass(frozen=True)
class Mapping:
	category: str
	line_item: str
	cash_flow: str = "Operating"
	expense_nature: str = ""
	note: str = ""
	confidence: str = "Rule based"


def _contains(text: str, *terms: str) -> bool:
	return any(re.search(term, text, re.IGNORECASE) for term in terms)


def infer_mapping(account) -> Mapping:
	"""Infer a conservative IFRS 18 mapping from ERPNext account metadata and name."""
	name = " ".join(filter(None, [account.get("account_name"), account.get("name"), account.get("account_type")]))
	root = account.get("root_type")
	type_ = account.get("account_type") or ""

	if root == "Asset":
		if _contains(name, "biological asset"):
			return Mapping("Non-current assets", "Biological assets", "Investing", note="Biological assets")
		if type_ == "Cash" or _contains(name, r"\bcash\b", r"bank"):
			return Mapping("Current assets", "Cash and cash equivalents", "Cash and cash equivalents", note="Cash and short-term deposits")
		if type_ == "Receivable" or _contains(name, "receivable", "contract asset"):
			return Mapping("Current assets", "Trade and other receivables", "Operating", note="Trade receivables and contract assets")
		if type_ == "Stock" or _contains(name, "inventory", "stock"):
			return Mapping("Current assets", "Inventories", "Operating", note="Inventories")
		if type_ in {"Fixed Asset", "Accumulated Depreciation", "Capital Work in Progress"} or _contains(
			name, "property", "equipment", "right.of.use", "fixed asset", "accumulated depreciation", r"\bcwip\b", "work in progress"
		):
			return Mapping("Non-current assets", "Property, plant and equipment", "Investing", note="Property, plant and equipment")
		if _contains(name, "goodwill"):
			return Mapping("Non-current assets", "Goodwill", "Investing", note="Intangible assets and goodwill")
		if _contains(name, "intangible", "development cost"):
			return Mapping("Non-current assets", "Intangible assets", "Investing", note="Intangible assets and goodwill")
		if _contains(name, "investment propert"):
			return Mapping("Non-current assets", "Investment properties", "Investing", note="Investment properties")
		if _contains(name, "investment", "associate", "joint venture"):
			return Mapping("Non-current assets", "Investments and other financial assets", "Investing", note="Financial assets")
		if _contains(name, "deferred tax"):
			return Mapping("Non-current assets", "Deferred tax assets", "Non-cash", note="Income tax")
		if _contains(name, "prepayment", "advance", "deposit", "earnest money"):
			return Mapping("Current assets", "Prepayments and other current assets", "Operating")
		if _contains(name, "tax asset"):
			return Mapping("Current assets", "Current tax assets", "Operating", note="Income tax")
		if _contains(name, "current asset", "application of funds", "temporary"):
			return Mapping("Current assets", "Other current assets", "Operating")
		return Mapping("Current assets", "Other current assets", "Operating", confidence="Fallback")

	if root == "Liability":
		if type_ == "Payable" or _contains(name, "payable", "creditor", "contract liab"):
			return Mapping("Current liabilities", "Trade and other payables", "Operating", note="Trade, other and related party payables")
		if _contains(name, "deferred tax"):
			return Mapping("Non-current liabilities", "Deferred tax liabilities", "Non-cash", note="Income tax")
		if _contains(name, "tax", "vat", "withholding"):
			return Mapping("Current liabilities", "Current tax liabilities", "Operating", note="Income tax")
		if _contains(name, "lease", "loan", "borrow", "overdraft", "mortgage"):
			category = "Current liabilities" if _contains(name, "current", "short.term", "overdraft") else "Non-current liabilities"
			return Mapping(category, "Interest-bearing loans, borrowings and lease liabilities", "Financing", note="Financial liabilities")
		if _contains(name, "provision", "pension", "employee benefit"):
			return Mapping("Non-current liabilities", "Provisions and employee benefit obligations", "Operating", note="Provisions and employee benefits")
		if type_ in {"Asset Received But Not Billed", "Stock Received But Not Billed"} or _contains(
			name, "received but not billed", "stock liabilities", "input clearing"
		):
			return Mapping("Current liabilities", "Trade and other payables", "Operating", note="Trade, other and related party payables")
		if _contains(name, "current liabilities", "source of funds"):
			return Mapping("Current liabilities", "Other current liabilities", "Operating")
		return Mapping("Current liabilities", "Other current liabilities", "Operating", confidence="Fallback")

	if root == "Equity":
		if _contains(name, "dividend", "opening balance equity"):
			return Mapping("Equity", "Retained earnings", "Financing", note="Issued capital and reserves")
		if _contains(name, "share", "capital", "common stock"):
			return Mapping("Equity", "Issued capital", "Financing", note="Issued capital and reserves")
		if _contains(name, "retained", "profit", "loss"):
			return Mapping("Equity", "Retained earnings", "Financing", note="Issued capital and reserves")
		if _contains(name, "reserve", "surplus", "translation"):
			return Mapping("Equity", "Other reserves", "Financing", note="Issued capital and reserves")
		if _contains(name, r"\bequity\b"):
			return Mapping("Equity", "Other equity", "Financing", note="Issued capital and reserves")
		return Mapping("Equity", "Other equity", "Financing", confidence="Fallback")

	if root == "Income":
		if _contains(name, "discontinued"):
			return Mapping("Discontinued operations", "Profit/(loss) after tax from discontinued operations", "Operating")
		if _contains(name, "interest income", "dividend", "rental income", "fair value", "investment income", "associate", "joint venture"):
			return Mapping("Investing", "Income from investments", "Investing", note="Other income and expenses")
		if _contains(name, "other comprehensive", "cash flow hedge", "foreign operation", "fvoci"):
			return Mapping("Other comprehensive income - reclassifiable", "Items that may be reclassified to profit or loss", "Non-cash")
		if type_ == "Income Account" or _contains(name, "sales", "revenue", "service", "fee"):
			return Mapping("Operating", "Revenue from contracts with customers", "Operating", note="Revenue from contracts with customers")
		if _contains(name, "direct income", "indirect income", r"\bincome\b"):
			return Mapping("Operating", "Other operating income", "Operating", note="Other income and expenses")
		return Mapping("Operating", "Other operating income", "Operating", note="Other income and expenses", confidence="Fallback")

	if root == "Expense":
		if _contains(name, "tax penalty"):
			return Mapping("Operating", "Administrative and other operating expenses", "Operating", "Taxes and penalties", "Other income and expenses")
		if _contains(name, "income tax", "corporate tax", "tax expenses"):
			return Mapping("Income taxes", "Income tax expense", "Operating", "Tax expense", "Income tax")
		if _contains(name, "discontinued"):
			return Mapping("Discontinued operations", "Profit/(loss) after tax from discontinued operations", "Operating")
		if type_ == "Cost of Goods Sold" or _contains(name, "cost of sales", "cost of goods", "direct cost"):
			return Mapping("Operating", "Cost of sales", "Operating", "Cost of inventories", "Specified expenses by nature")
		if type_ == "Depreciation" or _contains(name, "depreciation", "amortisation", "amortization"):
			return Mapping("Operating", "Depreciation and amortisation", "Operating", "Depreciation and amortisation", "Specified expenses by nature")
		if _contains(name, "interest", "finance cost", "bank charge"):
			return Mapping("Financing", "Interest expense on borrowings and other liabilities", "Financing", "Finance costs", "Financial liabilities")
		if _contains(name, "research", "development"):
			return Mapping("Operating", "Research and development expenses", "Operating", "Research and development", "Research and development costs")
		if _contains(name, "selling", "marketing", "advert", "sales expense", "commission on sales"):
			return Mapping("Operating", "Selling expenses", "Operating", "Marketing expenses", "Specified expenses by nature")
		if _contains(name, "distribution", "freight", "delivery"):
			return Mapping("Operating", "Distribution expenses", "Operating", "Distribution expenses", "Specified expenses by nature")
		if _contains(name, "salary", "wage", "employee", "payroll", "staff"):
			return Mapping("Operating", "Administrative expenses", "Operating", "Employee benefits", "Specified expenses by nature")
		if _contains(name, "impairment", "write.down", "write off"):
			return Mapping("Operating", "Impairment losses", "Non-cash", "Impairment losses", "Specified expenses by nature")
		if type_ in {"Expenses Included In Asset Valuation", "Expenses Included In Valuation", "Stock Adjustment"} or _contains(
			name, "harvest purchases", "direct expenses", "stock expenses", "included in valuation"
		):
			return Mapping("Operating", "Cost of sales", "Operating", "Cost of inventories", "Specified expenses by nature")
		if _contains(name, "biological asset fair value"):
			return Mapping("Operating", "Other operating income and expenses", "Non-cash", "Fair value movements", "Other income and expenses")
		if _contains(name, "exchange gain", "asset disposal"):
			return Mapping("Operating", "Other operating income and expenses", "Operating", "Other operating expenses", "Other income and expenses")
		if _contains(name, "medical aid"):
			return Mapping("Operating", "Administrative expenses", "Operating", "Employee benefits", "Specified expenses by nature")
		if _contains(
			name, "administrative expenses", "indirect expenses", r"\bexpenses\b", "entertainment", "legal expenses",
			"miscellaneous", "office maintenance", "office rent", "postal", "stationery", "round off", "telephone", "travel", "utility"
		):
			return Mapping("Operating", "Administrative and other operating expenses", "Operating", "Other operating expenses", "Other income and expenses")
		return Mapping("Operating", "Administrative and other operating expenses", "Operating", "Other operating expenses", "Other income and expenses", "Fallback")

	return Mapping("Operating", "Unclassified", "Operating", confidence="Fallback")


def apply_mapping(
	account, force: bool = False, *, source: str = "Automatic installation rule", review_required: bool = False
) -> bool:
	if not frappe.db.has_column("Account", "custom_ifrs18_category"):
		return False
	if account.get("custom_ifrs18_mapping_locked") and not force:
		return False
	if account.get("custom_ifrs18_category") and not force:
		return False

	mapping = infer_mapping(account)
	values = {
		"custom_ifrs18_category": mapping.category,
		"custom_ifrs18_line_item": mapping.line_item,
		"custom_ifrs18_cash_flow_activity": mapping.cash_flow,
		"custom_ifrs18_expense_nature": mapping.expense_nature,
		"custom_ifrs18_note_reference": mapping.note,
		"custom_ifrs18_mapping_source": source,
		"custom_ifrs18_mapping_confidence": mapping.confidence,
		"custom_ifrs18_mapping_review_required": int(review_required),
	}
	frappe.db.set_value("Account", account.name, values, update_modified=False)
	return True


def map_new_account(doc, method=None):
	apply_mapping(doc, source="Automatic new-account suggestion", review_required=True)


def validate_account_mapping(doc, method=None):
	"""Keep every posting account mapped and track explicit review of new accounts."""
	if not frappe.db.has_column("Account", "custom_ifrs18_category") or doc.get("is_group"):
		return

	required = (
		"custom_ifrs18_category",
		"custom_ifrs18_line_item",
		"custom_ifrs18_cash_flow_activity",
	)
	suggestion = infer_mapping(doc)
	if any(not doc.get(fieldname) for fieldname in required):
		doc.custom_ifrs18_category = doc.custom_ifrs18_category or suggestion.category
		doc.custom_ifrs18_line_item = doc.custom_ifrs18_line_item or suggestion.line_item
		doc.custom_ifrs18_cash_flow_activity = doc.custom_ifrs18_cash_flow_activity or suggestion.cash_flow
		doc.custom_ifrs18_expense_nature = doc.custom_ifrs18_expense_nature or suggestion.expense_nature
		doc.custom_ifrs18_note_reference = doc.custom_ifrs18_note_reference or suggestion.note

	is_new_method = getattr(doc, "is_new", None)
	is_new = bool(is_new_method()) if callable(is_new_method) else False
	if is_new and not doc.get("custom_ifrs18_mapping_source"):
		doc.custom_ifrs18_mapping_source = "Automatic new-account suggestion"
		doc.custom_ifrs18_mapping_confidence = suggestion.confidence
		doc.custom_ifrs18_mapping_review_required = 1

	if doc.get("custom_ifrs18_mapping_locked"):
		doc.custom_ifrs18_mapping_review_required = 0
		doc.custom_ifrs18_mapping_confidence = "Manually reviewed"
		doc.custom_ifrs18_mapping_source = "Manual review"
	elif doc.get("custom_ifrs18_mapping_source") == "Automatic new-account suggestion":
		doc.custom_ifrs18_mapping_review_required = 1


def map_all_accounts(force: bool = False) -> int:
	if not frappe.db.has_column("Account", "custom_ifrs18_category"):
		return 0
	fields = [
		"name", "account_name", "account_type", "root_type", "is_group",
		"custom_ifrs18_category", "custom_ifrs18_mapping_locked",
	]
	count = 0
	for account in frappe.get_all("Account", fields=fields):
		count += int(apply_mapping(account, force=force))
	return count



def remap_automatic_biological_assets() -> int:
	"""Move legacy automatic biological-asset mappings out of PPE without overriding user locks."""
	if not frappe.db.has_column("Account", "custom_ifrs18_category"):
		return 0
	fields = [
		"name", "account_name", "account_type", "root_type", "is_group",
		"custom_ifrs18_category", "custom_ifrs18_mapping_locked",
		"custom_ifrs18_mapping_source",
	]
	count = 0
	for account in frappe.get_all(
		"Account",
		filters={"root_type": "Asset", "custom_ifrs18_mapping_locked": 0,
			"custom_ifrs18_mapping_source": ["like", "Automatic%"]},
		fields=fields,
	):
		mapping = infer_mapping(account)
		if mapping.line_item != "Biological assets":
			continue
		count += int(apply_mapping(
			account, force=True, source="Automatic rule update: biological assets"
		))
	return count
