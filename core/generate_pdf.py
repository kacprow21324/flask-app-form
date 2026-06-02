from flask import render_template
from weasyprint import HTML
import io


def generate_pdf(app, zal_key, context):
    with app.app_context():
        html_string = render_template(f"print/{zal_key}.html", **context)
    buf = io.BytesIO()
    HTML(string=html_string).write_pdf(buf)
    buf.seek(0)
    return buf
