"""Controlled mapping upgrades for accounts still carrying fallback classifications."""

import frappe

from financial_reports.mapping import apply_mapping, infer_mapping


def remap_fallback_accounts():
	rows = frappe.get_all(
		"Account",
		filters={"custom_ifrs18_mapping_confidence": "Fallback", "custom_ifrs18_mapping_locked": 0},
		fields=["*"],
	)
	updated = []
	still_fallback = []
	for row in rows:
		candidate = infer_mapping(row)
		if candidate.confidence == "Fallback":
			still_fallback.append(row.name)
			continue
		apply_mapping(row, force=True, source="Automatic improved ERPNext chart rule")
		updated.append(row.name)
	return {"updated": len(updated), "still_fallback": still_fallback}
