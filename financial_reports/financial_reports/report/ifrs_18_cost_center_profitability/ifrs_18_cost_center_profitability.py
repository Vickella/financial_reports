import frappe
from frappe import _
from frappe.utils import flt

from financial_reports.reporting import get_periods, prepare_filters


def execute(filters=None):
	filters = prepare_filters(filters)
	periods = get_periods(filters)
	centres = {}
	for period in periods:
		rows = frappe.db.sql(
			"""select coalesce(gle.cost_center, %(unallocated)s) cost_center,
				a.custom_ifrs18_category category, a.root_type, sum(gle.debit-gle.credit) amount
			from `tabGL Entry` gle inner join `tabAccount` a on a.name=gle.account
			where gle.company=%(company)s and gle.posting_date between %(from_date)s and %(to_date)s
			and gle.is_cancelled=0 and a.root_type in ('Income','Expense')
			group by gle.cost_center, a.custom_ifrs18_category, a.root_type""",
			{"company": filters.company, "from_date": period.from_date, "to_date": period.to_date, "unallocated": _("Unallocated")},
			as_dict=True,
		)
		for item in rows:
			centre = centres.setdefault(item.cost_center, {"cost_center": item.cost_center})
			centre.setdefault(f"{period.key}_revenue", 0)
			centre.setdefault(f"{period.key}_operating_profit", 0)
			centre.setdefault(f"{period.key}_profit", 0)
			statement_amount = flt(item.amount) * (-1 if item.root_type == "Income" else -1)
			if item.root_type == "Income":
				statement_amount = -flt(item.amount)
			else:
				statement_amount = -flt(item.amount)
			centre[f"{period.key}_profit"] += statement_amount
			if item.category == "Operating":
				centre[f"{period.key}_operating_profit"] += statement_amount
			if item.root_type == "Income" and item.category == "Operating":
				centre[f"{period.key}_revenue"] += -flt(item.amount)
	data = list(centres.values())
	for row in data:
		for period in periods:
			revenue = row.get(f"{period.key}_revenue", 0)
			row[f"{period.key}_operating_margin"] = row.get(f"{period.key}_operating_profit", 0) / revenue * 100 if revenue else 0
	columns = [{"fieldname":"cost_center","label":_("Cost Center"),"fieldtype":"Link","options":"Cost Center","width":220}]
	for period in periods:
		columns.extend([
			{"fieldname":f"{period.key}_revenue","label":_("{0} revenue").format(period.label),"fieldtype":"Currency","width":170},
			{"fieldname":f"{period.key}_operating_profit","label":_("{0} operating profit").format(period.label),"fieldtype":"Currency","width":190},
			{"fieldname":f"{period.key}_operating_margin","label":_("{0} margin").format(period.label),"fieldtype":"Percent","width":150},
			{"fieldname":f"{period.key}_profit","label":_("{0} profit").format(period.label),"fieldtype":"Currency","width":170},
		])
	latest = periods[-1].key
	chart = {"data":{"labels":[r["cost_center"] for r in data],"datasets":[{"name":_("Operating profit"),"values":[r.get(f"{latest}_operating_profit", 0) for r in data]}]},"type":"bar"}
	return columns, data, None, chart
