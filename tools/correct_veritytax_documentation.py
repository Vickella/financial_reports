from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

status = ROOT / "financial_reports" / "validation_status.py"
text = status.read_text(encoding="utf-8")
text = text.replace("Foreign Payment Compliance Log", "Foreign Payment Log")
status.write_text(text, encoding="utf-8")

document = ROOT / "docs" / "VERITYTAX_INTEGRATION.md"
text = document.read_text(encoding="utf-8")
text = text.replace(
    "### 3. VerityTax cancellation hook references an unsynchronised column",
    "### 3. VerityTax cancellation hook encountered a stale site schema",
)
text = text.replace(
    "When cancelling a submitted validation Journal Entry, the VerityTax cancellation hook queries a `tax_payment` column that is absent from the current site table. The resulting database error is:",
    "When cancelling a submitted validation Journal Entry, the VerityTax cancellation hook queried a `tax_payment` column that was absent from the site's `Foreign Payment Log` table. The installed VerityTax DocType JSON already defines that field, so this was a stale site schema rather than a missing source definition. The resulting database error was:",
)
old = """This indicates that the installed VerityTax code and its database DocType schema are out of sync, most likely because the earlier VerityTax data patch prevents migration from reaching schema synchronisation.

Compliant user resolution:

1. Satisfy and approve the statutory interest rule described above.
2. Back up `test.local`.
3. Run the normal site migration to completion.
4. Confirm the VerityTax Foreign Payment Compliance Log schema includes its `tax_payment` link field.
5. Cancel the tagged `IFRS18-VALIDATION%` Journal Entries through normal ERPNext cancellation.
"""
new = """The schema was synchronised using Frappe's supported targeted command:

```bash
bench --site test.local reload-doc veritytax doctype foreign_payment_log
```

This reloads the installed VerityTax DocType definition. It does not disable hooks, alter tax rules, or fabricate statutory data.

Compliant user resolution:

1. Back up the affected site.
2. Reload the installed `Foreign Payment Log` DocType definition as shown above.
3. Confirm the table includes its `tax_payment` link field.
4. Cancel the tagged `IFRS18-VALIDATION%` Journal Entries through normal ERPNext cancellation.
5. Separately satisfy the approved statutory-interest-rule prerequisite and complete normal migration.
"""
if old not in text:
    raise SystemExit("Expected VerityTax documentation block was not found")
document.write_text(text.replace(old, new), encoding="utf-8")
