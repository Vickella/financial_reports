import frappe
from frappe.tests.utils import FrappeTestCase

from financial_reports.mapping import infer_mapping


class TestDefaultERPNextChartMapping(FrappeTestCase):
	def mapping(self, name, root_type, account_type=""):
		return infer_mapping(frappe._dict(
			name=f"{name} - TEST", account_name=name, root_type=root_type,
			account_type=account_type, is_group=0,
		))

	def test_capital_work_in_progress(self):
		mapping = self.mapping("CWIP Account", "Asset", "Capital Work in Progress")
		self.assertEqual((mapping.category, mapping.line_item, mapping.cash_flow),
			("Non-current assets", "Property, plant and equipment", "Investing"))

	def test_stock_received_not_billed(self):
		mapping = self.mapping("Stock Received But Not Billed", "Liability", "Stock Received But Not Billed")
		self.assertEqual(mapping.line_item, "Trade and other payables")

	def test_sales_commission(self):
		mapping = self.mapping("Commission on Sales", "Expense")
		self.assertEqual((mapping.line_item, mapping.expense_nature), ("Selling expenses", "Marketing expenses"))

	def test_valuation_expense(self):
		mapping = self.mapping("Expenses Included In Valuation", "Expense", "Expenses Included In Valuation")
		self.assertEqual(mapping.line_item, "Cost of sales")

	def test_tax_penalty_is_not_income_tax(self):
		mapping = self.mapping("Tax Penalty Expense", "Expense", "Expense Account")
		self.assertEqual(mapping.category, "Operating")
		self.assertEqual(mapping.expense_nature, "Taxes and penalties")

	def test_opening_equity(self):
		mapping = self.mapping("Opening Balance Equity", "Equity", "Equity")
		self.assertEqual(mapping.line_item, "Retained earnings")
