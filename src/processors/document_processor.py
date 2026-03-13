"""
Document processor for parsing and chunking documents.

日本語対応版: 文境界（。！？）での分割、文字数ベースのチャンキング。
"""

import re
import os
import uuid
import yaml
import logging

logger = logging.getLogger(__name__)

# 日本語の文末パターン
_JA_SENTENCE_ENDINGS = re.compile(
    r'(?<=[。！？\!\?\n])\s*'
)

# 段落境界（空行）
_PARAGRAPH_BREAK = re.compile(r'\n\s*\n')


def _split_sentences_ja(text: str) -> list[str]:
    """日本語テキストを文単位で分割する。
    
    「。」「！」「？」「!」「?」および改行を文境界として使用。
    英語混在テキストにも対応（". " も境界として扱う）。
    """
    # まず段落を保持しつつ、文末で分割
    # 日本語の句点 + 英語のピリオド + 改行
    pattern = re.compile(
        r'(?<=[。！？\!\?])\s*'  # 日本語・英語の文末記号の後
        r'|(?<=\.)\s+(?=[A-Z\u3000-\u9fff])'  # 英語ピリオド後のスペース+大文字 or 日本語文字
        r'|(?<=\n)\s*(?=\S)'  # 改行後の非空白
    )
    
    sentences = pattern.split(text)
    # 空文字列を除去
    return [s.strip() for s in sentences if s and s.strip()]


class DocumentProcessor:
    """Process documents into chunks with metadata.
    
    日本語対応: 文字数ベースのチャンキング、文境界での分割。
    """
    
    def __init__(self, config):
        """Initialize with configuration"""
        self.config = config
        # 文字数ベース（日本語は1文字≒1情報単位、英語の1単語に相当）
        self.chunk_size = config.get('chunking.chunk_size', 800)
        self.chunk_overlap = config.get('chunking.chunk_overlap', 150)
        self.supported_extensions = ['.md', '.markdown']
    
    def process_document(self, file_path):
        """Process a document file into chunks with metadata"""
        logger.info(f"Processing document: {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document file not found: {file_path}")
            
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in self.supported_extensions:
            raise ValueError(
                f"Unsupported file extension: {ext}. "
                f"Supported: {self.supported_extensions}"
            )
        
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract YAML front matter and content
        metadata, text = self._extract_front_matter(content)
        
        # Add defaults and file path to metadata
        metadata['path'] = file_path
        if 'id' not in metadata:
            metadata['id'] = f"doc_{uuid.uuid4().hex[:8]}"
        
        # Ensure required fields
        if 'title' not in metadata or not metadata['title']:
            title = self._extract_title_from_text(text)
            if not title:
                title = os.path.basename(file_path)
            metadata['title'] = title
        
        if 'category' not in metadata:
            dir_path = os.path.dirname(file_path)
            base_dir = os.path.basename(dir_path)
            metadata['category'] = base_dir if base_dir else 'uncategorized'
        
        # Chunk the document（日本語対応版）
        chunks = self._chunk_text_ja(text)
        logger.info(f"Document chunked into {len(chunks)} parts")
        
        # Create chunk objects with metadata
        chunk_objects = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chunk_objects.append({
                'id': chunk_id,
                'text': chunk_text,
                'doc_id': metadata['id'],
                'position': i,
                'metadata': metadata,
            })
        
        return metadata, chunk_objects
    
    def _extract_front_matter(self, content):
        """Extract YAML front matter from document content"""
        front_matter_match = re.match(
            r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL
        )
        
        if front_matter_match:
            yaml_text = front_matter_match.group(1)
            content_text = front_matter_match.group(2)
            try:
                metadata = yaml.safe_load(yaml_text)
                if metadata and isinstance(metadata, dict):
                    logger.debug(f"Extracted metadata: {metadata.keys()}")
                    return metadata, content_text
            except yaml.YAMLError as e:
                logger.warning(f"Error parsing YAML front matter: {str(e)}")
        
        logger.debug("No valid front matter found, using defaults")
        return {'title': '', 'category': ''}, content
    
    def _extract_title_from_text(self, text):
        """Extract title from first heading in the document"""
        heading_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()
        return ''
    
    def _chunk_text_ja(self, text: str) -> list[str]:
        """日本語対応チャンク分割。
        
        アルゴリズム:
        1. テキストを文単位に分割
        2. 文を順次結合し、chunk_size文字に達したらチャンクとして確定
        3. chunk_overlap文字分の重複を持たせて次のチャンクを開始
        
        文の途中で切断しないため、チャンクサイズは目安値。
        """
        # 文単位に分割
        sentences = _split_sentences_ja(text)
        
        if not sentences:
            return [text.strip()] if text.strip() else []
        
        chunks = []
        current_chunk_sentences = []
        current_length = 0
        
        for sentence in sentences:
            sentence_len = len(sentence)
            
            # 現在のチャンク + この文が chunk_size を超える場合
            if current_length + sentence_len > self.chunk_size and current_chunk_sentences:
                # 現在のチャンクを確定
                chunk_text = '\n'.join(current_chunk_sentences).strip()
                if chunk_text:
                    chunks.append(chunk_text)
                
                # オーバーラップ: 末尾から overlap 文字分の文を残す
                overlap_sentences = []
                overlap_length = 0
                for s in reversed(current_chunk_sentences):
                    if overlap_length + len(s) > self.chunk_overlap:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_length += len(s)
                
                current_chunk_sentences = overlap_sentences
                current_length = overlap_length
            
            current_chunk_sentences.append(sentence)
            current_length += sentence_len
        
        # 残りの文をチャンクとして追加
        if current_chunk_sentences:
            chunk_text = '\n'.join(current_chunk_sentences).strip()
            if chunk_text:
                chunks.append(chunk_text)
        
        return chunks
    
    def process_directory(self, directory_path, recursive=True):
        """Process all documents in a directory"""
        logger.info(
            f"Processing directory: {directory_path} (recursive: {recursive})"
        )
        
        all_docs = []
        all_chunks = []
        
        files = []
        if recursive:
            for root, _, filenames in os.walk(directory_path):
                for filename in filenames:
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in self.supported_extensions:
                        files.append(os.path.join(root, filename))
        else:
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in self.supported_extensions:
                        files.append(file_path)
        
        logger.info(f"Found {len(files)} documents to process")
        
        for file_path in files:
            try:
                metadata, chunks = self.process_document(file_path)
                all_docs.append(metadata)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
        
        logger.info(
            f"Processed {len(all_docs)} documents "
            f"with {len(all_chunks)} total chunks"
        )
        return all_docs, all_chunks
