# Financial Reports for ERPNext

An ERPNext v15 app that makes the standard **Profit and Loss Statement**, **Balance Sheet**, and **Cash Flow** links execute IFRS 18 structured reports, while adding the other primary statements, disclosure schedules, mapping controls, management-defined performance measures (MPMs), and management analytics.

## What is included

- Account-level **IFRS 18 Mapping** section with automatic installation mapping, review confidence and manual lock.
- Profit or loss grouped into operating, investing, financing, income tax and discontinued-operation categories.
- Mandatory subtotals: operating profit and profit before financing and income taxes.
- Statement of comprehensive income, with OCI split between items that may and will not be reclassified.
- Current/non-current statement of financial position, changes in equity and indirect cash flow.
- Systematic notes schedule and mapping-completeness audit.
- Configurable IFRS 18 MPM definitions and reconciliation including tax and NCI effects.
- Financial ratios, working-capital analysis, budget variance and cost-centre profitability.
- A dedicated **IFRS 18 Financial Reporting** workspace.

The implementation structure is based on every PDF supplied with this repository, especially the 172-page illustrative financial statements in `reports structure required.pdf`. The supplied IFRS 18 standard and workshop materials informed the categories, subtotals, aggregation/disaggregation, specified-expense and MPM controls; IAS 1 and the financial-statements primer informed comparative statement and general presentation behaviour.

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/Vickella/financial_reports.git
bench --site your-site install-app financial_reports
bench --site your-site migrate
bench build --app financial_reports
```

Printable PDF export requires `wkhtmltopdf` on the bench host. On Ubuntu: `sudo apt-get install wkhtmltopdf`.

Installation is intentionally non-destructive: it redirects the three standard Report records to the Financial Reports module, so existing ERPNext workspace links remain valid. Uninstall restores their module to `Accounts`. ERPNext source files are never patched.

## First-use control procedure

1. Open **IFRS 18 Reporting Settings** and record the entity's expense presentation and any specified main business activity.
2. Run **IFRS 18 Mapping Audit** with *Exceptions only* enabled.
3. Review fallback mappings in each Account, correct entity-specific judgements, and enable **Lock Manual Mapping**.
4. Define any publicly communicated MPMs and their reconciliations.
5. Reconcile the IFRS 18 statements to Trial Balance and obtain preparer/reviewer approval before external issue.

Automatic mappings are a controlled starting point, not a substitute for entity-specific IFRS judgements, materiality assessment, consolidation entries, tax review or audit.

## Development checks

```bash
python -m compileall financial_reports
bench --site your-site migrate
bench --site your-site run-tests --app financial_reports
```
