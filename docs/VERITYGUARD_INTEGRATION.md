# VerityGuard interoperability

`VG Exception Feed` is owned by VerityGuard. It is not a VerityTax DocType.

During controlled validation, Financial Reports created and submitted journals through normal ERPNext APIs. VerityTax validation and VerityGuard monitoring both remained enabled. After the VerityTax `Foreign Payment Log` schema was synchronised, all validation journals cancelled successfully.

Frappe correctly prevented physical deletion of the cancelled journals because VerityGuard exception-feed records dynamically link to them. The validation cleanup therefore retains cancelled vouchers and their linked exception records. Financial Reports reads submitted GL Entries only, so these cancelled vouchers have no financial-report impact.

This boundary is intentional:

- VerityGuard owns exception detection, monitoring and audit-feed retention.
- VerityTax owns tax classifications, tax rules and tax-register workflows.
- Financial Reports owns IFRS 18 presentation mappings and reporting.
- ERPNext's submitted General Ledger is the shared accounting source of truth.

No app hook is disabled, no dynamic link is ignored, and no ledger row is deleted directly.
