"""Tests for DocumentProcessor and related helpers.

Covers sentence splitting, chunking, frontmatter extraction, and the
full document processing pipeline.
"""

import pytest

from src.processors.document_processor import DocumentProcessor, _split_sentences_ja

# Re-use the lightweight mock from conftest
from tests.conftest import MockConfig

# ---------------------------------------------------------------------------
# _split_sentences_ja (module-level function)
# ---------------------------------------------------------------------------


class TestSplitSentencesJa:
    """Tests for Japanese sentence boundary detection."""

    def test_split_basic_japanese(self):
        text = "これは最初の文です。二番目の文です。三番目の文です。"
        result = _split_sentences_ja(text)
        assert len(result) == 3

    def test_split_exclamation_and_question(self):
        text = "すごい！本当ですか？はい、そうです。"
        result = _split_sentences_ja(text)
        assert len(result) == 3

    def test_split_fullwidth_punctuation(self):
        text = "驚きました！本当に？そうなんです。"
        result = _split_sentences_ja(text)
        assert len(result) == 3

    def test_split_mixed_language(self):
        text = "日本語の文です。This is English. また日本語。"
        result = _split_sentences_ja(text)
        assert len(result) >= 3

    def test_empty_string(self):
        result = _split_sentences_ja("")
        assert result == []

    def test_whitespace_only(self):
        result = _split_sentences_ja("   \n\n  ")
        assert result == []

    def test_single_sentence_no_ending(self):
        text = "終端記号がない文"
        result = _split_sentences_ja(text)
        assert len(result) == 1
        assert result[0] == "終端記号がない文"

    def test_preserves_content(self):
        """Splitting should not lose any non-whitespace content."""
        text = "一番目。二番目。三番目。"
        result = _split_sentences_ja(text)
        joined = "".join(result)
        # Remove whitespace for comparison
        assert joined.replace(" ", "") == text.replace(" ", "").replace("\n", "")

    def test_newline_boundaries(self):
        text = "最初の行\n二番目の行\n三番目の行"
        result = _split_sentences_ja(text)
        assert len(result) >= 2


# ---------------------------------------------------------------------------
# DocumentProcessor._extract_front_matter
# ---------------------------------------------------------------------------


class TestExtractFrontMatter:
    """Tests for YAML frontmatter extraction."""

    def test_basic_frontmatter(self):
        content = "---\ntitle: テスト\ncategory: test/unit\n---\n# 本文\nここは本文です。"
        proc = DocumentProcessor(MockConfig())
        metadata, text = proc._extract_front_matter(content)
        assert metadata["title"] == "テスト"
        assert metadata["category"] == "test/unit"
        assert "本文" in text

    def test_no_frontmatter(self):
        content = "# タイトル\n\n本文がここにあります。"
        proc = DocumentProcessor(MockConfig())
        metadata, text = proc._extract_front_matter(content)
        # Should return empty defaults
        assert metadata.get("title") == ""
        assert "本文" in text

    def test_invalid_yaml(self):
        content = "---\n: invalid: yaml: [broken\n---\n本文です。"
        proc = DocumentProcessor(MockConfig())
        metadata, text = proc._extract_front_matter(content)
        # Should gracefully fall back to defaults
        assert isinstance(metadata, dict)

    def test_extra_fields_preserved(self):
        content = "---\ntitle: テスト\nauthor: 著者\ntags: [a, b]\n---\n本文。"
        proc = DocumentProcessor(MockConfig())
        metadata, text = proc._extract_front_matter(content)
        assert metadata["author"] == "著者"
        assert metadata["tags"] == ["a", "b"]


# ---------------------------------------------------------------------------
# DocumentProcessor._chunk_text_ja
# ---------------------------------------------------------------------------


class TestChunkTextJa:
    """Tests for Japanese-aware text chunking."""

    def test_short_text_single_chunk(self):
        proc = DocumentProcessor(MockConfig())
        text = "短いテキストです。"
        chunks = proc._chunk_text_ja(text)
        assert len(chunks) == 1

    def test_chunk_respects_size_limit(self):
        config = MockConfig({"chunking.chunk_size": 50, "chunking.chunk_overlap": 10})
        proc = DocumentProcessor(config)
        # Each sentence ~7 chars; 20 sentences total ~140 chars
        text = "短い文です。" * 20
        chunks = proc._chunk_text_ja(text)
        assert len(chunks) > 1

    def test_chunk_overlap(self):
        config = MockConfig({"chunking.chunk_size": 100, "chunking.chunk_overlap": 30})
        proc = DocumentProcessor(config)
        text = (
            "一番目の文章です。二番目の文章です。三番目の文章です。"
            "四番目の文章です。五番目の文章です。六番目の文章です。"
            "七番目の文章です。八番目の文章です。"
        )
        chunks = proc._chunk_text_ja(text)
        if len(chunks) >= 2:
            # At least one sentence from the first chunk should appear in the second
            first_sentences = set(chunks[0].split("\n"))
            second_text = chunks[1]
            overlap_found = any(s in second_text for s in first_sentences if s.strip())
            assert overlap_found, "Expected overlap between consecutive chunks"

    def test_empty_text(self):
        proc = DocumentProcessor(MockConfig())
        chunks = proc._chunk_text_ja("")
        assert chunks == []

    def test_whitespace_only_text(self):
        proc = DocumentProcessor(MockConfig())
        chunks = proc._chunk_text_ja("   \n\n   ")
        assert chunks == []

    def test_long_single_sentence(self):
        """A single sentence exceeding chunk_size should still be returned."""
        config = MockConfig({"chunking.chunk_size": 10, "chunking.chunk_overlap": 3})
        proc = DocumentProcessor(config)
        text = "これはチャンクサイズを大幅に超える非常に長い一文です"
        chunks = proc._chunk_text_ja(text)
        assert len(chunks) >= 1
        # The content should not be lost
        assert text in "".join(chunks)


