frappe.query_reports["IFRS 18 Budget Variance"] = {
	filters: [
		{fieldname:"company",label:__("Company"),fieldtype:"Link",options:"Company",default:frappe.defaults.get_user_default("Company"),reqd:1},
		{fieldname:"fiscal_year",label:__("Fiscal Year"),fieldtype:"Link",options:"Fiscal Year",default:erpnext.utils.get_fiscal_year(frappe.datetime.get_today()),reqd:1}
	]
};

