# IFRS 18 account-mapping lifecycle

## Installation and migration

When Financial Reports is installed, it creates the **IFRS 18 Mapping** section on `Account` and deterministically maps every existing ERPNext account. The mapping uses Account metadata (`root_type`, `account_type`) and account-name rules to populate:

- IFRS 18 category;
- statement line item;
- cash-flow activity;
- expense by nature, where relevant;
- note/disclosure group;
- mapping source and confidence.

Installation mappings are not overwritten on later migrations when they already exist. A mapping locked after manual review is never automatically remapped.

## New accounts

Every new posting Account is kept complete by a server-side validation hook. Missing mapping fields receive an immediate deterministic suggestion during the initial save, including expense classification. The Account is then marked **Mapping Review Required** with source `Automatic new-account suggestion`.

On the Account form, the user reviews the suggested category, statement line, cash-flow activity, expense nature and disclosure group. Selecting **IFRS 18 → Confirm IFRS 18 Mapping** locks the mapping and changes its state to:

- source: `Manual review`;
- confidence: `Manually reviewed`;
- review required: off; and
- lock manual mapping: on.

This avoids interrupting ERPNext account creation while preserving explicit user accountability. If required mapping fields are later cleared, the server restores a complete conservative suggestion instead of allowing an unmapped posting account.

## Monitoring

`IFRS 18 Mapping Audit` lists missing fields, fallback classifications and newly created accounts awaiting confirmation. Entity-specific fallback mappings must be reviewed before external reporting.

## Verified test

On `test.local`, a new expense account was created and automatically suggested as:

```text
Category:       Operating
Statement line: Administrative and other operating expenses
Cash flow:      Operating
Expense nature: Other operating expenses
```

After confirmation, a controlled 13-unit expense moved that exact report line by `-13`. The Journal Entry was cancelled through normal VerityTax and VerityGuard hooks. VerityGuard's linked `VG Financial Mapping` audit record was retained and the test Account was disabled.
