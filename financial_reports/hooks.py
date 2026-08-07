app_name = "financial_reports"
app_title = "Financial Reports"
app_publisher = "VerityCore Consultancy (Pvt) Ltd"
app_description = "IFRS 18 compliant statutory and management financial reporting for ERPNext"
app_email = "devs@veritycore.co.zw"
app_license = "mit"

required_apps = ["erpnext"]

app_include_js = "/assets/financial_reports/js/report_filters.js"

after_install = "financial_reports.install.after_install"
after_migrate = ["financial_reports.install.after_migrate"]
before_uninstall = "financial_reports.install.before_uninstall"

doctype_js = {"Account": "public/js/account.js"}

doc_events = {
	"Account": {
		"validate": "financial_reports.mapping.validate_account_mapping",
		"after_insert": "financial_reports.mapping.map_new_account",
	}
}

