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
		{ account_name: "Revenue", current: 282150, comparative: 159088, currency: "USD" },
		{ account_name: "Cost of sales", current: -138441.60, comparative: -127946, currency: "USD" },
		{ account_name: "'Operating profit", current: 105, comparative: 84, currency: "USD", is_total: 1 },
	],
});

for (const expected of ["Test", "Operating profit", "(138,441.60)", "282,150.00", ">USD<"]) {
	if (!rendered.includes(expected)) throw new Error(`Rendered HTML is missing: ${expected}`);
}
for (const prohibited of ["Fiscal period", "Cost center", "Applied filters", "Prepared from ERPNext", "Review materiality", "-138,441.60"]) {
	if (rendered.includes(prohibited)) throw new Error(`Rendered HTML contains prohibited text: ${prohibited}`);
}
const unitCount = (rendered.match(/>USD</g) || []).length;
if (unitCount !== 2) throw new Error(`Expected one currency unit per amount column, got ${unitCount}`);
console.log(JSON.stringify({ compiled: true, rendered_bytes: Buffer.byteLength(rendered), assertions: 12, accounting_parentheses: true, repeated_currency_symbols: false }));
