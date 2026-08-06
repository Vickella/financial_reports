frappe.ui.form.on("Account", {
	refresh(frm) {
		if (!frm.doc.custom_ifrs18_mapping_locked && frm.doc.custom_ifrs18_category) {
			frm.dashboard.set_headline_alert(
				__("This IFRS 18 mapping was generated automatically. Review it and enable <b>Lock Manual Mapping</b> after approval."),
				"blue"
			);
		}
	},
	custom_ifrs18_mapping_locked(frm) {
		if (frm.doc.custom_ifrs18_mapping_locked) {
			frm.set_value("custom_ifrs18_mapping_confidence", "Manually reviewed");
			frm.set_value("custom_ifrs18_mapping_source", "Manual review");
		}
	},
});
