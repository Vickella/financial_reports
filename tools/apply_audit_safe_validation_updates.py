from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

validation = ROOT / "financial_reports" / "validation.py"
text = validation.read_text(encoding="utf-8")
old = '''def cleanup_transactions():
\tnames = frappe.get_all("Journal Entry", filters={"user_remark": ["like", f"{TAG}%"]}, pluck="name")
\tfor name in names:
\t\tdoc = frappe.get_doc("Journal Entry", name)
\t\tif doc.docstatus == 1:
\t\t\tdoc.cancel()
\t\tif doc.docstatus == 2:
\t\t\tdoc.delete(ignore_permissions=True)
\tfrappe.db.commit()
\treturn {"removed": names}
'''
new = '''def cleanup_transactions():
\t"""Cancel submitted test journals; retain cancelled vouchers and linked audit records."""
\tnames = frappe.get_all(
\t\t"Journal Entry",
\t\tfilters={"user_remark": ["like", f"{TAG}%"], "docstatus": 1},
\t\tpluck="name",
\t)
\tfor name in names:
\t\tfrappe.get_doc("Journal Entry", name).cancel()
\tfrappe.db.commit()
\treturn {"cancelled": names}
'''
if old not in text:
    raise SystemExit("Expected cleanup function not found")
validation.write_text(text.replace(old, new), encoding="utf-8")

existing = ROOT / "financial_reports" / "validation_existing.py"
text = existing.read_text(encoding="utf-8").replace(
    '"note": "Tagged vouchers retained because the installed VerityTax cancellation hook references an unsynchronized tax_payment column.",',
    '"note": "Tagged validation vouchers are retained as cancelled records so VerityTax and VerityGuard audit links remain intact.",',
)
existing.write_text(text, encoding="utf-8")

document = ROOT / "docs" / "VERITYTAX_INTEGRATION.md"
text = document.read_text(encoding="utf-8")
old_status = """## Validation data status

Forty submitted Journal Entries on `test.local` are tagged with a `user_remark` beginning `IFRS18-VALIDATION`. They are intentionally retained until the VerityTax schema mismatch is repaired, because normal cancellation must be allowed to complete atomically.

The test records are confined to the `Test` company and use dedicated `Validation ...` accounts. They must never be copied to a production site.
"""
new_status = """### 4. VerityGuard retains audit links to cancelled journals

After the VerityTax schema repair, all 40 validation journals cancelled successfully through normal hooks. Frappe then prevented physical deletion because `VG Exception Feed` records dynamically link to the journals. `VG Exception Feed` belongs to VerityGuard, not VerityTax.

Compliant resolution applied:

- retain the cancelled Journal Entries and VerityGuard exception records as an audit trail;
- do not ignore dynamic links or delete ledger records directly; and
- make the validation cleanup cancellation-only.

This is harmonious operation: Financial Reports reads only submitted GL Entries, so cancelled test vouchers have no reporting effect, while VerityGuard's audit evidence is preserved.

## Validation data status

Forty tagged validation Journal Entries on `test.local` were cancelled successfully and are retained with `docstatus = 2` because of their VerityGuard audit links. No tagged validation Journal Entry remains submitted.

The test records are confined to the `Test` company and use dedicated `Validation ...` accounts. They must never be copied to a production site.
"""
if old_status not in text:
    raise SystemExit("Expected validation status section not found")
text = text.replace(old_status, new_status)
text = text.replace(
    "On a site with both apps installed:",
    "On a site with Financial Reports, VerityTax and VerityGuard installed:",
).replace(
    "4. ERPNext's submitted GL remains the shared source of truth.",
    "4. VerityGuard owns exception monitoring and its audit-feed links.\n5. ERPNext's submitted GL remains the shared source of truth.",
)
document.write_text(text, encoding="utf-8")

record = ROOT / "docs" / "VALIDATION.md"
text = record.read_text(encoding="utf-8")
text += """
## Audit-safe cleanup result

The 40 submitted test journals were cancelled through standard ERPNext hooks after synchronising VerityTax's `Foreign Payment Log` DocType. VerityGuard's linked `VG Exception Feed` records were preserved, so the cancelled journals were intentionally not physically deleted. Submitted tagged vouchers remaining: **0**.

The shared print format was also compiled and rendered with Frappe's browser microtemplate engine after correcting its print context from `report_columns` to Frappe's actual `columns` variable.
"""
record.write_text(text, encoding="utf-8")
