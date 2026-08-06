"""Remove remaining function-scope underscore assignments in report modules."""

from pathlib import Path


root = Path(__file__).resolve().parents[1]
changes = {
	"financial_reports/financial_reports/report/ifrs_18_notes_schedule/ifrs_18_notes_schedule.py": (
		"periods, _, account_rows = aggregate_accounts(filters)",
		"periods, aggregates, account_rows = aggregate_accounts(filters)",
	),
	"financial_reports/financial_reports/report/ifrs_18_management_performance_measures/ifrs_18_management_performance_measures.py": (
		"for row, _, factor in account_rows:",
		"for row, mapping, factor in account_rows:",
	),
}
for relative, (old, new) in changes.items():
	path = root / relative
	content = path.read_text(encoding="utf-8")
	if old not in content and new not in content:
		raise RuntimeError(f"Expected source not found in {relative}")
	path.write_text(content.replace(old, new), encoding="utf-8")
print("Remaining translation shadowing fixed")
