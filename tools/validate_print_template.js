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
global.format_currency = (value, currency) => `${currency || "USD"} ${Number(value).toFixed(2)}`;

const compiler = fs.readFileSync(
	"/home/frappe/frappe-bench/apps/frappe/frappe/public/js/frappe/microtemplate.js",
	"utf8",
);
vm.runInThisContext(compiler);

const template = fs.readFileSync(
	"/home/frappe/frappe-bench/apps/financial_reports/financial_reports/templates/ifrs18_query_report.html",
	"utf8",
);
const rendered = frappe.template.compile(template, "ifrs18_validation")({
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
		{ account_name: "'Operating profit", current: 105, comparative: 84, currency: "USD", is_total: 1 },
	],
});

for (const expected of ["Test", "2026-03-07", "2026-01-06", "Operating profit", "USD 105.00"]) {
	if (!rendered.includes(expected)) throw new Error(`Rendered HTML is missing: ${expected}`);
}
console.log(JSON.stringify({ compiled: true, rendered_bytes: Buffer.byteLength(rendered), assertions: 5 }));
