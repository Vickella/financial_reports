import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company") or not filters.get("fiscal_year"):
		frappe.throw(_("Company and Fiscal Year are required"))
	fy = frappe.get_cached_doc("Fiscal Year", filters.fiscal_year)
	budgets = frappe.db.sql(
		"""select ba.account, sum(ba.budget_amount) as budget
		from `tabBudget Account` ba inner join `tabBudget` b on b.name=ba.parent
		where b.docstatus=1 and b.company=%s and b.fiscal_year=%s
		group by ba.account""",
		(filters.company, filters.fiscal_year), as_dict=True,
	)
	data = []
	for item in budgets:
		account = frappe.get_cached_value("Account", item.account, ["account_name", "root_type", "custom_ifrs18_category", "custom_ifrs18_line_item"], as_dict=True)
		actual = frappe.db.sql(
			"""select coalesce(sum(debit-credit),0) from `tabGL Entry`
			where company=%s and account=%s and posting_date between %s and %s and is_cancelled=0""",
			(filters.company, item.account, fy.year_start_date, fy.year_end_date),
		)[0][0]
		if account.root_type == "Income":
			actual *= -1
		variance = flt(actual) - flt(item.budget)
		favourable = variance >= 0 if account.root_type == "Income" else variance <= 0
		data.append({
			"account": item.account, "account_name": account.account_name,
			"category": account.custom_ifrs18_category, "line_item": account.custom_ifrs18_line_item,
			"budget": item.budget, "actual": actual, "variance": variance,
			"variance_percent": variance / item.budget * 100 if item.budget else 0,
			"status": _("Favourable") if favourable else _("Adverse"),
		})
	columns = [
		{"fieldname":"account","label":_("Account"),"fieldtype":"Link","options":"Account","width":220},
		{"fieldname":"category","label":_("IFRS 18 category"),"fieldtype":"Data","width":150},
		{"fieldname":"line_item","label":_("Line item"),"fieldtype":"Data","width":220},
		{"fieldname":"budget","label":_("Budget"),"fieldtype":"Currency","width":140},
		{"fieldname":"actual","label":_("Actual"),"fieldtype":"Currency","width":140},
		{"fieldname":"variance","label":_("Variance"),"fieldtype":"Currency","width":140},
		{"fieldname":"variance_percent","label":_("Variance %"),"fieldtype":"Percent","width":110},
		{"fieldname":"status","label":_("Status"),"fieldtype":"Data","width":100},
	]
	return columns, data

