frappe.query_reports["Cash Flow"] = $.extend({}, erpnext.financial_statements, {name_field: "section", parent_field: "parent_section"});
erpnext.utils.add_dimensions("Cash Flow", 10);
frappe.query_reports["Cash Flow"].filters.splice(8, 1);
frappe.query_reports["Cash Flow"].filters.push(
	{fieldname: "include_default_book_entries", label: __("Include Default FB Entries"), fieldtype: "Check", default: 1},
	{fieldname: "show_opening_and_closing_balance", label: __("Show Opening and Closing Balance"), fieldtype: "Check", default: 1}
);
financial_reports.add_comparison_filters("Cash Flow");
