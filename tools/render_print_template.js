const fs = require("fs");
const vm = require("vm");

global.frappe = {
	utils: { get_random: () => "rnd" },
	templates: {},
	boot: { lang: "en", print_css: "" },
	urllib: { get_base_url: () => "http://test.local:8000" },
	datetime: { str_to_user: (value) => value },
};
global.__ = (value) => value;
global.format_currency = (value, currency) => `${currency || "USD"} ${Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

vm.runInThisContext(fs.readFileSync(
	"/home/frappe/frappe-bench/apps/frappe/frappe/public/js/frappe/microtemplate.js",
	"utf8",
));
const template = fs.readFileSync(
	"/home/frappe/frappe-bench/apps/financial_reports/financial_reports/templates/ifrs18_query_report.html",
	"utf8",
);
const default_context = {
	filters: {
		company: "Test",
		filter_based_on: "Date Range",
		period_start_date: "2026-03-07",
		period_end_date: "2026-04-05",
		comparison_enabled: 1,
		comparison_from_date: "2026-01-06",
		comparison_to_date: "2026-02-04",
		presentation_currency: "USD",
	},
	report: { report_name: "IFRS 18 Statement of Comprehensive Income" },
	columns: [
		{ fieldname: "account_name", label: "Line item", fieldtype: "Data" },
		{ fieldname: "current", label: "Current", fieldtype: "Currency" },
		{ fieldname: "comparative", label: "Comparative", fieldtype: "Currency" },
	],
	data: [
		{ account_name: "Revenue", current: 240, comparative: 120, currency: "USD" },
		{ account_name: "Cost of sales", current: -138.50, comparative: -70, currency: "USD" },
		{ account_name: "'Operating profit", current: 80, comparative: 40, currency: "USD", is_total: 1 },
	],
};
const input = fs.readFileSync(0, "utf8").trim();
const context = input ? JSON.parse(input) : default_context;
process.stdout.write(frappe.template.compile(template, "ifrs18_pdf_validation")(context));
