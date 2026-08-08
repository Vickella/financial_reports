import frappe
from frappe.tests.utils import FrappeTestCase

from financial_reports.financial_reports.doctype.ifrs_18_management_performance_measure.ifrs_18_management_performance_measure import (
	MPM_PRESETS,
	_matches_scope,
)
from financial_reports.financial_reports.report.cash_flow.cash_flow import (
	_period_rows,
	_replace_direct_activity_rows,
)


class TestManagementPerformanceMeasurePresets(FrappeTestCase):
	def test_common_measure_presets_are_available(self):
		expected = {
			"EBIT", "EBITDA", "Adjusted EBITDA", "Adjusted operating profit",
			"Adjusted profit before tax", "Adjusted profit after tax",
		}
		self.assertEqual(set(MPM_PRESETS), expected)
		self.assertTrue(all(preset.get("comparable_subtotal") for preset in MPM_PRESETS.values()))

	def test_adjustment_scope_uses_mapping_and_account_labels(self):
		depreciation = frappe._dict(
			account_name="Depreciation expense", custom_ifrs18_line_item="",
			custom_ifrs18_category="Operating",
		)
		finance_cost = frappe._dict(
			account_name="Interest expense", custom_ifrs18_line_item="Finance costs",
			custom_ifrs18_category="Financing",
		)
		self.assertTrue(_matches_scope(depreciation, "depreciation"))
		self.assertTrue(_matches_scope(finance_cost, "financing"))
		self.assertFalse(_matches_scope(finance_cost, "depreciation"))


class TestCashFlowPresentation(FrappeTestCase):
	def test_period_rows_remove_spacers_and_merge_duplicate_totals(self):
		rows = [
			{"section": "Net Change in Cash", "period": 0},
			{},
			{"section": "Net Change in Cash", "period": 125},
		]
		order, normalised = _period_rows(rows, "period")
		self.assertEqual(order, [("Net Change in Cash", "")])
		self.assertEqual(normalised[order[0]]["period"], 125)

	def test_direct_activity_rows_replace_non_cash_erp_movements(self):
		investing_total = {"section": "Net cash flows from investing activities"}
		financing_total = {"section": "Net cash flows from financing activities"}
		data = [
			{"section": "Investing activities"},
			{"section": "Legacy non-cash investing movement"},
			investing_total,
			{"section": "Financing activities"},
			{"section": "Legacy financing movement"},
			financing_total,
		]
		periods = [frappe._dict(key="current_period")]
		details = {
			("Investing", "Property, plant and equipment"): {
				"current_period": -22000
			},
			("Financing", "Issued capital"): {"current_period": 50000},
		}
		_replace_direct_activity_rows(
			data,
			{"Investing": investing_total, "Financing": financing_total},
			periods,
			details,
			"USD",
		)
		labels = [row["section"] for row in data]
		self.assertNotIn("Legacy non-cash investing movement", labels)
		self.assertNotIn("Legacy financing movement", labels)
		self.assertIn("Property, plant and equipment", labels)
		self.assertIn("Issued capital", labels)
