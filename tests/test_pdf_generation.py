import subprocess
import unittest
from unittest.mock import patch

import fitz

from core.generate_pdf_latex import (
    PDFCompilationError,
    PDFEngineUnavailable,
    PDFGenerationTimeout,
    PDFTemplateNotFound,
    _latex_escape,
    generate_pdf_latex,
)
from scripts.pdf_samples import (
    EFFECT_MAP,
    PROFILES,
    diary_context,
    effects_context,
    report_context,
)


def pdf_document(buffer):
    return fitz.open(stream=buffer.getvalue(), filetype="pdf")


def pdf_text(buffer):
    with pdf_document(buffer) as document:
        return "\n".join(page.get_text() for page in document)


def normalized_pdf_text(buffer):
    return pdf_text(buffer).replace("-\n", "").replace("\n", " ")


class PDFGenerationTests(unittest.TestCase):
    template_keys = (
        "zal1", "zal2", "zal2a", "zal3", "zal4", "zal4a", "zal4b",
        "zal5", "zal6", "zal7", "zal7a", "zal8",
    )

    @classmethod
    def setUpClass(cls):
        cls.diaries = [
            generate_pdf_latex("zal6", diary_context(profile))
            for profile in PROFILES
        ]
        cls.effects = [
            generate_pdf_latex("zal4", effects_context(profile))
            for profile in PROFILES
        ]

    def test_three_diaries_contain_database_equivalent_student_data(self):
        for profile, buffer in zip(PROFILES, self.diaries):
            text = pdf_text(buffer)
            self.assertIn(profile["name"], text)
            self.assertIn(profile["album"], text)
            self.assertIn(profile["company"], text)
            self.assertIn("Konfiguracja środowiska testowego", text)

    def test_three_effect_confirmations_contain_students_and_effects(self):
        for profile, buffer in zip(PROFILES, self.effects):
            text = normalized_pdf_text(buffer)
            self.assertIn(profile["name"], text)
            self.assertIn(profile["album"], text)
            self.assertIn(EFFECT_MAP[1], text)
            self.assertIn("osiągnięty", text)

    def test_diary_is_a4_and_has_page_numbers(self):
        with pdf_document(self.diaries[0]) as document:
            self.assertAlmostEqual(document[0].rect.width, 595.28, delta=1)
            self.assertAlmostEqual(document[0].rect.height, 841.89, delta=1)
            for number, page in enumerate(document, start=1):
                self.assertIn(f"Strona {number}", page.get_text())

    def test_long_diary_splits_across_pages_and_repeats_header(self):
        buffer = generate_pdf_latex(
            "zal6",
            diary_context(PROFILES[0], count=70, long_text=True),
        )
        with pdf_document(buffer) as document:
            self.assertGreaterEqual(document.page_count, 4)
            full_text = "\n".join(page.get_text() for page in document)
            self.assertIn("70", full_text)
            self.assertIn("identyfikator #PDF", full_text)
            for page in document:
                text = page.get_text()
                self.assertIn("Opis wykonanych prac", text)
                self.assertRegex(text, r"Strona \d+")

    def test_final_report_contains_complete_summary_and_polish_text(self):
        buffer = generate_pdf_latex("zal7", report_context(PROFILES[2]))
        text = pdf_text(buffer)
        self.assertIn(
            "SPRAWOZDANIEZPRAKTYKIZAWODOWEJ",
            normalized_pdf_text(buffer).replace(" ", ""),
        )
        self.assertIn("Małgorzata Ździebło", text)
        self.assertIn(
            "CHARAKTERYSTYKAZAKŁADUPRACY",
            normalized_pdf_text(buffer).replace(" ", ""),
        )
        self.assertIn("współpracę z zespołem", text)
        self.assertIn("Strona 1", text)

    def test_empty_optional_lists_still_produce_valid_pdf(self):
        context = diary_context(PROFILES[0], count=0)
        buffer = generate_pdf_latex("zal6", context)
        self.assertTrue(buffer.getvalue().startswith(b"%PDF-"))
        self.assertIn(
            "DZIENNIKPRAKTYKIZAWODOWEJ",
            normalized_pdf_text(buffer).replace(" ", ""),
        )

    def test_long_report_text_is_wrapped_without_generation_failure(self):
        context = report_context(PROFILES[1], long_text=True)
        context["data"]["opis_prac"] += " KONIEC-ROZBUDOWANEGO-OPISU"
        buffer = generate_pdf_latex("zal7", context)
        with pdf_document(buffer) as document:
            self.assertGreaterEqual(document.page_count, 2)
            text = "\n".join(page.get_text() for page in document)
            self.assertIn("R&D Północ S.A.", text)
            self.assertIn("KONIEC-ROZBUDOWANEGO-OPISU", text)

    def test_female_student_wording_is_used_in_pdf(self):
        context = report_context(PROFILES[0])
        context["data"]["gender"] = "K"
        buffer = generate_pdf_latex("zal7", context)
        self.assertIsNotNone(buffer)

    def test_latex_special_characters_are_escaped(self):
        escaped = _latex_escape(r"R&D 100% plik_test #1 C:\backup")
        self.assertIn(r"R\&D", escaped)
        self.assertIn(r"100\%", escaped)
        self.assertIn(r"plik\_test", escaped)
        self.assertIn(r"\#1", escaped)

    def test_invalid_or_missing_template_is_rejected(self):
        with self.assertRaises(PDFTemplateNotFound):
            generate_pdf_latex("../base", {"data": {}})
        with self.assertRaises(PDFTemplateNotFound):
            generate_pdf_latex("zal99", {"data": {}})

    def test_all_document_templates_compile_with_minimal_data(self):
        context = {
            "data": {},
            "effect_map": {},
            "effects": [],
            "questions": [],
            "options": [],
            "specialties": [],
            "sn": False,
        }
        for template_key in self.template_keys:
            with self.subTest(template=template_key):
                buffer = generate_pdf_latex(template_key, context)
                self.assertTrue(buffer.getvalue().startswith(b"%PDF-"))

    @patch("core.generate_pdf_latex.subprocess.run")
    def test_missing_xelatex_is_reported(self, run):
        run.side_effect = FileNotFoundError("xelatex")
        with self.assertRaises(PDFEngineUnavailable):
            generate_pdf_latex("zal7", report_context(PROFILES[0]))

    @patch("core.generate_pdf_latex.subprocess.run")
    def test_xelatex_timeout_is_reported(self, run):
        run.side_effect = subprocess.TimeoutExpired("xelatex", 60)
        with self.assertRaises(PDFGenerationTimeout):
            generate_pdf_latex("zal7", report_context(PROFILES[0]))

    @patch("core.generate_pdf_latex.subprocess.run")
    def test_xelatex_nonzero_exit_is_reported_with_log(self, run):
        run.return_value.returncode = 1
        run.return_value.stdout = b"latex compilation failed"
        run.return_value.stderr = b""
        with self.assertRaisesRegex(
            PDFCompilationError,
            "latex compilation failed",
        ):
            generate_pdf_latex("zal7", report_context(PROFILES[0]))


if __name__ == "__main__":
    unittest.main()
