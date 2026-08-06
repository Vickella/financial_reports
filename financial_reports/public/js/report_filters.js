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
