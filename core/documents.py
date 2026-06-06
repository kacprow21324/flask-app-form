import hashlib
import os
from datetime import datetime

from core.models import GeneratedDocument, db


def archive_pdf(
    pdf_bytes,
    *,
    base_dir,
    album_number,
    form_key,
    file_name,
    generated_by,
    internship=None,
):
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    relative_dir = os.path.join("generated", str(album_number))
    target_dir = os.path.join(base_dir, relative_dir)
    os.makedirs(target_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    stored_name = f"{form_key}_{timestamp}_{digest[:12]}.pdf"
    absolute_path = os.path.join(target_dir, stored_name)
    with open(absolute_path, "wb") as handle:
        handle.write(pdf_bytes)

    document = GeneratedDocument(
        internship_id=getattr(internship, "id", None),
        album_number=str(album_number),
        form_key=form_key,
        template_version="latex-v1",
        file_path=os.path.join(relative_dir, stored_name).replace("\\", "/"),
        file_name=file_name,
        file_size_bytes=len(pdf_bytes),
        mime_type="application/pdf",
        checksum_sha256=digest,
        generated_by=getattr(generated_by, "id", None),
        download_count=1,
    )
    db.session.add(document)
    return document, absolute_path
