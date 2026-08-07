"""Read-only inventory of accounts using conservative fallback mappings."""

import frappe


def get_fallback_accounts():
	return frappe.get_all(
		"Account",
		filters={"custom_ifrs18_mapping_confidence": "Fallback"},
		fields=[
			"name", "account_name", "company", "root_type", "account_type", "is_group",
			"custom_ifrs18_category", "custom_ifrs18_line_item",
		],
		order_by="company, root_type, account_name",
	)
