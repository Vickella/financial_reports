import frappe
from frappe.tests.utils import FrappeTestCase

from financial_reports.mapping import infer_mapping


class TestIFRS18Mapping(FrappeTestCase):
	def test_revenue_maps_to_operating(self):
		mapping = infer_mapping(frappe._dict(
			name="Sales - TEST", account_name="Sales", account_type="Income Account", root_type="Income"
		))
		self.assertEqual(mapping.category, "Operating")
		self.assertEqual(mapping.line_item, "Revenue from contracts with customers")

	def test_interest_expense_maps_to_financing(self):
		mapping = infer_mapping(frappe._dict(
			name="Interest on Loans - TEST", account_name="Interest on Loans", account_type="Expense Account", root_type="Expense"
		))
		self.assertEqual(mapping.category, "Financing")

	def test_receivable_maps_to_current_assets(self):
		mapping = infer_mapping(frappe._dict(
			name="Debtors - TEST", account_name="Debtors", account_type="Receivable", root_type="Asset"
		))
		self.assertEqual(mapping.category, "Current assets")
		self.assertEqual(mapping.cash_flow, "Operating")

	def test_fixed_asset_maps_to_investing(self):
		mapping = infer_mapping(frappe._dict(
			name="Plant - TEST", account_name="Plant", account_type="Fixed Asset", root_type="Asset"
		))
		self.assertEqual(mapping.category, "Non-current assets")
		self.assertEqual(mapping.cash_flow, "Investing")

	def test_biological_asset_is_not_property_plant_and_equipment(self):
		mapping = infer_mapping(frappe._dict(
			name="Biological Asset - Maize - TEST",
			account_name="Biological Asset - Maize",
			account_type="Fixed Asset",
			root_type="Asset",
		))
		self.assertEqual((mapping.category, mapping.line_item),
			("Non-current assets", "Biological assets"))
