"""
PDF processor for converting PDF files to Markdown text.
Uses pymupdf4llm for LLM-optimized conversion.
"""

import logging
import os
import tempfile
from pathlib import Path

import pymupdf4llm

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Convert PDF files to Markdown for downstream processing."""

    SUPPORTED_EXTENSIONS = [".pdf"]

    def convert_to_markdown(self, file_path: str) -> str:
        """Convert a PDF file to Markdown text.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Markdown text extracted from the PDF.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is not supported.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        ext = Path(file_path).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension: {ext}. Supported: {self.SUPPORTED_EXTENSIONS}"
            )

        logger.info(f"Converting PDF to Markdown: {file_path}")
        md_text = pymupdf4llm.to_markdown(file_path)
        logger.info(
            f"PDF converted successfully: {len(md_text)} characters extracted"
        )
        return md_text

    def convert_uploaded_file(self, uploaded_file) -> str:
        """Convert a Streamlit UploadedFile to Markdown text.

        Writes the uploaded bytes to a temporary file, then converts.

        Args:
            uploaded_file: Streamlit UploadedFile object.

        Returns:
            Markdown text extracted from the PDF.
        """
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = tmp.name

        try:
            return self.convert_to_markdown(tmp_path)
        finally:
            os.unlink(tmp_path)
