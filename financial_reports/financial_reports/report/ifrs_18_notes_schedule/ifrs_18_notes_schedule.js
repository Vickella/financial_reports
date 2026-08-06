frappe.query_reports["IFRS 18 Notes Schedule"] = $.extend({}, erpnext.financial_statements);
erpnext.utils.add_dimensions("IFRS 18 Notes Schedule", 10);
frappe.query_reports["IFRS 18 Notes Schedule"].filters.push(
	{fieldname: "accumulated_values", label: __("Accumulated Values"), fieldtype: "Check", default: 0},
	{fieldname: "include_default_book_entries", label: __("Include Default FB Entries"), fieldtype: "Check", default: 1},
	{fieldname: "show_zero_values", label: __("Show zero values"), fieldtype: "Check"}
);
