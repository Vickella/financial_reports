"""Extract searchable UTF-8 text from the project reference PDFs."""

from pathlib import Path
import sys

from pypdf import PdfReader


def main() -> None:
	if len(sys.argv) != 3:
		raise SystemExit("usage: extract_pdf_text.py INPUT.pdf OUTPUT.txt")

	input_path = Path(sys.argv[1])
	output_path = Path(sys.argv[2])
	reader = PdfReader(input_path)
	pages = []
	for page_number, page in enumerate(reader.pages, start=1):
		pages.append(f"\n\n===== PAGE {page_number} =====\n\n{page.extract_text() or ''}")
	output_path.write_text("".join(pages), encoding="utf-8")
	print(f"{input_path.name}: {len(reader.pages)} pages -> {output_path}")


if __name__ == "__main__":
	main()
