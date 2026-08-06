frappe.query_reports["IFRS 18 Mapping Audit"] = {
	filters: [
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company")},
		{fieldname: "exceptions_only", label: __("Exceptions only"), fieldtype: "Check", default: 1}
	]
};

