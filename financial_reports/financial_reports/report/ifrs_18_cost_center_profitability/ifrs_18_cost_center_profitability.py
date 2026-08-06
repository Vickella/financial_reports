import frappe
from frappe import _
from frappe.utils import flt

from financial_reports.reporting import get_periods, prepare_filters


def execute(filters=None):
	filters = prepare_filters(filters)
	periods = get_periods(filters)
	rows = frappe.db.sql(
		"""select coalesce(gle.cost_center, %(unallocated)s) cost_center,
			a.custom_ifrs18_category category, a.custom_ifrs18_line_item line_item,
			a.root_type, sum(gle.debit-gle.credit) amount
		from `tabGL Entry` gle inner join `tabAccount` a on a.name=gle.account
		where gle.company=%(company)s and gle.posting_date between %(from_date)s and %(to_date)s
		and gle.is_cancelled=0 and a.root_type in ('Income','Expense')
		group by gle.cost_center, a.custom_ifrs18_category, a.custom_ifrs18_line_item, a.root_type""",
		{"company": filters.company, "from_date": periods[0].from_date, "to_date": periods[-1].to_date, "unallocated": _("Unallocated")},
		as_dict=True,
	)
	centres = {}
	for row in rows:
		centre = centres.setdefault(row.cost_center, {"cost_center": row.cost_center, "revenue": 0, "operating_profit": 0, "profit": 0})
		amount = flt(row.amount) * (-1 if row.root_type == "Income" else 1)
		contribution = -amount if row.root_type == "Expense" else amount
		centre["profit"] += contribution
		if row.category == "Operating":
			centre["operating_profit"] += contribution
		if row.root_type == "Income" and row.category == "Operating":
			centre["revenue"] += amount
	data = list(centres.values())
	for row in data:
		row["operating_margin"] = row["operating_profit"] / row["revenue"] * 100 if row["revenue"] else 0
	columns = [
		{"fieldname":"cost_center","label":_("Cost Center"),"fieldtype":"Link","options":"Cost Center","width":240},
		{"fieldname":"revenue","label":_("Operating revenue"),"fieldtype":"Currency","width":150},
		{"fieldname":"operating_profit","label":_("Operating profit"),"fieldtype":"Currency","width":150},
		{"fieldname":"operating_margin","label":_("Operating margin"),"fieldtype":"Percent","width":130},
		{"fieldname":"profit","label":_("Profit"),"fieldtype":"Currency","width":150},
	]
	chart = {"data":{"labels":[r["cost_center"] for r in data],"datasets":[{"name":_("Operating profit"),"values":[r["operating_profit"] for r in data]}]},"type":"bar"}
	return columns, data, None, chart

