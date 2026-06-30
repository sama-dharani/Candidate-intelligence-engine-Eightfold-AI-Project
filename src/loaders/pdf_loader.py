from pathlib import Path

try:
    import pdfplumber
    _PDF_BACKEND = "pdfplumber"
except ImportError:
    try:
        from PyPDF2 import PdfReader
        _PDF_BACKEND = "pypdf2"
    except ImportError:
        _PDF_BACKEND = "text"


class PDFLoader:
    """Extract raw text from PDF files.  
    Uses pdfplumber if available, falls back to PyPDF2, then plain-text read."""

    def load(self, file_path: str | Path) -> str:
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

        # Final fallback: read as text
        return path.read_text(encoding="utf-8", errors="ignore")
