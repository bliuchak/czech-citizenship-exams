# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Validate image extraction and linking.

Compares:
1. Images extracted from PDF (in *_images/ directory)
2. Images referenced in JSON
3. Expected orphans (cover pages, decorative headers)

Usage:
    uv run validate_images.py [json_file]
"""

import json
import sys
from pathlib import Path


def find_json_file() -> Path:
    """Find the questions JSON file."""
    candidates = list(Path.cwd().glob("*_databanka_*.json"))
    if not candidates:
        candidates = list(Path.cwd().glob("questions*.json"))
    if not candidates:
        print("Error: No JSON file found. Run pdf_to_json.py first.")
        sys.exit(1)
    return candidates[0]


def find_images_dir(json_path: Path) -> Path:
    """Find the images directory based on JSON filename."""
    # Try stem_images pattern
    images_dir = json_path.parent / f"{json_path.stem}_images"
    if images_dir.exists():
        return images_dir

    # Try finding any *_images directory
    candidates = list(json_path.parent.glob("*_images"))
    if candidates:
        return candidates[0]

    print(f"Error: Images directory not found for {json_path.name}")
    sys.exit(1)


def get_referenced_images(data: dict) -> set[str]:
    """Extract all image filenames referenced in JSON."""
    images = set()
    for section in data.get("sections", []):
        for q in section.get("questions", []):
            if q.get("image"):
                images.add(q["image"].split("/")[-1])
            for opt in q.get("options", []):
                if opt.get("image"):
                    images.add(opt["image"].split("/")[-1])
    return images


def get_questions_with_images(data: dict) -> list[dict]:
    """Get list of questions that have images."""
    result = []
    for section in data.get("sections", []):
        for q in section.get("questions", []):
            has_q_img = bool(q.get("image"))
            opt_imgs = [opt["label"] for opt in q.get("options", []) if opt.get("image")]
            if has_q_img or opt_imgs:
                result.append({
                    "section": section["id"],
                    "question": q["id"],
                    "text": q["text"][:50] + "...",
                    "q_image": q.get("image", "").split("/")[-1] if q.get("image") else None,
                    "opt_images": opt_imgs,
                })
    return result


def main():
    # Find files
    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])
    else:
        json_path = find_json_file()

    images_dir = find_images_dir(json_path)

    print(f"JSON file: {json_path.name}")
    print(f"Images dir: {images_dir.name}")
    print("=" * 70)

    # Load JSON
    with open(json_path) as f:
        data = json.load(f)

    # Get image sets
    dir_images = set(f.name for f in images_dir.iterdir() if f.is_file())
    json_images = get_referenced_images(data)

    # Calculate differences
    orphaned = dir_images - json_images
    missing = json_images - dir_images

    # Print summary
    print(f"\nImages in directory: {len(dir_images)}")
    print(f"Images in JSON: {len(json_images)}")
    print(f"Orphaned (not in JSON): {len(orphaned)}")
    print(f"Missing (in JSON but not on disk): {len(missing)}")

    # Details
    if orphaned:
        print(f"\n{'='*70}")
        print("ORPHANED IMAGES (extracted but not linked):")
        print("  These are expected: cover pages, section headers")
        print("-" * 70)
        for img in sorted(orphaned):
            size = (images_dir / img).stat().st_size
            print(f"  {img} ({size:,} bytes)")

    if missing:
        print(f"\n{'='*70}")
        print("MISSING IMAGES (linked but not on disk):")
        print("  These are ERRORS - images referenced but not extracted!")
        print("-" * 70)
        for img in sorted(missing):
            print(f"  {img}")

    # Questions with images
    questions = get_questions_with_images(data)
    print(f"\n{'='*70}")
    print(f"QUESTIONS WITH IMAGES ({len(questions)} total):")
    print("-" * 70)
    for q in questions:
        img_type = f"[Q: {q['q_image']}]" if q['q_image'] else f"[Opts: {','.join(q['opt_images'])}]"
        print(f"  S{q['section']}.Q{q['question']}: {img_type}")
        print(f"    {q['text']}")

    # Final status
    print(f"\n{'='*70}")
    if missing:
        print("STATUS: FAILED - Missing images detected!")
        sys.exit(1)
    elif len(orphaned) > 5:
        print(f"STATUS: WARNING - {len(orphaned)} orphaned images (expected ~4)")
        sys.exit(0)
    else:
        print("STATUS: OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
