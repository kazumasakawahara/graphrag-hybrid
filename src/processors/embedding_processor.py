"""
Embedding processor for converting text to vector embeddings.

日本語対応版: intfloat/multilingual-e5-base を使用。
E5モデルはクエリに "query: "、文書に "passage: " プレフィックスが必要。
"""

import logging
from typing import List

import numpy as np

try:
    import torch
    from transformers import AutoModel, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


def _is_e5_model(model_name: str) -> bool:
    """E5系モデルかどうかを判定"""
    return 'e5' in model_name.lower()


class EmbeddingProcessor:
    """Process text into vector embeddings using a transformer model.

    日本語対応: E5モデル使用時は自動的にプレフィックスを付与。
    """

    def __init__(self, config):
        """Initialize with configuration"""
        self.config = config
        self.model_name = config.get(
            'embedding.model_name',
            'intfloat/multilingual-e5-base'
        )
        self.vector_size = config.get('embedding.vector_size', 768)
        self.device = config.get('embedding.device', 'cpu')
        self.max_length = config.get('embedding.max_length', 512)
        self.tokenizer = None
        self.model = None

        # E5モデルはプレフィックスが必要
        self.is_e5 = _is_e5_model(self.model_name)
        if self.is_e5:
            logger.info(
                f"E5モデル検出: {self.model_name} — "
                "クエリに 'query: '、文書に 'passage: ' プレフィックスを自動付与します"
            )

        # Validate transformers availability
        if not TRANSFORMERS_AVAILABLE:
            logger.error(
                "Transformers package not available. "
                "Please install with: pip install transformers torch"
            )
            raise ImportError("Required package 'transformers' is not installed")

    def load_model(self):
        """Load the embedding model and tokenizer"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")

            # デバイス選択（M4 Mac では MPS が利用可能な場合あり）
            if self.device == 'cuda' and torch.cuda.is_available():
                logger.info("Using CUDA for embeddings")
                device = torch.device('cuda')
            elif self.device == 'mps' and torch.backends.mps.is_available():
                logger.info("Using MPS (Apple Silicon) for embeddings")
                device = torch.device('mps')
            else:
                if self.device in ('cuda', 'mps'):
                    logger.warning(
                        f"{self.device.upper()} requested but not available, "
                        "falling back to CPU"
                    )
                device = torch.device('cpu')

            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)

            # Move model to appropriate device
            self.model.to(device)

            # Set model to evaluation mode
            self.model.eval()

            logger.info(
                f"Successfully loaded embedding model "
                f"(vector size: {self.vector_size}, device: {device})"
            )
            return True
        except Exception as e:
            logger.error(f"Error loading embedding model: {str(e)}")
            raise

    def _add_prefix(self, text: str, prefix_type: str = "passage") -> str:
        """E5モデル用プレフィックスを付与。

        Args:
            text: 入力テキスト
            prefix_type: "query" (検索クエリ) または "passage" (文書チャンク)
        """
        if not self.is_e5:
            return text

        if prefix_type == "query":
            return f"query: {text}"
        else:
            return f"passage: {text}"

    def get_embedding(
        self, text: str, prefix_type: str = "passage"
    ) -> List[float]:
        """Generate embedding for a text string.

        Args:
            text: 入力テキスト
            prefix_type: "query" (検索時) or "passage" (文書登録時)
        """
        if not self.model or not self.tokenizer:
            self.load_model()

        try:
            # Handle empty or None input
            if not text:
                logger.warning("Empty text provided for embedding, returning zero vector")
                return [0.0] * self.vector_size

            # Truncate text if necessary
            if len(text) > 10000:
                logger.warning(
                    f"Text too long ({len(text)} chars), truncating to 10000 chars"
                )
                text = text[:10000]

            # E5モデル用プレフィックス付与
            text = self._add_prefix(text, prefix_type)

            # Tokenize and prepare for model
            inputs = self.tokenizer(
                text,
                max_length=self.max_length,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )

            # Move inputs to same device as model
            inputs = {key: val.to(self.model.device) for key, val in inputs.items()}

            # Generate embeddings without gradient calculation
            with torch.no_grad():
                outputs = self.model(**inputs)

            # Mean pooling with attention mask
            embeddings = outputs.last_hidden_state

            if 'attention_mask' not in inputs:
                attention_mask = torch.ones_like(inputs['input_ids'])
            else:
                attention_mask = inputs['attention_mask']

            mask = attention_mask.unsqueeze(-1).expand(embeddings.size()).float()
            masked_embeddings = embeddings * mask
            summed = torch.sum(masked_embeddings, dim=1)
            counts = torch.sum(mask, dim=1)
            mean_pooled = summed / counts

            # L2 normalize (E5の推奨)
            if self.is_e5:
                mean_pooled = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)

            # Convert to list of floats
            embedding = mean_pooled[0].cpu().numpy().tolist()

            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return [0.0] * self.vector_size

    def get_query_embedding(self, text: str) -> List[float]:
        """検索クエリ用のembeddingを生成（E5: "query: " プレフィックス付与）"""
        return self.get_embedding(text, prefix_type="query")

    def get_passage_embedding(self, text: str) -> List[float]:
        """文書チャンク用のembeddingを生成（E5: "passage: " プレフィックス付与）"""
        return self.get_embedding(text, prefix_type="passage")

    def get_batch_embeddings(
        self, texts: List[str], batch_size: int = 8, prefix_type: str = "passage"
    ) -> List[List[float]]:
        """Generate embeddings for a batch of texts"""
        if not self.model or not self.tokenizer:
            self.load_model()

        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            try:
                # E5プレフィックス付与
                prefixed_batch = [self._add_prefix(t, prefix_type) for t in batch]

                # Tokenize the batch
                encoded_batch = self.tokenizer(
                    prefixed_batch,
                    max_length=self.max_length,
                    padding='max_length',
                    truncation=True,
                    return_tensors='pt'
                )

                # Move batch to model device
                encoded_batch = {
                    k: v.to(self.model.device) for k, v in encoded_batch.items()
                }

                # Generate embeddings
                with torch.no_grad():
                    outputs = self.model(**encoded_batch)

                # Mean pooling
                embeddings = outputs.last_hidden_state
                attention_mask = encoded_batch['attention_mask']
                mask = attention_mask.unsqueeze(-1).expand(embeddings.size()).float()
                masked_embeddings = embeddings * mask
                summed = torch.sum(masked_embeddings, dim=1)
                counts = torch.sum(mask, dim=1)
                mean_pooled = summed / counts

                # L2 normalize for E5
                if self.is_e5:
                    mean_pooled = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)

                batch_embeddings = mean_pooled.cpu().numpy().tolist()
                results.extend(batch_embeddings)

                logger.debug(f"Processed batch of {len(batch)} embeddings")
            except Exception as e:
                logger.error(f"Error processing embedding batch: {str(e)}")
                for _ in batch:
                    results.append([0.0] * self.vector_size)

        return results

    def unload_model(self):
        """Unload model to free memory"""
        if self.model:
            del self.model
            self.model = None
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None

        try:
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Embedding model unloaded and memory freed")
        except Exception:
            logger.warning("Failed to fully clear memory resources")

    def vector_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if len(vec1) != len(vec2):
            raise ValueError(
                f"Vector dimensions do not match: {len(vec1)} vs {len(vec2)}"
            )

        try:
            vec1_array = np.array(vec1)
            vec2_array = np.array(vec2)

            dot_product = np.dot(vec1_array, vec2_array)
            magnitude1 = np.linalg.norm(vec1_array)
            magnitude2 = np.linalg.norm(vec2_array)

            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0

            similarity = dot_product / (magnitude1 * magnitude2)
            return float(similarity)
        except Exception as e:
            logger.error(f"Error calculating vector similarity: {str(e)}")
            return 0.0
