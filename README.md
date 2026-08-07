# Financial Reports for ERPNext

An ERPNext v15 app that replaces the standard **Profit and Loss Statement**, **Balance Sheet**, and **Cash Flow** report implementations with IFRS 18 structured reports. It also provides the other primary statements, disclosure schedules, management-defined performance measures (MPMs), mapping controls, and management analytics.

## Included reports and controls

- Statement of profit or loss with operating, investing, financing, income-tax and discontinued-operation categories and the IFRS 18 required subtotals.
- Statement of financial position, statement of comprehensive income, statement of changes in equity, and indirect statement of cash flows.
- Notes schedule, mapping audit, financial ratios, working-capital analysis, budget variance, cost-centre profitability and MPM reconciliation.
- Independent current and comparative custom date ranges, fiscal-year periods, ERPNext accounting-dimension filters, presentation-currency conversion, XLSX export, printing and PDF generation.
- Account-level **IFRS 18 Mapping** and collapsible **Mapping Review** sections. Existing ERPNext accounts are mapped automatically at installation. New accounts receive a rule-based suggestion and must be confirmed and locked by the user.
- Reference-style statement presentation: Notes column, currency unit beneath each amount-column heading, accounting parentheses for deductions, and no repeated currency symbols on report lines.

The report structure is based on every PDF supplied with this repository, especially the illustrative statements in `reports structure required.pdf`. The supplied IFRS 18, IAS 1 and IASB/EFRAG materials informed classification, subtotals, aggregation/disaggregation, specified-expense and MPM controls.

## Navigation and default report replacement

The app does **not** create a standalone workspace. Installation adds a **Financial Reports** card inside ERPNext's existing **Accounting** workspace. The standard Profit and Loss Statement, Balance Sheet and Cash Flow Report records are redirected to this app, so their normal ERPNext links open the IFRS 18 versions. Uninstall restores those records to the `Accounts` module, removes the Accounting card and removes only the Account custom fields owned by this app. ERPNext source files are never patched.

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/Vickella/financial_reports.git
bench --site your-site install-app financial_reports
bench --site your-site migrate
bench build --app financial_reports
bench --site your-site clear-cache
```

PDF export requires `wkhtmltopdf` on the bench host. On Ubuntu/WSL:

```bash
sudo apt-get update
sudo apt-get install -y wkhtmltopdf
wkhtmltopdf --version
```

## First-use control procedure

1. Open **IFRS 18 Reporting Settings** and record the entity's expense presentation and specified main business activities.
2. Run **IFRS 18 Mapping Audit** and resolve every exception.
3. Review new-account suggestions and entity-specific judgements, then use **Confirm and Lock Mapping**.
4. Complete note references and define any publicly communicated MPM reconciliations.
5. Reconcile the statements to Trial Balance and obtain preparer/reviewer approval before external issue.

Automatic mappings are a controlled starting point. Entity management remains responsible for materiality, accounting-policy choices, consolidation/elimination entries, disclosures, tax review and external-report approval.

## Development checks

```bash
python -m compileall financial_reports
node tools/validate_print_template.js
bench --site your-site migrate
bench --site your-site run-tests --app financial_reports
```

See [docs/VALIDATION.md](docs/VALIDATION.md), [docs/ACCOUNT_MAPPING_WORKFLOW.md](docs/ACCOUNT_MAPPING_WORKFLOW.md), [docs/VERITYTAX_INTEGRATION.md](docs/VERITYTAX_INTEGRATION.md), and [docs/VERITYGUARD_INTEGRATION.md](docs/VERITYGUARD_INTEGRATION.md).
