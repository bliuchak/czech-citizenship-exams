# Czech Citizenship Exams

Practice tool for the Czech citizenship exams (`Zkouška z českých reálií`). Extracts questions from the official PDF and provides an interactive quiz viewer.

## Features

- Downloads official test question bank from [cestina-pro-cizince.cz](https://cestina-pro-cizince.cz/obcanstvi/databanka-uloh/)
- Converts PDF to structured JSON with images
- Browser-based quiz with two modes:
  - **Full Coverage**: 10 rounds, each covering all 30 categories with 300 questions
  - **Random**: Random selection from each category
- Tracks score and shows pass/fail status (18/30 needed to pass)
- **Flag hard questions** (⚑) for later review, stored in browser
- **URL bookmarking**: Share specific questions via URL (e.g., `#17.8`)
- **Share flagged lists**: Send friends a link to practice your hard questions

## Quick Start

Requires [uv](https://docs.astral.sh/uv/) for running Python scripts.

```bash
# 1. Download the official PDF
uv run download_pdf.py

# 2. Convert PDF to JSON (extracts questions and images)
uv run pdf_to_json.py OBC_databanka_testovychuloh_251215.pdf

# 3. Open the quiz viewer in your browser
open test_viewer.html   # macOS
xdg-open test_viewer.html   # Linux
```

## Test Structure

The Czech citizenship test consists of:

- **30 questions** (1 from each of 30 categories)
- **30 minutes** to complete
- **18 correct answers** needed to pass (60%)
- Multiple choice with 4 options (A, B, C, D)

### Categories

1-16: Občanský základ (Civic Basics)

- Customs & traditions, transportation, healthcare, education, political system, etc.

17-21: Základní geografické informace (Geography)

- Location, regions, environment, etc.

22-30: Základní historické informace (History)

- Czech history from medieval times to present

## Files

| File | Description |
|------|-------------|
| `download_pdf.py` | Download official PDF from source |
| `pdf_to_json.py` | Convert PDF to JSON + extract images |
| `validate_images.py` | Validate image extraction and linking |
| `test_viewer.html` | Interactive quiz viewer |

## Validation

After converting the PDF, run the validation script to check for issues:

```bash
uv run validate_images.py
```

This checks:

- Images extracted from PDF vs. images referenced in JSON
- Orphaned images (expected: ~4 cover/decorative images)
- Missing images (errors if any)

## Data Source

Official test question bank from the Czech Ministry of Education:

- **Source**: <https://cestina-pro-cizince.cz/obcanstvi/databanka-uloh/>
- **Total questions**: 300 (30 categories × 10 questions each)

## License

This tool is for educational purposes. The test questions are published by the Czech government for public use.
