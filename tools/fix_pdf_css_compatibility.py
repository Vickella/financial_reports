from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
template = ROOT / "financial_reports" / "templates" / "ifrs18_query_report.html"
text = template.read_text(encoding="utf-8")
text = text.replace("break-inside: avoid; page-break-inside: avoid;", "page-break-inside: avoid;")
text = text.replace("\n\t\t.ifrs18-print .footer { position: running(report-footer); }", "")
template.write_text(text, encoding="utf-8")

for target in (ROOT / "financial_reports" / "financial_reports" / "report").glob("*/*.html"):
    target.write_text(text, encoding="utf-8")
