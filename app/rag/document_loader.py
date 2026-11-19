import os
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader

class DocumentLoader:
    def load(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Loads document content by page/section.
        Returns a list of dicts: [{"page": int, "text": str}]
        """
        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        ext = p.suffix.lower()
        if ext == ".pdf":
            return self._load_pdf(p)
        elif ext in [".txt", ".md"]:
            return self._load_text(p)
        else:
            raise ValueError(f"Formato de arquivo não suportado: '{ext}'. Suportados: .pdf, .txt, .md")

    def _load_pdf(self, path: Path) -> List[Dict[str, Any]]:
        pages = []
        reader = PdfReader(str(path))
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append({"page": idx + 1, "text": text})
        return pages

    def _load_text(self, path: Path) -> List[Dict[str, Any]]:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return []
        return [{"page": 1, "text": text}]

document_loader = DocumentLoader()
