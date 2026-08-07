# VerityTax integration and independence

## Independence boundary

`financial_reports` depends only on ERPNext. Its production reporting code:

- reads standard `Account`, `GL Entry`, `Company`, `Fiscal Year`, `Budget`, `Cost Center` and Report data;
- does not import VerityTax modules;
- does not suppress, override or bypass VerityTax validation or cancellation hooks;
- remains installable and functional on sites where VerityTax is not installed; and
- treats tax-account classifications as IFRS 18 presentation mappings, not tax-return determinations.

The controlled test harness checks whether the optional `Journal Entry Account.tax_nature` field exists. When present, it supplies the valid `Operating Expense` classification on synthetic expense lines. This is conditional compatibility code used only by an explicitly invoked test; it is not a runtime dependency.

## Interferences observed on `test.local`

### 1. VerityTax migration prerequisite on the UAT site

VerityTax's migration patch required an approved, effective-dated statutory interest rule for `Test-2026` / `USD`. At the user's explicit instruction, the UAT-only rule `Test-2026-USD` was completed and approved with the reference:

```text
TEST-LOCAL-UAT-ONLY / USER-AUTHORIZED-2026-08-06 / NOT-A-LEGAL-AUTHORITY
```

The 10% Simple Daily value is test data, is not an authoritative legal reference, and must never be copied to production or used for a real tax calculation. A production tax administrator must replace it with the legally applicable rate, effective dates and primary legal instrument after authorised review. With that UAT prerequisite present, the normal site migration completed successfully. Financial Reports contains no production dependency on this rule.

### 2. Expense Journal Entry lines require Tax Nature

VerityTax validates every expense line in a Journal Entry and rejects it if `tax_nature` is blank. The controlled validation initially failed on the synthetic cost-of-sales account.

Compliant resolution applied by the test harness:

- detect whether the optional custom field exists;
- populate `Operating Expense` on synthetic expense lines; and
- allow all normal VerityTax validation and tax-register hooks to run.

Financial Reports does not add this requirement and does not require the field when VerityTax is absent.

### 3. VerityTax cancellation hook encountered a stale site schema

When cancelling a submitted validation Journal Entry, the VerityTax cancellation hook queried a `tax_payment` column that was absent from the site's `Foreign Payment Log` table. The installed VerityTax DocType JSON already defines that field, so this was a stale site schema rather than a missing source definition. The resulting database error was:

```text
Unknown column 'tax_payment' in 'SELECT'
```

The schema was synchronised using Frappe's supported targeted command:

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

Do not delete GL Entries directly, ignore links, or disable VerityTax hooks. Those approaches would compromise both accounting and tax audit trails.

### 4. VerityGuard retains audit links to cancelled journals

After the VerityTax schema repair, all 40 validation journals cancelled successfully through normal hooks. Frappe then prevented physical deletion because `VG Exception Feed` records dynamically link to the journals. `VG Exception Feed` belongs to VerityGuard, not VerityTax.

Compliant resolution applied:

- retain the cancelled Journal Entries and VerityGuard exception records as an audit trail;
- do not ignore dynamic links or delete ledger records directly; and
- make the validation cleanup cancellation-only.

This is harmonious operation: Financial Reports reads only submitted GL Entries, so cancelled test vouchers have no reporting effect, while VerityGuard's audit evidence is preserved.

## Validation data status

Eighty tagged validation Journal Entries on `test.local` are retained with `docstatus = 2`: 40 from the initial validation and 40 from the post-fix lifecycle rerun. No tagged validation Journal Entry remains submitted. The cancelled records remain because of their VerityGuard audit links.

The test records are confined to the `Test` company and use dedicated `Validation ...` accounts. They must never be copied to a production site.

## Supported operating model

On a site with Financial Reports, VerityTax and VerityGuard installed:

1. VerityTax owns tax nature, deductibility, tax rules and tax-register workflows.
2. Financial Reports owns IFRS 18 presentation category, statement line, cash-flow activity, disclosure grouping and financial analytics.
3. The same Account may carry both sets of metadata. Neither app overwrites the other's fields.
4. VerityGuard owns exception monitoring and its audit-feed links.
5. ERPNext's submitted GL remains the shared source of truth.

