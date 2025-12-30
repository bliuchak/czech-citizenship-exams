# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pymupdf>=1.23.0",
# ]
# ///
"""
PDF to JSON converter for Czech citizenship test questions.

Extracts questions, options, correct answers, and images from PDF files
and outputs structured JSON suitable for a quiz application.

Usage:
    uv run pdf_to_json.py <input.pdf> [output.json]
"""

import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF


@dataclass
class Option:
    label: str  # A, B, C, D
    text: str
    image: Optional[str] = None  # relative path to image file


@dataclass
class Question:
    id: int
    text: str
    options: list[Option] = field(default_factory=list)
    correct: str = ""  # A, B, C, or D
    image: Optional[str] = None  # image in question itself
    date: Optional[str] = None  # update date
    page: int = 0  # page number where question appears


@dataclass
class Section:
    id: int
    name: str
    questions: list[Question] = field(default_factory=list)


@dataclass
class QuizData:
    source_file: str
    sections: list[Section] = field(default_factory=list)


def extract_images_from_page(page: fitz.Page, output_dir: Path, page_num: int) -> list[dict]:
    """Extract all images from a page and return their info."""
    images = []
    image_list = page.get_images(full=True)

    for img_idx, img_info in enumerate(image_list, 1):
        xref = img_info[0]
        try:
            base_image = page.parent.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            # Get image position on page
            img_rects = page.get_image_rects(xref)
            rect = img_rects[0] if img_rects else None

            # Save image
            image_filename = f"page{page_num:02d}_img{img_idx:02d}.{image_ext}"
            image_path = output_dir / image_filename
            with open(image_path, "wb") as f:
                f.write(image_bytes)

            images.append({
                "filename": image_filename,
                "page": page_num,
                "rect": rect,
                "y_pos": rect.y0 if rect else 0,
            })
        except Exception as e:
            print(f"  Warning: Could not extract image {img_idx} on page {page_num}: {e}")

    return images


def cleanup_tiny_images(images_dir: Path, min_size: int = 200) -> int:
    """Delete images smaller than min_size bytes (artifacts)."""
    deleted = 0
    for img_path in images_dir.iterdir():
        if img_path.is_file() and img_path.stat().st_size < min_size:
            img_path.unlink()
            deleted += 1
    return deleted


def parse_answers_line(line: str) -> dict[int, str]:
    """Parse 'SPRÁVNÉ ŘEŠENÍ: 1C, 2C, 3D...' into {1: 'C', 2: 'C', 3: 'D', ...}"""
    answers = {}
    matches = re.findall(r'(\d+)([A-D])', line)
    for num, letter in matches:
        answers[int(num)] = letter
    return answers


