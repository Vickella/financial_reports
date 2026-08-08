function load_mpm_template(frm) {
	if (!frm.doc.company) {
		frappe.msgprint(__("Select the company before loading a common measure template."));
		return;
	}
	if (!frm.doc.measure_template || frm.doc.measure_template === "Custom") return;

	frappe.call({
		method: "financial_reports.financial_reports.doctype.ifrs_18_management_performance_measure.ifrs_18_management_performance_measure.get_mpm_preset",
		args: {company: frm.doc.company, measure_template: frm.doc.measure_template},
		freeze: true,
		freeze_message: __("Loading measure definition and account suggestions..."),
		callback(r) {
			const preset = r.message || {};
			if (frm.is_new() && !frm.doc.measure_name) frm.set_value("measure_name", frm.doc.measure_template);
			frm.set_value("comparable_subtotal", preset.comparable_subtotal);
			frm.set_value("reason_for_use", preset.reason_for_use);
			frm.set_value("calculation_description", preset.calculation_description);
			frm.clear_table("adjustments");
			(preset.adjustments || []).forEach((adjustment) => frm.add_child("adjustments", adjustment));
			frm.refresh_field("adjustments");
			frappe.show_alert({
				message: __("Loaded {0} suggested adjustment account(s). Review treatments, tax rates and NCI effects before saving.", [(preset.adjustments || []).length]),
				indicator: "blue",
			}, 8);
		}
	});
}

frappe.ui.form.on("IFRS 18 Management Performance Measure", {
	setup(frm) {
		frm.set_query("account", "adjustments", () => ({
			filters: {company: frm.doc.company, is_group: 0},
		}));
	},
	refresh(frm) {
		if (frm.doc.measure_template && frm.doc.measure_template !== "Custom") {
			frm.add_custom_button(__("Reload template and account suggestions"), () => load_mpm_template(frm));
		}
	},
	measure_template(frm) {
		if (frm.doc.measure_template === "Custom") return;
		if ((frm.doc.adjustments || []).length) {
			frappe.confirm(
				__("Replace the current reconciliation table with suggestions for {0}?", [frm.doc.measure_template]),
				() => load_mpm_template(frm)
			);
			return;
		}
		load_mpm_template(frm);
	},
});
