from pathlib import Path
from typing import Union

try:
    import pdfplumber
    _PDF_BACKEND = "pdfplumber"
except ImportError:
    try:
        # pyrefly: ignore [missing-import]
        from PyPDF2 import PdfReader
        _PDF_BACKEND = "pypdf2"
    except ImportError:
        try:
            from pdfminer.high_level import extract_text
            _PDF_BACKEND = "pdfminer"
        except ImportError:
            _PDF_BACKEND = "text"
            extract_text = None


class PDFLoader:
    """Extract raw text from PDF files.  
    Uses pdfplumber if available, falls back to PyPDF2, then plain-text read."""

    def load(self, file_path: Union[str, Path]) -> str:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        # Non-PDF: read as plain text immediately
        try:
            with open(path, "rb") as f:
                header = f.read(4)
            if header != b"%PDF":
                return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

        # pdfplumber backend
        if _PDF_BACKEND == "pdfplumber":
            try:
                with pdfplumber.open(str(path)) as pdf:
                    return "\n".join(
                        (page.extract_text() or "") for page in pdf.pages
                    )
            except Exception:
                pass

        # PyPDF2 backend
        if _PDF_BACKEND == "pypdf2":
            try:
                reader = PdfReader(str(path))
                return "\n".join(
                    (page.extract_text() or "") for page in reader.pages
                )
            except Exception:
                pass

        # pdfminer backend
        if _PDF_BACKEND == "pdfminer":
            try:
                return extract_text(str(path))
            except Exception:
                pass

        # Final fallback: if it reached here, all PDF parsing failed.
        # Do NOT read as plain text because it will yield binary garbage.
        return ""
