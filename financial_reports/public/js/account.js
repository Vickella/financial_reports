frappe.ui.form.on("Account", {
	refresh(frm) {
		if (frm.doc.custom_ifrs18_mapping_review_required) {
			frm.dashboard.set_headline_alert(
				__("Review the suggested IFRS 18 category, statement line, cash-flow activity and expense nature, then confirm the mapping."),
				"orange"
			);
			if (!frm.is_new()) {
				frm.add_custom_button(__("Confirm IFRS 18 Mapping"), async () => {
					await frm.set_value("custom_ifrs18_mapping_locked", 1);
					await frm.save();
				}, __("IFRS 18"));
			}
		} else if (!frm.doc.custom_ifrs18_mapping_locked && frm.doc.custom_ifrs18_category) {
			frm.dashboard.set_headline_alert(
				__("This IFRS 18 mapping was generated automatically during installation. Review and lock it when entity-specific approval is complete."),
				"blue"
			);
		}
	},
	custom_ifrs18_mapping_locked(frm) {
		if (frm.doc.custom_ifrs18_mapping_locked) {
			frm.set_value("custom_ifrs18_mapping_review_required", 0);
			frm.set_value("custom_ifrs18_mapping_confidence", "Manually reviewed");
			frm.set_value("custom_ifrs18_mapping_source", "Manual review");
		}
	},
});
