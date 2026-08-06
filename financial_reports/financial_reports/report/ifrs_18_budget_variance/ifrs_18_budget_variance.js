frappe.query_reports["IFRS 18 Budget Variance"] = {
	filters: [
		{fieldname:"company",label:__("Company"),fieldtype:"Link",options:"Company",default:frappe.defaults.get_user_default("Company"),reqd:1},
		{fieldname:"fiscal_year",label:__("Fiscal Year"),fieldtype:"Link",options:"Fiscal Year",default:erpnext.utils.get_fiscal_year(frappe.datetime.get_today()),reqd:1},
		{fieldname:"from_date",label:__("Current From"),fieldtype:"Date",default:frappe.datetime.year_start(),reqd:1},
		{fieldname:"to_date",label:__("Current To"),fieldtype:"Date",default:frappe.datetime.year_end(),reqd:1},
		{fieldname:"comparison_enabled",label:__("Compare custom period"),fieldtype:"Check",default:0},
		{fieldname:"comparison_from_date",label:__("Comparative From"),fieldtype:"Date",depends_on:"eval:doc.comparison_enabled",mandatory_depends_on:"eval:doc.comparison_enabled",default:frappe.datetime.add_years(frappe.datetime.year_start(),-1)},
		{fieldname:"comparison_to_date",label:__("Comparative To"),fieldtype:"Date",depends_on:"eval:doc.comparison_enabled",mandatory_depends_on:"eval:doc.comparison_enabled",default:frappe.datetime.add_years(frappe.datetime.year_end(),-1)}
	]
};
