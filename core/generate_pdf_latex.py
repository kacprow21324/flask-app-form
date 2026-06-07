"""
LaTeX-based PDF generation for ANS Elblag internship forms.
Uses xelatex (from MiKTeX or TeX Live) to compile Jinja2-templated .tex.j2 files.

Requirements:
    - MiKTeX (Windows): https://miktex.org/download
      After install run: miktex-console → Updates → Check for updates
      Packages needed: fontspec, geometry, booktabs, tabularx, fancyhdr, xcolor
    - OR TeX Live (cross-platform): https://www.tug.org/texlive/
    - xelatex must be on the system PATH

Usage:
    from core.generate_pdf_latex import generate_pdf_latex
    buf = generate_pdf_latex('zal1', context_dict)
    # buf is a BytesIO containing the PDF
"""

import os
import hashlib
import re
import shutil
import subprocess
import tempfile
import io

from jinja2 import Environment, FileSystemLoader

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # katalog główny (pakiet core/ jest poziom niżej)
LATEX_DIR = os.path.join(BASE, "templates", "latex")
VALID_TEMPLATE_KEY = re.compile(r"^zal[1-9][a-z]?$")


class PDFGenerationError(RuntimeError):
    """Base error raised when a PDF cannot be generated."""


class PDFTemplateNotFound(FileNotFoundError, PDFGenerationError):
    """The requested LaTeX template does not exist."""


class PDFEngineUnavailable(PDFGenerationError):
    """XeLaTeX is not installed or cannot be executed."""


class PDFGenerationTimeout(PDFGenerationError):
    """XeLaTeX did not finish within the configured timeout."""


class PDFCompilationError(PDFGenerationError):
    """XeLaTeX rejected the rendered document."""


def _template_path(zal_key):
    if not isinstance(zal_key, str) or not VALID_TEMPLATE_KEY.fullmatch(zal_key):
        raise PDFTemplateNotFound(f"Invalid LaTeX template key: {zal_key!r}")
    path = os.path.join(LATEX_DIR, f"{zal_key}.tex.j2")
    if not os.path.isfile(path):
        raise PDFTemplateNotFound(f"LaTeX template not found: {path}")
    return path


def get_template_version(zal_key):
    template_path = _template_path(zal_key)
    digest = hashlib.sha256()
    for path in (
        os.path.join(LATEX_DIR, "base.tex"),
        template_path,
    ):
        with open(path, "rb") as handle:
            digest.update(handle.read())
    return f"latex-{digest.hexdigest()[:16]}"


def _latex_escape(s):
    """Escape special LaTeX characters in a string value."""
    if s is None:
        return ''
    s = str(s)
    # Order matters: backslash must be first
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&',  r'\&'),
        ('%',  r'\%'),
        ('$',  r'\$'),
        ('#',  r'\#'),
        ('_',  r'\_'),
        ('{',  r'\{'),
        ('}',  r'\}'),
        ('~',  r'\textasciitilde{}'),
        ('^',  r'\textasciicircum{}'),
    ]
    for old, new in replacements:
        s = s.replace(old, new)
    return s


def _le(s):
    """Short alias for latex_escape."""
    return _latex_escape(s)


# Jinja2 environment with LaTeX-safe delimiters
env = Environment(
    variable_start_string='((',
    variable_end_string='))',
    block_start_string='((*',
    block_end_string='*))',
    comment_start_string='((#',
    comment_end_string='#))',
    loader=FileSystemLoader(LATEX_DIR),
    autoescape=False,
    keep_trailing_newline=True,
)
env.filters['latex_escape'] = _latex_escape
env.filters['le'] = _le


def generate_pdf_latex(zal_key, context):
    """
    Render a LaTeX template and compile it with xelatex.

    Args:
        zal_key: template key, e.g. 'zal1', 'zal2a', 'zal4b'
        context: dict passed to the Jinja2 template

    Returns:
        io.BytesIO with the compiled PDF content

    Raises:
        PDFTemplateNotFound: if the .tex.j2 template does not exist
        PDFEngineUnavailable: if xelatex cannot be executed
        PDFGenerationTimeout: if compilation exceeds 60 seconds
        PDFCompilationError: if xelatex fails or produces an invalid PDF
    """
    template_path = _template_path(zal_key)
    template_name = os.path.basename(template_path)

    tpl = env.get_template(template_name)
    tex_source = tpl.render(**context)

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "doc.tex")
        pdf_path = os.path.join(tmpdir, "doc.pdf")

        # Copy base.tex into the temp dir so \input{base} resolves correctly
        base_src = os.path.join(LATEX_DIR, "base.tex")
        base_dst = os.path.join(tmpdir, "base.tex")
        if os.path.exists(base_src):
            shutil.copy2(base_src, base_dst)

        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(tex_source)

        # Run xelatex twice so cross-references and page numbers settle
        for run_number in range(1, 3):
            try:
                result = subprocess.run(
                    [
                        'xelatex',
                        '-no-shell-escape',
                        '-halt-on-error',
                        '-interaction=nonstopmode',
                        '-output-directory', tmpdir,
                        tex_path,
                    ],
                    capture_output=True,
                    timeout=60,
                    cwd=tmpdir,
                )
            except FileNotFoundError as exc:
                raise PDFEngineUnavailable(
                    "XeLaTeX executable was not found on PATH."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise PDFGenerationTimeout(
                    f"XeLaTeX timed out while compiling '{template_name}'."
                ) from exc

            if result.returncode != 0:
                stdout = result.stdout.decode('utf-8', errors='replace')
                stderr = result.stderr.decode('utf-8', errors='replace')
                log_tail = (stdout + stderr)[-4000:]
                raise PDFCompilationError(
                    f"xelatex run {run_number} failed for template "
                    f"'{template_name}'.\nLast 4000 chars of log:\n{log_tail}"
                )

        if not os.path.isfile(pdf_path):
            stdout = result.stdout.decode('utf-8', errors='replace')
            stderr = result.stderr.decode('utf-8', errors='replace')
            log_tail = (stdout + stderr)[-4000:]
            raise PDFCompilationError(
                f"xelatex failed for template '{template_name}'.\n"
                f"Last 4000 chars of log:\n{log_tail}"
            )

        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        if not pdf_bytes.startswith(b"%PDF-"):
            raise PDFCompilationError(
                f"xelatex produced an invalid PDF for '{template_name}'."
            )
        buf = io.BytesIO(pdf_bytes)

    buf.seek(0)
    return buf
