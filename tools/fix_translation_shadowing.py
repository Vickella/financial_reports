"""Replace throwaway underscore assignments that shadow frappe._ at runtime."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
replacements = {
	"financial_reports/reporting.py": [
		('periods, aggregates, _ = aggregate_accounts(filters, ("Income", "Expense"))', 'periods, aggregates, account_rows = aggregate_accounts(filters, ("Income", "Expense"))'),
		('periods, aggregates, _ = aggregate_accounts(filters, ("Asset", "Liability", "Equity"))', 'periods, aggregates, account_rows = aggregate_accounts(filters, ("Asset", "Liability", "Equity"))'),
	],
	"financial_reports/financial_reports/report/ifrs_18_working_capital_analysis/ifrs_18_working_capital_analysis.py": [
		('periods, aggregates, _ = aggregate_accounts(filters, ("Asset", "Liability"))', 'periods, aggregates, account_rows = aggregate_accounts(filters, ("Asset", "Liability"))'),
	],
	"financial_reports/financial_reports/report/ifrs_18_financial_ratios/ifrs_18_financial_ratios.py": [
		('_, pnl, _ = aggregate_accounts(pl_filters, ("Income", "Expense"))', 'pnl_periods, pnl, pnl_accounts = aggregate_accounts(pl_filters, ("Income", "Expense"))'),
		('_, position, _ = aggregate_accounts(bs_filters, ("Asset", "Liability", "Equity"))', 'position_periods, position, position_accounts = aggregate_accounts(bs_filters, ("Asset", "Liability", "Equity"))'),
	],
	"financial_reports/financial_reports/report/ifrs_18_statement_of_comprehensive_income/ifrs_18_statement_of_comprehensive_income.py": [
		('columns, data, _, _, _ = profit_or_loss(filters)', 'columns, data, message, chart, report_summary = profit_or_loss(filters)'),
		('periods, aggregates, _ = aggregate_accounts(filters, ("Income", "Expense"))', 'periods, aggregates, account_rows = aggregate_accounts(filters, ("Income", "Expense"))'),
	],
	"financial_reports/financial_reports/report/cash_flow/cash_flow.py": [
		('periods, aggregates, _ = aggregate_accounts(filters, ("Income", "Expense"))', 'periods, aggregates, account_rows = aggregate_accounts(filters, ("Income", "Expense"))'),
	],
	"financial_reports/financial_reports/report/ifrs_18_statement_of_changes_in_equity/ifrs_18_statement_of_changes_in_equity.py": [
		('_, aggregates, _ = aggregate_accounts(pl_filters, ("Income", "Expense"))', 'pnl_periods, aggregates, pnl_accounts = aggregate_accounts(pl_filters, ("Income", "Expense"))'),
	],
}

for relative_path, changes in replacements.items():
	path = ROOT / relative_path
	content = path.read_text(encoding="utf-8")
	for old, new in changes:
		if old not in content and new not in content:
			raise RuntimeError(f"Expected assignment not found in {relative_path}: {old}")
		content = content.replace(old, new)
	path.write_text(content, encoding="utf-8")

print("Translation shadowing fixed")
