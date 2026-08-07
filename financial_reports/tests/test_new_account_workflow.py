import frappe
from frappe.tests.utils import FrappeTestCase

from financial_reports.mapping import infer_mapping, validate_account_mapping


class TestNewAccountMappingWorkflow(FrappeTestCase):
	def test_expense_suggestion_is_complete(self):
		account = frappe._dict(
			name="Advertising - TEST",
			account_name="Advertising",
			account_type="Expense Account",
			root_type="Expense",
			is_group=0,
		)
		mapping = infer_mapping(account)
		self.assertEqual(mapping.category, "Operating")
		self.assertEqual(mapping.line_item, "Selling expenses")
		self.assertEqual(mapping.expense_nature, "Marketing expenses")

	def test_confirmation_clears_review_state(self):
		if not frappe.db.has_column("Account", "custom_ifrs18_mapping_review_required"):
			self.skipTest("Custom fields have not been installed")
		account = frappe._dict(
			name="New Service Cost - TEST",
			account_name="New Service Cost",
			account_type="Expense Account",
			root_type="Expense",
			is_group=0,
			custom_ifrs18_category="Operating",
			custom_ifrs18_line_item="Administrative and other operating expenses",
			custom_ifrs18_cash_flow_activity="Operating",
			custom_ifrs18_mapping_locked=1,
			custom_ifrs18_mapping_review_required=1,
			custom_ifrs18_mapping_source="Automatic new-account suggestion",
		)
		validate_account_mapping(account)
		self.assertEqual(account.custom_ifrs18_mapping_review_required, 0)
		self.assertEqual(account.custom_ifrs18_mapping_confidence, "Manually reviewed")
		self.assertEqual(account.custom_ifrs18_mapping_source, "Manual review")
