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

financial_reports.apply_accounting_formatter = function (report_name) {
	const report = frappe.query_reports[report_name];
	if (!report || report.__ifrs18_accounting_formatter) {
		return;
	}
	const original_formatter = report.formatter;
	report.formatter = function (value, row, column, data, default_formatter) {
		const formatter = original_formatter || default_formatter;
		const is_numeric = ["Currency", "Float", "Percent"].includes(column.fieldtype);
		const numeric_value = Number(value);
		const display_value = is_numeric && Number.isFinite(numeric_value) && numeric_value < 0
			? Math.abs(numeric_value)
			: value;
		let formatted = formatter(display_value, row, column, data, default_formatter);
		if (column.fieldtype === "Currency") {
			const currency = (data && data.currency) || frappe.defaults.get_default("currency") || "";
			const sample = currency ? format_currency(0, currency) : "";
			const unit = sample.replace(/[0-9.,\s\-()]/g, "");
			if (unit) formatted = formatted.split(unit).join("").trim();
		}
		return is_numeric && Number.isFinite(numeric_value) && numeric_value < 0
			? `(${formatted})`
			: formatted;
	};
	report.__ifrs18_accounting_formatter = true;
};


financial_reports.pdf_report_names = new Set([
	"Profit and Loss Statement",
	"Balance Sheet",
	"Cash Flow",
	"IFRS 18 Statement of Comprehensive Income",
	"IFRS 18 Statement of Changes in Equity",
	"IFRS 18 Notes Schedule",
	"IFRS 18 Financial Ratios",
	"IFRS 18 Working Capital Analysis",
	"IFRS 18 Budget Variance",
	"IFRS 18 Cost Center Profitability",
	"IFRS 18 Management Performance Measures",
	"IFRS 18 Mapping Audit",
]);

financial_reports.install_strict_report_print_format = function () {
	const QueryReport = frappe.views && frappe.views.QueryReport;
	if (!QueryReport || QueryReport.prototype.__financial_reports_print_format) return;
	const standard_get_custom_format = QueryReport.prototype.get_custom_format;
	QueryReport.prototype.get_custom_format = async function (print_settings) {
		let custom_format = await standard_get_custom_format.call(this, print_settings);
		if (!financial_reports.pdf_report_names.has(this.report_name)) return custom_format;

		let enforced_format = this.report_settings && this.report_settings.html_format;
		if (!enforced_format) {
			const settings = await frappe.xcall("frappe.desk.query_report.get_script", {
				report_name: this.report_name,
			});
			enforced_format = settings && settings.html_format;
			if (enforced_format && this.report_settings) {
				this.report_settings.html_format = enforced_format;
			}
		}
		if (enforced_format) {
			print_settings.columns = [];
			print_settings.orientation = "Landscape";
			return enforced_format;
		}
		return custom_format;
	};
	QueryReport.prototype.__financial_reports_print_format = true;
};

financial_reports.install_pdf_download = function () {
	if (!frappe.render_pdf || frappe.render_pdf.__financial_reports_download) return;
	const standard_render_pdf = frappe.render_pdf;
	const download_pdf = function (html, opts = {}) {
		const route = frappe.get_route();
		const report_name = route[0] === "query-report" ? route[1] : "";
		if (!financial_reports.pdf_report_names.has(report_name)) {
			return standard_render_pdf(html, opts);
		}
		const form_data = new FormData();
		form_data.append("html", html);
		form_data.append("orientation", "Landscape");
		form_data.append("blob", new Blob([], { type: "text/xml" }));
		frappe.dom.freeze(__("Preparing PDF..."));
		fetch("/api/method/frappe.utils.print_format.report_to_pdf", {
			method: "POST",
			headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
			credentials: "same-origin",
			body: form_data,
		})
			.then((response) => {
				if (!response.ok) throw new Error(__("PDF generation failed with status {0}", [response.status]));
				return response.blob();
			})
			.then((pdf_blob) => {
				if (!pdf_blob.size) throw new Error(__("The generated PDF was empty."));
				const object_url = URL.createObjectURL(new Blob([pdf_blob], { type: "application/pdf" }));
				const link = document.createElement("a");
				const requested_name = opts.report_name || `${report_name}.pdf`;
				link.download = requested_name.replace(/[<>:"/\\|?*\u0000-\u001F]/g, "-").slice(0, 180);
				link.href = object_url;
				link.style.display = "none";
				document.body.appendChild(link);
				link.click();
				setTimeout(() => { link.remove(); URL.revokeObjectURL(object_url); }, 60000);
			})
			.catch((error) => frappe.msgprint({ title: __("PDF Download Failed"), message: error.message, indicator: "red" }))
			.finally(() => frappe.dom.unfreeze());
	};
	download_pdf.__financial_reports_download = true;
	frappe.render_pdf = download_pdf;
};

frappe.ready(() => {
	financial_reports.install_strict_report_print_format();
	financial_reports.install_pdf_download();
});
