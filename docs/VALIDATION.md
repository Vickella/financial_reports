# Live validation record

The automated suite is restricted in code to `test.local` and uses two non-overlapping custom reporting ranges.

Verified behavior:

- default ERPNext Profit and Loss, Balance Sheet and Cash Flow Report records resolve to `Financial Reports`;
- arbitrary current and comparative date ranges are calculated independently;
- operating, investing, financing, income-tax and discontinued-operation arithmetic reconciles;
- OCI is excluded from profit and included in total comprehensive income;
- assets equal liabilities plus equity, including current-period earnings;
- changes in equity shows opening balance, period changes and closing balance for each range;
- MPM reconciliation includes account adjustments, income-tax effects and NCI fields;
- notes, working capital, ratios, cost-centre profitability and budget variance return comparative data;
- every report exposes a professional landscape print template containing the selected filters; and
- every report result generates a valid XLSX workbook.

The controlled dataset uses dedicated accounts for every IFRS 18 statement category and major balance-sheet/cash-flow classification. It posts 40 submitted Journal Entries: 20 for the comparative range and 20 for the current range.

Run the non-mutating verification again with:

```bash
bench --site test.local execute financial_reports.validation_existing.validate_posted_dataset
```

Do not invoke the mutating seed routine on a production site; it contains an explicit `test.local` guard.


## Audit-safe cleanup result

The initial 40 submitted test journals were cancelled through standard ERPNext hooks after synchronising VerityTax's `Foreign Payment Log` DocType. VerityGuard's linked `VG Exception Feed` records were preserved, so the cancelled journals were intentionally not physically deleted. Submitted tagged vouchers remaining: **0**.

The shared print format was also compiled and rendered with Frappe's browser microtemplate engine after correcting its print context from `report_columns` to Frappe's actual `columns` variable.


## PDF verification

`wkhtmltopdf 0.12.6` was installed on the Ubuntu bench host. The shared professional template was rendered with Frappe's client microtemplate compiler and passed through Frappe's server PDF pipeline as A4 landscape. Result: valid `%PDF` output, 21,755 bytes. The selected current and comparative periods and formatted values were asserted in the rendered HTML.


The final template prints every non-empty applied filter in the report header. Budget Variance was separately verified with current and comparative ranges: 2 rows, 10 columns, 5,160-byte XLSX output, and the shared print format loaded successfully.


The post-fix lifecycle then created, submitted, tested and cancelled another 40 tagged journals. Final status: **0 submitted** and **80 cancelled** validation journals. All four Frappe app tests passed.
