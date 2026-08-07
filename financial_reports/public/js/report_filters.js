window.financial_reports = window.financial_reports || {};

financial_reports.add_comparison_filters = function (report_name) {
	const report = frappe.query_reports[report_name];
	if (!report || report.filters.some((filter) => filter.fieldname === "comparison_enabled")) {
		return;
	}
	report.filters.push(
		{
			fieldname: "comparison_enabled",
			label: __("Compare custom period"),
			fieldtype: "Check",
			default: 0,
			on_change() {
				if (frappe.query_report.get_filter_value("comparison_enabled")) {
					frappe.query_report.set_filter_value("filter_based_on", "Date Range");
				}
			},
		},
		{
			fieldname: "comparison_from_date",
			label: __("Comparative From"),
			fieldtype: "Date",
			depends_on: "eval:doc.comparison_enabled",
			mandatory_depends_on: "eval:doc.comparison_enabled",
			default: frappe.datetime.add_years(frappe.datetime.year_start(), -1),
		},
		{
			fieldname: "comparison_to_date",
			label: __("Comparative To"),
			fieldtype: "Date",
			depends_on: "eval:doc.comparison_enabled",
			mandatory_depends_on: "eval:doc.comparison_enabled",
			default: frappe.datetime.add_years(frappe.datetime.year_end(), -1),
		}
	);
};

financial_reports.apply_accounting_formatter = function (report_name) {
	const report = frappe.query_reports[report_name];
	if (!report || report.__ifrs18_accounting_formatter) {
		return;
	}
	const original_formatter = report.formatter;
	report.formatter = function (value, row, column, data, default_formatter) {
		const formatter = original_formatter || default_formatter;
		const is_numeric = ["Currency", "Float", "Percent"].includes(column.fieldtype);
		const numeric_value = Number(value);
		const display_value = is_numeric && Number.isFinite(numeric_value) && numeric_value < 0
			? Math.abs(numeric_value)
			: value;
		let formatted = formatter(display_value, row, column, data, default_formatter);
		if (column.fieldtype === "Currency") {
			const currency = (data && data.currency) || frappe.defaults.get_default("currency") || "";
			const sample = currency ? format_currency(0, currency) : "";
			const unit = sample.replace(/[0-9.,\s\-()]/g, "");
			if (unit) formatted = formatted.split(unit).join("").trim();
		}
		return is_numeric && Number.isFinite(numeric_value) && numeric_value < 0
			? `(${formatted})`
			: formatted;
	};
	report.__ifrs18_accounting_formatter = true;
};
