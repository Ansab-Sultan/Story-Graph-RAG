"""File validation, persistence, and parsing helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.core.config import Settings
from app.core.constants import SUPPORTED_EXTENSIONS
from app.core.exceptions import UnsupportedFileTypeError


@dataclass(slots=True)
class FileService:
    settings: Settings

    def validate_extension(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file type '{suffix}'. Only .pdf and .txt are supported."
            )
        return suffix

    async def save_upload(self, upload: UploadFile, story_id: str) -> Path:
        self.validate_extension(upload.filename or "")
        filename = upload.filename or f"{story_id}.txt"
        target_path = self.settings.upload_dir / f"{story_id}_{filename}"
        data = await upload.read()
        target_path.write_bytes(data)
        await upload.close()
        return target_path

    def load_raw_text(self, file_path: Path) -> str:
        suffix = self.validate_extension(file_path.name)
        if suffix == ".txt":
            return file_path.read_text(encoding="utf-8")
        return self._extract_pdf_text(file_path)

    def build_graph_chunks(self, story_id: str, raw_text: str) -> list[Document]:
        return self._build_chunks(
            story_id,
            raw_text,
            chunk_size=self.settings.graph_chunk_size,
            chunk_overlap=self.settings.graph_chunk_overlap,
            chunk_id_prefix=f"{story_id}_graph_chunk_",
            chunk_kind="graph",
        )

    def build_vector_chunks(self, story_id: str, raw_text: str) -> list[Document]:
        return self._build_chunks(
            story_id,
            raw_text,
            chunk_size=self.settings.vector_chunk_size,
            chunk_overlap=self.settings.vector_chunk_overlap,
            chunk_id_prefix=f"{story_id}_chunk_",
            chunk_kind="vector",
        )

    def _build_chunks(
        self,
        story_id: str,
        raw_text: str,
        *,
        chunk_size: int,
        chunk_overlap: int,
        chunk_id_prefix: str,
        chunk_kind: str,
    ) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        raw_chunks = splitter.split_text(raw_text)
        return [
            Document(
                page_content=chunk,
                metadata={
                    "story_id": story_id,
                    "chunk_id": str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk_id_prefix}{index}")
                    ),
                    "chunk_label": f"{chunk_id_prefix}{index}",
                    "chunk_index": index,
                    "chunk_kind": chunk_kind,
                },
            )
            for index, chunk in enumerate(raw_chunks)
        ]

    def cleanup(self, file_path: str | Path) -> None:
        path = Path(file_path)
        if path.exists():
            path.unlink()

    def _extract_pdf_text(self, file_path: Path) -> str:
        reader = PdfReader(str(file_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