# ---------------------------------------------------------------------------
# DocumentProcessor.process_document (integration with filesystem)
# ---------------------------------------------------------------------------


class TestProcessDocument:
    """Tests for the full document processing pipeline."""

    def test_process_valid_document(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "---\ntitle: テストドキュメント\ncategory: test\n---\n"
            "# テスト\n\nこれはテスト文書です。内容がここに入ります。",
            encoding="utf-8",
        )

        proc = DocumentProcessor(MockConfig())
        metadata, chunks = proc.process_document(str(md_file))

        assert metadata["title"] == "テストドキュメント"
        assert metadata["category"] == "test"
        assert len(chunks) >= 1
        assert all(
            key in c for c in chunks for key in ("id", "text", "doc_id", "position")
        )

    def test_process_document_without_frontmatter(self, tmp_path):
        md_file = tmp_path / "no_front.md"
        md_file.write_text("# 自動タイトル\n\n本文です。", encoding="utf-8")

        proc = DocumentProcessor(MockConfig())
        metadata, chunks = proc.process_document(str(md_file))

        # Title should be extracted from the heading
        assert metadata["title"] == "自動タイトル"
        assert len(chunks) >= 1

    def test_process_document_file_not_found(self):
        proc = DocumentProcessor(MockConfig())
        with pytest.raises(FileNotFoundError):
            proc.process_document("/nonexistent/path/file.md")

    def test_process_document_unsupported_extension(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("plain text", encoding="utf-8")

        proc = DocumentProcessor(MockConfig())
        with pytest.raises(ValueError, match="Unsupported file extension"):
            proc.process_document(str(txt_file))

    def test_chunk_objects_have_sequential_positions(self, tmp_path):
        md_file = tmp_path / "multi.md"
        # Create enough content to produce multiple chunks
        content = "---\ntitle: マルチチャンク\n---\n" + ("テスト文です。" * 200)
        md_file.write_text(content, encoding="utf-8")

        config = MockConfig({"chunking.chunk_size": 100, "chunking.chunk_overlap": 20})
        proc = DocumentProcessor(config)
        metadata, chunks = proc.process_document(str(md_file))

        positions = [c["position"] for c in chunks]
        assert positions == list(range(len(chunks)))

    def test_chunk_objects_share_doc_id(self, tmp_path):
        md_file = tmp_path / "shared.md"
        md_file.write_text(
            "---\ntitle: 共有ID\nid: custom-id-123\n---\n本文。" * 10,
            encoding="utf-8",
        )

        proc = DocumentProcessor(MockConfig())
        metadata, chunks = proc.process_document(str(md_file))

        doc_ids = {c["doc_id"] for c in chunks}
        assert len(doc_ids) == 1
        assert "custom-id-123" in doc_ids


# ---------------------------------------------------------------------------
# DocumentProcessor.process_directory
# ---------------------------------------------------------------------------


class TestProcessDirectory:
    """Tests for batch directory processing."""

    def test_process_directory_finds_md_files(self, tmp_path):
        (tmp_path / "a.md").write_text("---\ntitle: A\n---\n内容A。", encoding="utf-8")
        (tmp_path / "b.md").write_text("---\ntitle: B\n---\n内容B。", encoding="utf-8")
        (tmp_path / "c.txt").write_text("無視されるファイル", encoding="utf-8")

        proc = DocumentProcessor(MockConfig())
        docs, chunks = proc.process_directory(str(tmp_path))

        assert len(docs) == 2

    def test_process_directory_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "root.md").write_text("---\ntitle: Root\n---\n内容。", encoding="utf-8")
        (sub / "nested.md").write_text("---\ntitle: Nested\n---\n内容。", encoding="utf-8")

        proc = DocumentProcessor(MockConfig())
        docs, _ = proc.process_directory(str(tmp_path), recursive=True)
        assert len(docs) == 2

    def test_process_directory_non_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "root.md").write_text("---\ntitle: Root\n---\n内容。", encoding="utf-8")
        (sub / "nested.md").write_text("---\ntitle: Nested\n---\n内容。", encoding="utf-8")

        proc = DocumentProcessor(MockConfig())
        docs, _ = proc.process_directory(str(tmp_path), recursive=False)
        assert len(docs) == 1
