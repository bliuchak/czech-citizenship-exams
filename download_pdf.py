# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.27.0",
# ]
# ///
"""
Download the official Czech citizenship test question bank PDF.

Source: https://cestina-pro-cizince.cz/obcanstvi/databanka-uloh/

Usage:
    uv run download_pdf.py
"""

import sys
from pathlib import Path

import httpx

PDF_URL = "https://cestina-pro-cizince.cz/obcanstvi/wp-content/uploads/2025/12/OBC_databanka_testovychuloh_251215.pdf"
PDF_FILENAME = "OBC_databanka_testovychuloh_251215.pdf"


def download_pdf(url: str, output_path: Path) -> bool:
    """Download PDF with progress indication."""
    print(f"Downloading: {url}")
    print(f"Saving to: {output_path}")

    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
            response.raise_for_status()

            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r  Progress: {pct}% ({downloaded:,} / {total:,} bytes)", end="")

            print()  # newline after progress

        size = output_path.stat().st_size
        print(f"Downloaded: {size:,} bytes")
        return True

    except httpx.HTTPError as e:
        print(f"Error downloading: {e}")
        return False


def main():
    output_path = Path.cwd() / PDF_FILENAME

    if output_path.exists():
        size = output_path.stat().st_size
        print(f"File already exists: {output_path.name} ({size:,} bytes)")
        print("Delete it first if you want to re-download.")
        sys.exit(0)

    success = download_pdf(PDF_URL, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
