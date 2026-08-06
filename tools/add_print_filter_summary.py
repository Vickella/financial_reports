from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
template = ROOT / "financial_reports" / "templates" / "ifrs18_query_report.html"
text = template.read_text(encoding="utf-8")
text = text.replace(
    '.ifrs18-print .period { color: #4d5d73; font-size: 8.5pt; }',
    '.ifrs18-print .period { color: #4d5d73; font-size: 8.5pt; }\n'
    '\t.ifrs18-print .filter-summary { color: #5a687b; font-size: 7.5pt; margin-top: 6px; }\n'
    '\t.ifrs18-print .filter-summary span { border-right: 1px solid #c9d2de; display: inline-block; margin: 2px 8px 2px 0; padding-right: 8px; }',
)
needle = '''\t\t\t{% if (filters.finance_book) { %}<br><strong>{%= __("Finance book") %}:</strong> {%= filters.finance_book %}{% } %}
\t\t</div>
'''
replacement = '''\t\t\t{% if (filters.finance_book) { %}<br><strong>{%= __("Finance book") %}:</strong> {%= filters.finance_book %}{% } %}
\t\t</div>
\t\t{% var applied_filter_keys = Object.keys(filters).filter(function(key) { var value = filters[key]; return value !== undefined && value !== null && value !== "" && value !== false; }); %}
\t\t{% if (applied_filter_keys.length) { %}
\t\t\t<div class="filter-summary"><strong>{%= __("Applied filters") %}:</strong>
\t\t\t\t{% for (var filter_index = 0; filter_index < applied_filter_keys.length; filter_index++) { var filter_key = applied_filter_keys[filter_index]; var filter_value = filters[filter_key]; %}
\t\t\t\t\t<span>{%= __(filter_key.replace(/_/g, " ").replace(/\\b\\w/g, function(letter) { return letter.toUpperCase(); })) %}: {%= Array.isArray(filter_value) ? filter_value.join(", ") : String(filter_value) %}</span>
\t\t\t\t{% } %}
\t\t\t</div>
\t\t{% } %}
'''
if needle not in text:
    raise SystemExit("Print header insertion point not found")
template.write_text(text.replace(needle, replacement), encoding="utf-8")

for target in (ROOT / "financial_reports" / "financial_reports" / "report").glob("*/*.html"):
    target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
