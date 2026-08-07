# Validation record

Validation was completed on 7 August 2026 against ERPNext 15.111.0 / Frappe 15.111.1.

## Clean installation and independence

A dedicated `ifrs18-clean.test` site was created with only Frappe and ERPNext, then a standard ERPNext company and 82-account chart were created before installing this app. The installation result was:

- installed apps: `frappe`, `erpnext`, `financial_reports`;
- VerityTax and VerityGuard present: **no**;
- default accounts mapped: **82 of 82**;
- unmapped accounts: **0**; fallback mappings: **0**;
- standalone IFRS workspace: **absent**;
- Financial Reports cards in Accounting: **1**;
- the three standard ERPNext reports resolved to the `Financial Reports` module.

The app was uninstalled and reinstalled on this site. Uninstall restored the three report records to `Accounts`, removed the Accounting navigation section, and left **0** app-owned Account custom fields. Reinstallation reproduced the successful mapping and navigation result.

## Transaction and report validation

The controlled harness is code-restricted to `test.local`. It created 40 tagged Journal Entries across 21 purpose-built accounts: 20 in a comparative custom range and 20 in a current custom range. It covered assets, liabilities, equity, operating/investing/financing income and expenses, tax, discontinued operations and both OCI classes.

Results:

- 10 independent subtotal-delta assertions passed in the creation lifecycle;
- 54 line-item, subtotal, OCI and accounting-equation assertions passed in the independent reread;
- all 12 statutory, disclosure and management reports executed;
- every report produced an XLSX workbook and loaded the shared print format;
- arbitrary comparative ranges `2026-01-06`?`2026-02-04` and `2026-03-07`?`2026-04-05` were calculated independently;
- P&L, financial position, comprehensive income, cash flow and changes in equity include a Notes column;
- all submitted validation vouchers were cancelled through normal ERPNext hooks after testing. Cancelled records remain where VerityGuard retains audit links and have no GL reporting effect.

The final automated suite ran **12 tests** successfully.

## Print and export validation

The shared template was compiled by Frappe's microtemplate engine. Assertions confirmed:

- no `Fiscal period`, `Cost center`, `Applied filters`, preparation disclaimer or review disclaimer block;
- no repeated currency symbol before report-line amounts;
- one currency unit directly below each amount-column heading;
- negative/deduction values shown in accounting parentheses, never with a minus sign;
- reference-style white statement layout, restrained rules, bold section/subtotal rows and reference statement titles.

Frappe's server PDF pipeline produced a valid `%PDF` file (18,279 bytes in the final pipeline check). The host uses `wkhtmltopdf 0.12.6`. Browser assets were rebuilt and both UAT caches cleared.

## Currency, permissions and filters

- Existing USD/ZWG exchange fixtures were used to run the P&L in both currencies. Six non-zero statement lines converted at the expected **30:1** rate; values were not merely relabelled.
- Administrator read access passed and Guest read access was denied. All Financial Reports query reports are available to Accounts User and Accounts Manager; the three replaced statutory reports also retain ERPNext Auditor access. Guest access is denied.
- Standard ERPNext fiscal-year, project, cost-centre, finance-book and enabled accounting-dimension filters are passed to ERPNext's audited financial-statement engine.

## Repeat commands

```bash
python -m compileall financial_reports
node tools/validate_print_template.js
bench --site test.local run-tests --app financial_reports
bench --site test.local execute financial_reports.validation_print.validate_pdf_pipeline
bench --site test.local execute financial_reports.validation_operational.validate_currency_conversion
bench --site test.local execute financial_reports.validation_operational.validate_permissions
bench --site test.local execute financial_reports.validation_lifecycle.run_and_cancel
```

Do not invoke mutating validation helpers on production sites. They contain an explicit `test.local` guard.
