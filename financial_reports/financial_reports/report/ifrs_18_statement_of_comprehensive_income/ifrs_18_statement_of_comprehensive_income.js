frappe.query_reports["IFRS 18 Statement of Comprehensive Income"] = $.extend({}, erpnext.financial_statements);
erpnext.utils.add_dimensions("IFRS 18 Statement of Comprehensive Income", 10);
frappe.query_reports["IFRS 18 Statement of Comprehensive Income"].filters.push(
	{fieldname: "accumulated_values", label: __("Accumulated Values"), fieldtype: "Check", default: 0},
	{fieldname: "include_default_book_entries", label: __("Include Default FB Entries"), fieldtype: "Check", default: 1},
	{fieldname: "show_zero_values", label: __("Show zero values"), fieldtype: "Check"}
);
financial_reports.add_comparison_filters("IFRS 18 Statement of Comprehensive Income");
