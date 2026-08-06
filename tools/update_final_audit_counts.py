from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

tax = ROOT / "docs" / "VERITYTAX_INTEGRATION.md"
text = tax.read_text(encoding="utf-8")
text = text.replace(
    "Forty tagged validation Journal Entries on `test.local` were cancelled successfully and are retained with `docstatus = 2` because of their VerityGuard audit links. No tagged validation Journal Entry remains submitted.",
    "Eighty tagged validation Journal Entries on `test.local` are retained with `docstatus = 2`: 40 from the initial validation and 40 from the post-fix lifecycle rerun. No tagged validation Journal Entry remains submitted. The cancelled records remain because of their VerityGuard audit links.",
)
tax.write_text(text, encoding="utf-8")

record = ROOT / "docs" / "VALIDATION.md"
text = record.read_text(encoding="utf-8")
text = text.replace(
    "The 40 submitted test journals were cancelled through standard ERPNext hooks after synchronising VerityTax's `Foreign Payment Log` DocType.",
    "The initial 40 submitted test journals were cancelled through standard ERPNext hooks after synchronising VerityTax's `Foreign Payment Log` DocType.",
)
text += """

The post-fix lifecycle then created, submitted, tested and cancelled another 40 tagged journals. Final status: **0 submitted** and **80 cancelled** validation journals. All four Frappe app tests passed.
"""
record.write_text(text, encoding="utf-8")
