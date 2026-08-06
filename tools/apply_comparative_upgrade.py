"""Apply deterministic source upgrades where the Windows patch wrapper cannot update files."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
	file_path = ROOT / path
	content = file_path.read_text(encoding="utf-8")
	if new in content:
		return
	if old not in content:
		raise RuntimeError(f"Expected source block not found in {path}")
	file_path.write_text(content.replace(old, new), encoding="utf-8")


replace(
	"financial_reports/reporting.py",
	"from frappe.utils import flt\n\nfrom erpnext.accounts.report.financial_statements import get_columns, get_data, get_period_list\n",
	"from frappe.utils import flt, formatdate, getdate\n\nfrom erpnext.accounts.report.financial_statements import get_columns, get_data, get_period_list\nfrom erpnext.accounts.utils import get_fiscal_year\n",
)

replace(
	"financial_reports/reporting.py",
	'''def get_periods(filters):
\treturn get_period_list(
\t\tfilters.from_fiscal_year,
\t\tfilters.to_fiscal_year,
\t\tfilters.period_start_date,
\t\tfilters.period_end_date,
\t\tfilters.filter_based_on,
\t\tfilters.periodicity,
\t\tcompany=filters.company,
\t)
''',
	'''def get_periods(filters):
\tif filters.get("comparison_enabled"):
\t\trequired = ("period_start_date", "period_end_date", "comparison_from_date", "comparison_to_date")
\t\tif any(not filters.get(field) for field in required):
\t\t\tfrappe.throw(_("Current and comparative start and end dates are required."))
\t\tcurrent_from = getdate(filters.period_start_date)
\t\tcurrent_to = getdate(filters.period_end_date)
\t\tcomparison_from = getdate(filters.comparison_from_date)
\t\tcomparison_to = getdate(filters.comparison_to_date)
\t\tif current_to < current_from or comparison_to < comparison_from:
\t\t\tfrappe.throw(_("The end of each reporting range must be on or after its start."))
\t\tearliest = min(current_from, comparison_from)
\t\tlatest = max(current_to, comparison_to)
\t\tperiods = []
\t\tfor key, label, from_date, to_date in (
\t\t\t("comparative_period", _("Comparative"), comparison_from, comparison_to),
\t\t\t("current_period", _("Current"), current_from, current_to),
\t\t):
\t\t\tfiscal_year = get_fiscal_year(to_date, company=filters.company)
\t\t\tperiods.append(frappe._dict(
\t\t\t\tfrom_date=from_date,
\t\t\t\tto_date=to_date,
\t\t\t\tkey=key,
\t\t\t\tlabel=f"{label} ({formatdate(from_date)} – {formatdate(to_date)})",
\t\t\t\tyear_start_date=earliest,
\t\t\t\tyear_end_date=latest,
\t\t\t\tto_date_fiscal_year=fiscal_year[0],
\t\t\t\tfrom_date_fiscal_year_start_date=fiscal_year[1],
\t\t\t))
\t\treturn periods
\treturn get_period_list(
\t\tfilters.from_fiscal_year,
\t\tfilters.to_fiscal_year,
\t\tfilters.period_start_date,
\t\tfilters.period_end_date,
\t\tfilters.filter_based_on,
\t\tfilters.periodicity,
\t\tcompany=filters.company,
\t)
''',
)

replace(
	"financial_reports/reporting.py",
	'''\tfor period in periods:
\t\trow[period.key] = sum(flt(item.get(period.key)) for item in rows)
\trow["total"] = sum(flt(item.get("total")) for item in rows)
\treturn row
''',
	'''\tfor period in periods:
\t\trow[period.key] = sum(flt(item.get(period.key)) for item in rows)
\trow["total"] = row.get("current_period") if "current_period" in row else sum(flt(item.get("total")) for item in rows)
\treturn row
''',
)

replace(
	"financial_reports/reporting.py",
	'''\tperiods, aggregates, _ = aggregate_accounts(filters, ("Asset", "Liability", "Equity"))
\tcurrency = currency_for(filters)
\tdata = []
\tsection_totals = {}
\tfor category in POSITION_ORDER:
\t\trows = category_rows(aggregates, category, periods, currency)
''',
	'''\tperiods, aggregates, _ = aggregate_accounts(filters, ("Asset", "Liability", "Equity"))
\tcurrency = currency_for(filters)
\tdata = []
\tsection_totals = {}
\tfor category in POSITION_ORDER:
\t\trows = category_rows(aggregates, category, periods, currency)
\t\tif category == "Equity":
\t\t\tprofit_row = {
\t\t\t\t"account_name": _("Current period earnings"),
\t\t\t\t"account": _("Current period earnings"),
\t\t\t\t"line_item": _("Current period earnings"),
\t\t\t\t"currency": currency,
\t\t\t\t"indent": 1,
\t\t\t}
\t\t\tfor period in periods:
\t\t\t\tfy_start = get_fiscal_year(period.to_date, company=filters.company)[1]
\t\t\t\tprofit_row[period.key] = flt(frappe.db.sql("""
\t\t\t\t\tselect coalesce(sum(case when a.root_type='Income' then gle.credit-gle.debit
\t\t\t\t\t\twhen a.root_type='Expense' then gle.credit-gle.debit else 0 end), 0)
\t\t\t\t\tfrom `tabGL Entry` gle inner join `tabAccount` a on a.name=gle.account
\t\t\t\t\twhere gle.company=%s and gle.posting_date between %s and %s
\t\t\t\t\tand gle.is_cancelled=0 and gle.voucher_type != 'Period Closing Voucher'
\t\t\t\t""", (filters.company, fy_start, period.to_date))[0][0])
\t\t\tprofit_row["total"] = profit_row.get("current_period", profit_row.get(periods[-1].key, 0))
\t\t\trows.append(profit_row)
''',
)

print("Comparative reporting engine upgrade applied")
