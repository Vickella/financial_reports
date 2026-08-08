import frappe
from frappe import _
from frappe.model.document import Document


MPM_PRESETS = {
	"EBIT": {
		"comparable_subtotal": "Profit before income tax",
		"reason_for_use": "Management uses EBIT to assess performance before financing structure and income taxes.",
		"calculation_description": "Profit before income tax adjusted for financing income and expenses.",
		"account_scope": "financing",
	},
	"EBITDA": {
		"comparable_subtotal": "Operating profit",
		"reason_for_use": "Management uses EBITDA to assess operating performance before depreciation and amortisation.",
		"calculation_description": "Operating profit before depreciation and amortisation expenses.",
		"account_scope": "depreciation",
	},
	"Adjusted EBITDA": {
		"comparable_subtotal": "Operating profit",
		"reason_for_use": "Management uses adjusted EBITDA to assess underlying operating performance before depreciation, amortisation and identified adjusting items.",
		"calculation_description": "Operating profit before depreciation and amortisation, adjusted for separately identified non-recurring or non-core items.",
		"account_scope": "depreciation_and_adjusting",
	},
	"Adjusted operating profit": {
		"comparable_subtotal": "Operating profit",
		"reason_for_use": "Management uses adjusted operating profit to evaluate sustainable performance from core operations.",
		"calculation_description": "Operating profit adjusted for separately identified non-recurring or non-core operating items.",
		"account_scope": "operating_adjusting",
	},
	"Adjusted profit before tax": {
		"comparable_subtotal": "Profit before income tax",
		"reason_for_use": "Management uses adjusted profit before tax to assess underlying pre-tax financial performance.",
		"calculation_description": "Profit before income tax adjusted for separately identified non-recurring or non-core items.",
		"account_scope": "adjusting",
	},
	"Adjusted profit after tax": {
		"comparable_subtotal": "Profit",
		"reason_for_use": "Management uses adjusted profit after tax to assess underlying earnings attributable to the reporting period.",
		"calculation_description": "Profit adjusted for separately identified items, their income-tax effects and NCI effects.",
		"account_scope": "adjusting",
	},
}

_DEPRECIATION_TERMS = ("depreciation", "amortisation", "amortization")
_ADJUSTING_TERMS = (
	"impairment", "restructuring", "exceptional", "non-recurring", "nonrecurring",
	"disposal", "government grant",
)


def _matches_scope(account, scope):
	label = " ".join(filter(None, (account.account_name, account.custom_ifrs18_line_item))).lower()
	is_depreciation = any(term in label for term in _DEPRECIATION_TERMS)
	is_adjusting = any(term in label for term in _ADJUSTING_TERMS)
	if scope == "depreciation":
		return is_depreciation
	if scope == "depreciation_and_adjusting":
		return is_depreciation or is_adjusting
	if scope == "operating_adjusting":
		return account.custom_ifrs18_category == "Operating" and is_adjusting
	if scope == "financing":
		return account.custom_ifrs18_category == "Financing"
	return is_adjusting


@frappe.whitelist()
def get_mpm_preset(company, measure_template):
	"""Return a common MPM definition and reviewable account suggestions."""
	frappe.has_permission("IFRS 18 Management Performance Measure", ptype="write", throw=True)
	if not company or measure_template not in MPM_PRESETS:
		frappe.throw(_("Select a company and a supported common measure template."))
	preset = dict(MPM_PRESETS[measure_template])
	scope = preset.pop("account_scope")
	accounts = frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 0, "root_type": ["in", ["Income", "Expense"]]},
		fields=["name", "account_name", "root_type", "custom_ifrs18_category", "custom_ifrs18_line_item"],
		order_by="lft",
	)
	adjustments = []
	for account in accounts:
		if not _matches_scope(account, scope):
			continue
		is_expense = account.root_type == "Expense"
		adjustments.append({
			"adjustment_label": _("Add back {0}").format(account.account_name) if is_expense else _("Remove {0}").format(account.account_name),
			"account": account.name,
			"treatment": "Add" if is_expense else "Subtract",
			"tax_rate": 0,
			"nci_effect": 0,
		})
	preset["adjustments"] = adjustments
	return preset


class IFRS18ManagementPerformanceMeasure(Document):
	def validate(self):
		seen = set()
		for adjustment in self.adjustments:
			if adjustment.account in seen:
				frappe.throw(_("Account {0} appears more than once in the reconciliation table.").format(adjustment.account))
			seen.add(adjustment.account)
			account_company = frappe.get_cached_value("Account", adjustment.account, "company")
			if account_company != self.company:
				frappe.throw(_("Adjustment account {0} does not belong to company {1}.").format(adjustment.account, self.company))

