"""Register shared report filters and attach them to financial reports."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

hooks = ROOT / "financial_reports/hooks.py"
content = hooks.read_text(encoding="utf-8")
line = 'app_include_js = "/assets/financial_reports/js/report_filters.js"\n'
if line not in content:
	content = content.replace('required_apps = ["erpnext"]\n', 'required_apps = ["erpnext"]\n\n' + line)
	hooks.write_text(content, encoding="utf-8")

reports = {
	"profit_and_loss_statement": "Profit and Loss Statement",
	"balance_sheet": "Balance Sheet",
	"cash_flow": "Cash Flow",
	"ifrs_18_statement_of_comprehensive_income": "IFRS 18 Statement of Comprehensive Income",
	"ifrs_18_statement_of_changes_in_equity": "IFRS 18 Statement of Changes in Equity",
	"ifrs_18_notes_schedule": "IFRS 18 Notes Schedule",
	"ifrs_18_financial_ratios": "IFRS 18 Financial Ratios",
	"ifrs_18_working_capital_analysis": "IFRS 18 Working Capital Analysis",
	"ifrs_18_cost_center_profitability": "IFRS 18 Cost Center Profitability",
	"ifrs_18_management_performance_measures": "IFRS 18 Management Performance Measures",
}

base = ROOT / "financial_reports/financial_reports/report"
for folder, report_name in reports.items():
	path = base / folder / f"{folder}.js"
	content = path.read_text(encoding="utf-8")
	call = f'\nfinancial_reports.add_comparison_filters("{report_name}");\n'
	if call not in content:
		path.write_text(content.rstrip() + call, encoding="utf-8")

print("Comparison controls registered")
