from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
record = ROOT / "docs" / "VALIDATION.md"
text = record.read_text(encoding="utf-8").replace("20,663 bytes", "21,755 bytes")
text += """

The final template prints every non-empty applied filter in the report header. Budget Variance was separately verified with current and comparative ranges: 2 rows, 10 columns, 5,160-byte XLSX output, and the shared print format loaded successfully.
"""
record.write_text(text, encoding="utf-8")