def clean_text(text: str) -> str:
    """Clean up text by normalizing whitespace."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_pdf(pdf_path: Path, output_dir: Path) -> QuizData:
    """Parse PDF and extract all questions with images."""
    doc = fitz.open(pdf_path)

    # Create images directory
    images_dir = output_dir / f"{pdf_path.stem}_images"
    images_dir.mkdir(exist_ok=True)

    quiz_data = QuizData(source_file=pdf_path.name)

    # Track content per page for later image association
    page_content = {}  # {page_num: {'text': str, 'images': [...]}}
    all_images = []

    # First pass: extract text and images per page
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text()

        # Extract images with positions
        page_images = extract_images_from_page(page, images_dir, page_num + 1)
        all_images.extend(page_images)

        page_content[page_num + 1] = {
            'text': page_text,
            'images': page_images
        }

    doc.close()

    # Cleanup tiny artifact images (< 200 bytes)
    deleted = cleanup_tiny_images(images_dir)
    if deleted:
        print(f"  Deleted {deleted} artifact images")
        # Filter out deleted images from our tracking list
        all_images = [img for img in all_images
                      if (images_dir / img['filename']).exists()]

    # Build full text with page markers
    lines_with_pages = []  # [(line, page_num), ...]
    for page_num in sorted(page_content.keys()):
        page_text = page_content[page_num]['text']
        for line in page_text.split('\n'):
            lines_with_pages.append((line, page_num))

    # Parse the text
    current_section: Optional[Section] = None
    current_question: Optional[Question] = None
    current_answers: dict[int, str] = {}

    i = 0
    while i < len(lines_with_pages):
        line, page_num = lines_with_pages[i]
        line = line.strip()

        # Skip empty lines and page numbers
        if not line or re.match(r'^\d+$', line):
            i += 1
            continue

        # Skip header lines
        if line in ["TESTOVÉ ÚLOHY", "OBČANSKÝ ZÁKLAD"]:
            i += 1
            continue

        # Check for section header
        section_match = re.match(r'^(\d+)\.\s+([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ\s,0-9.]+)$', line)
        if section_match:
            section_text = section_match.group(2)
            is_section = all(c.isupper() or not c.isalpha() for c in section_text)
            if is_section:
                # Save current question before moving to new section
                if current_section and current_question and current_question.options:
                    current_section.questions.append(current_question)
                    current_question = None

                # Save previous section
                if current_section and current_section.questions:
                    for q in current_section.questions:
                        if q.id in current_answers:
                            q.correct = current_answers[q.id]
                    quiz_data.sections.append(current_section)

                section_id = int(section_match.group(1))
                section_name = section_match.group(2).strip()
                current_section = Section(id=section_id, name=section_name)
                current_question = None
                current_answers = {}
                i += 1
                continue

        # Check for answers line
        if "SPRÁVNÉ ŘEŠENÍ:" in line or "SPRÁVNÉ ŘEŠENÍ" in line:
            if current_section and current_question and current_question.options:
                current_section.questions.append(current_question)
                current_question = None

            answers_text = line
            current_answers = parse_answers_line(answers_text)
            i += 1
            continue

        # Check for question start
        question_match = re.match(r'^(\d+)\.\s*(.*)', line)
        if question_match:
            if current_section is None:
                current_section = Section(id=0, name="(Pokračování)")
            q_num = int(question_match.group(1))
            q_text = question_match.group(2) if question_match.group(2) else ""

            if not line.isupper() and (q_num <= 10 or '?' in line):
                if current_question and current_question.options:
                    current_section.questions.append(current_question)

                # Collect multi-line question text
                j = i + 1
                while j < len(lines_with_pages):
                    next_line = lines_with_pages[j][0].strip()
                    if (re.match(r'^[A-D]\)', next_line) or
                        next_line.startswith("Datum aktualizace") or
                        re.match(r'^\d+\.\s', next_line) or
                        "SPRÁVNÉ ŘEŠENÍ" in next_line or
                        not next_line):
                        break
                    q_text += " " + next_line if q_text else next_line
                    j += 1

                current_question = Question(id=q_num, text=clean_text(q_text), page=page_num)
                i = j
                continue

        # Check for option
        option_match = re.match(r'^([A-D])\)\s*(.*)', line)
        if option_match and current_question is not None:
            label = option_match.group(1)
            opt_text = option_match.group(2)

            j = i + 1
            while j < len(lines_with_pages):
                next_line = lines_with_pages[j][0].strip()
                if (re.match(r'^[A-D]\)', next_line) or
                    next_line.startswith("Datum aktualizace") or
                    re.match(r'^\d+\.\s+', next_line) or
                    "SPRÁVNÉ ŘEŠENÍ" in next_line or
                    not next_line):
                    break
                opt_text += " " + next_line
                j += 1

            current_question.options.append(Option(label=label, text=clean_text(opt_text)))
            i = j
            continue

        # Check for date line
        date_match = re.match(r'Datum aktualizace testové úlohy:\s*(.+)', line)
        if date_match and current_question is not None:
            current_question.date = date_match.group(1).strip()
            i += 1
            continue

        i += 1

    # Don't forget the last section
    if current_section and current_section.questions:
        if current_question and current_question.options:
            current_section.questions.append(current_question)
        for q in current_section.questions:
            if q.id in current_answers:
                q.correct = current_answers[q.id]
        quiz_data.sections.append(current_section)

    # Group images by page for efficient lookup
    images_by_page = {}
    for img in all_images:
        page = img['page']
        if page not in images_by_page:
            images_by_page[page] = []
        images_by_page[page].append(img)

    # Sort images on each page by Y position (top to bottom), then X (left to right)
    # This gives reading order for 2x2 grids: top-left, top-right, bottom-left, bottom-right
    for page in images_by_page:
        images_by_page[page].sort(key=lambda x: (
            round(x['y_pos'] / 100) * 100,  # Group by row (100px tolerance)
            x['rect'].x0 if x['rect'] else 0  # Then sort by X within row
        ))

    # Associate images with questions based on page
    assign_images_to_questions(quiz_data, images_by_page, images_dir.name)

    return quiz_data


def assign_images_to_questions(quiz_data: QuizData, images_by_page: dict, images_dir: str):
    """
    Assign images to questions using hybrid approach:

    1. For 4-image option questions: Pure page-based (4 short options + 4 images on SAME page)
    2. For single-image questions: Keyword-based (because multiple questions share pages)

    Keywords that indicate an image reference:
    - obrázku, obrázek (picture)
    - tato/této socha/sochy (this statue)
    - tato/této budova/budovy (this building)
    - tato/této panovnice (this ruler)
    - na obrázku (in the picture)
    """
    # Known false positives - questions that match keywords but shouldn't have images
    EXCLUDE_IMAGE = {
        (17, 8),  # "tato hora" refers to previously mentioned mountain, not an image
    }

    IMAGE_KEYWORDS = [
        "obrázku", "obrázek", "obrázků",  # picture (singular and plural)
        "na obrázku", "na mapě",  # on the picture/map
        "bankovce",  # on banknote (word order varies)
        "tato socha", "této sochy",  # this statue
        "tato panovnice",  # this ruler
        "tato budova", "této budovy", "tato stavba",  # this building
        "tato hora",  # this mountain
    ]

    for section in quiz_data.sections:
        for question in section.questions:
            # Skip known false positives
            if (section.id, question.id) in EXCLUDE_IMAGE:
                continue

            q_page = question.page
            q_lower = question.text.lower()
            mentions_image = any(kw in q_lower for kw in IMAGE_KEYWORDS)

            # Get images from the question's page
            page_images = images_by_page.get(q_page, [])

            # Only check next page if question explicitly references an image
            # (prevents false positives from adjacent pages with images)
            if not page_images and mentions_image:
                page_images = images_by_page.get(q_page + 1, [])

            if not page_images:
                continue

            # Check option structure
            short_options = all(len(opt.text) < 50 for opt in question.options)
            has_four_options = len(question.options) == 4
            has_four_plus_images = len(page_images) >= 4

            # Case 1: 4 short options + 4 images on SAME page + mentions image → assign to options
            if short_options and has_four_options and has_four_plus_images and mentions_image:
                for idx, opt in enumerate(question.options):
                    if idx < len(page_images):
                        opt.image = f"{images_dir}/{page_images[idx]['filename']}"

            # Case 2: Single image → only if keywords present
            elif len(page_images) >= 1 and mentions_image:
                question.image = f"{images_dir}/{page_images[0]['filename']}"


def convert_to_dict(quiz_data: QuizData) -> dict:
    """Convert QuizData to a JSON-serializable dictionary."""
    return {
        "source_file": quiz_data.source_file,
        "sections": [
            {
                "id": section.id,
                "name": section.name,
                "questions": [
                    {
                        "id": q.id,
                        "text": q.text,
                        "options": [
                            {
                                "label": opt.label,
                                "text": opt.text,
                                **({"image": opt.image} if opt.image else {})
                            }
                            for opt in q.options
                        ],
                        "correct": q.correct,
                        **({"image": q.image} if q.image else {}),
                        **({"date": q.date} if q.date else {})
                    }
                    for q in section.questions
                ]
            }
            for section in quiz_data.sections
        ]
    }


def process_pdf(pdf_path: Path, output_path: Optional[Path] = None) -> Path:
    """Process a single PDF file and save JSON output."""
    if output_path is None:
        output_path = pdf_path.with_suffix('.json')

    output_dir = pdf_path.parent

    print(f"Processing: {pdf_path.name}")
    quiz_data = parse_pdf(pdf_path, output_dir)

    # Convert to dict and save
    data = convert_to_dict(quiz_data)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Print summary
    total_questions = sum(len(s.questions) for s in quiz_data.sections)
    print(f"  Sections: {len(quiz_data.sections)}")
    print(f"  Questions: {total_questions}")
    print(f"  Output: {output_path.name}")

    return output_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    process_pdf(pdf_path, output_path)


if __name__ == "__main__":
    main()
