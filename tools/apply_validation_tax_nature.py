"""Make controlled validation vouchers comply with installed VerityTax hooks."""

from pathlib import Path


path = Path(__file__).resolve().parents[1] / "financial_reports/validation.py"
content = path.read_text(encoding="utf-8")
old = '''\t\tif root_type in ("Income", "Expense") and default_cost_center:
\t\t\ttarget_row["cost_center"] = default_cost_center
'''
new = '''\t\tif root_type in ("Income", "Expense") and default_cost_center:
\t\t\ttarget_row["cost_center"] = default_cost_center
\t\tif root_type == "Expense" and frappe.db.has_column("Journal Entry Account", "tax_nature"):
\t\t\ttarget_row["tax_nature"] = "Operating Expense"
'''
if old not in content and new not in content:
	raise RuntimeError("Expected validation Journal Entry block not found")
path.write_text(content.replace(old, new), encoding="utf-8")
print("Validation tax nature applied")
