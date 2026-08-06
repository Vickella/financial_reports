from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

readme = ROOT / "README.md"
text = readme.read_text(encoding="utf-8")
needle = "bench build --app financial_reports\n```"
replacement = "bench build --app financial_reports\n```\n\nPrintable PDF export requires `wkhtmltopdf` on the bench host. On Ubuntu: `sudo apt-get install wkhtmltopdf`."
if needle not in text:
    raise SystemExit("README installation block not found")
readme.write_text(text.replace(needle, replacement), encoding="utf-8")

record = ROOT / "docs" / "VALIDATION.md"
text = record.read_text(encoding="utf-8")
text += """

## PDF verification

`wkhtmltopdf 0.12.6` was installed on the Ubuntu bench host. The shared professional template was rendered with Frappe's client microtemplate compiler and passed through Frappe's server PDF pipeline as A4 landscape. Result: valid `%PDF` output, 20,663 bytes. The selected current and comparative periods and formatted values were asserted in the rendered HTML.
"""
record.write_text(text, encoding="utf-8")

tax = ROOT / "docs" / "VERITYTAX_INTEGRATION.md"
text = tax.read_text(encoding="utf-8")
needle = "Do not insert a fabricated rate merely to make migration pass. The rule affects tax calculations and requires an authorised tax user."
replacement = needle + "\n\nSite audit result: `Test-2026-USD` exists in Draft with a 10% late-payment interest rate and no Legal Reference. There are no Approved Zimbabwe Tax Rule records. VerityTax's controller requires a Legal Reference before approval. An authorised tax user must verify the rate against the authoritative instrument, enter that reference, and approve the existing draft; Financial Reports must not perform that legal judgement."
if needle not in text:
    raise SystemExit("VerityTax warning not found")
tax.write_text(text.replace(needle, replacement), encoding="utf-8")
