"""Generate reproducible ETAP 11A PDF examples, previews and a ZIP package."""

import argparse
import hashlib
import json
import sys
import time
import zipfile
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.generate_pdf_latex import generate_pdf_latex, get_template_version
from scripts.pdf_samples import PROFILES, artifact_documents


DEFAULT_OUTPUT = ROOT / "documentation" / "testy-pdf"


def _clean_generated_files(directory, patterns):
    directory.mkdir(parents=True, exist_ok=True)
    for pattern in patterns:
        for path in directory.glob(pattern):
            if path.is_file():
                path.unlink()


def _pdf_metadata(pdf_bytes):
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        text = "\n".join(page.get_text() for page in document)
        first_page = document[0]
        return {
            "pages": document.page_count,
            "width_points": round(first_page.rect.width, 2),
            "height_points": round(first_page.rect.height, 2),
            "contains_page_number": "Strona 1" in text,
            "text_length": len(text),
        }


def generate(output_dir=DEFAULT_OUTPUT):
    output_dir = Path(output_dir).resolve()
    examples_dir = output_dir / "przyklady"
    previews_dir = output_dir / "podglady"
    _clean_generated_files(examples_dir, ("*.pdf", "*.json", "*.zip"))
    _clean_generated_files(previews_dir, ("*.png",))

    manifest = {
        "generated_at": "2026-06-07",
        "generator": "XeLaTeX + Jinja2",
        "profiles": list(PROFILES),
        "documents": [],
    }
    inputs = {}
    started_all = time.perf_counter()

    for file_name, template_key, context in artifact_documents():
        started = time.perf_counter()
        pdf_bytes = generate_pdf_latex(template_key, context).getvalue()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        pdf_path = examples_dir / file_name
        pdf_path.write_bytes(pdf_bytes)

        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            preview = document[0].get_pixmap(
                matrix=fitz.Matrix(1.35, 1.35),
                alpha=False,
            )
            preview.save(previews_dir / f"{pdf_path.stem}_strona_1.png")
            if file_name == "dziennik_31001.pdf" and document.page_count > 1:
                second = document[1].get_pixmap(
                    matrix=fitz.Matrix(1.35, 1.35),
                    alpha=False,
                )
                second.save(previews_dir / "dziennik_31001_strona_2.png")

        metadata = _pdf_metadata(pdf_bytes)
        metadata.update({
            "file": file_name,
            "template": template_key,
            "template_version": get_template_version(template_key),
            "size_bytes": len(pdf_bytes),
            "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "generation_time_ms": elapsed_ms,
        })
        manifest["documents"].append(metadata)
        inputs[file_name] = context

    manifest["total_generation_time_ms"] = round(
        (time.perf_counter() - started_all) * 1000,
        1,
    )
    manifest_path = examples_dir / "manifest.json"
    inputs_path = examples_dir / "dane_wejsciowe.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    inputs_path.write_text(
        json.dumps(inputs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    zip_path = examples_dir / "pakiet_zbiorczy_etap11a.zip"
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(examples_dir.glob("*.pdf")):
            archive.write(path, path.name)
        archive.write(manifest_path, manifest_path.name)
        archive.write(inputs_path, inputs_path.name)

    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory for examples, previews and the ZIP package.",
    )
    args = parser.parse_args()
    manifest = generate(args.output)
    print(
        f"Generated {len(manifest['documents'])} PDFs in "
        f"{manifest['total_generation_time_ms']} ms."
    )


if __name__ == "__main__":
    main()
