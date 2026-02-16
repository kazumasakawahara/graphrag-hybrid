"""
Query engine for hybrid Neo4j and Qdrant search
"""

import logging
from typing import List, Dict, Any, Optional, Union
import uuid

logger = logging.getLogger(__name__)

class QueryEngine:
    """Hybrid query engine for Neo4j and Qdrant databases"""
    
    def __init__(self, neo4j_manager, qdrant_manager, embedding_processor=None):
        """Initialize with database managers"""
        self.neo4j = neo4j_manager
        self.qdrant = qdrant_manager
        self.embedding_processor = embedding_processor
        
        # Verify connections
        self._verify_connections()
    
    def _verify_connections(self):
        """Verify database connections"""
        if not self.neo4j.driver:
            logger.warning("Neo4j connection not established, attempting to connect")
            self.neo4j.connect()
            
        if not self.qdrant.client:
            logger.warning("Qdrant connection not established, attempting to connect")
            self.qdrant.connect()
    
    def semantic_search(self, query: str, limit: int = 5, category: Optional[str] = None) -> List[Dict[Any, Any]]:
        """Perform semantic search using Qdrant"""
        logger.info(f"Semantic search: '{query}' (limit: {limit}, category: {category})")
        
        # Set up filter if category is provided
        filter_conditions = None
        if category:
            filter_conditions = {'category': category}
            
        # Perform vector search
        try:
            if not self.embedding_processor:
                logger.error("No embedding processor available for semantic search")
                return []
                
            # Use Qdrant for vector search
            search_results = self.qdrant.search(
                query_text=query,
                limit=limit,
                filter_conditions=filter_conditions
            )
            
            # Enhance results with document information
            enhanced_results = []
            for result in search_results:
                # Get document information from Neo4j
                doc_info = self.neo4j.get_document_by_id(result.get('doc_id'))
                if doc_info:
                    result['document'] = doc_info
                    
                # Get chunk context if needed
                chunk_context = self.neo4j.get_chunk_context(result['id'], context_size=1)
                if chunk_context:
                    result['context'] = {
                        'previous': [c.get('text', '') for c in chunk_context.get('previous', [])],
                        'next': [c.get('text', '') for c in chunk_context.get('next', [])]
                    }
                
                enhanced_results.append(result)
            
            return enhanced_results
        except Exception as e:
            logger.error(f"Error in semantic search: {str(e)}")
            return []
    
    def category_search(self, category: str, limit: int = 10) -> List[Dict[Any, Any]]:
        """Search for documents by category using Neo4j"""
        logger.info(f"Category search: '{category}' (limit: {limit})")
        
        try:
            # Use Neo4j for category search
            results = self.neo4j.search_by_category(category, limit)
            return results
        except Exception as e:
            logger.error(f"Error in category search: {str(e)}")
            return []
    
    def get_document_with_chunks(self, doc_id: str) -> Dict[Any, Any]:
        """Get document with all its chunks"""
        logger.info(f"Getting document with chunks: {doc_id}")
        
        try:
            # Get document from Neo4j
            document = self.neo4j.get_document_by_id(doc_id)
            if not document:
                logger.warning(f"Document not found: {doc_id}")
                return {}
            
            # Get chunks from Neo4j
            chunks = self.neo4j.get_document_chunks(doc_id)
            document['chunks'] = chunks
            
            return document
        except Exception as e:
            logger.error(f"Error getting document with chunks: {str(e)}")
            return {}
    
    def hybrid_search(self, query: str, limit: int = 5, category: Optional[str] = None,
                       semantic_weight: float = 0.6, graph_weight: float = 0.2,
                       entity_weight: float = 0.2) -> List[Dict[Any, Any]]:
        """
        Perform hybrid search combining semantic, graph-based, and entity-based search.

        Scoring: semantic (60%) + graph (20%) + entity (20%)

        Args:
            query: Search query text
            limit: Maximum number of results
            category: Optional category filter
            semantic_weight: Weight for semantic (vector) search
            graph_weight: Weight for graph-based (category relation) search
            entity_weight: Weight for entity-based search

        Returns:
            List of search results with scores
        """
        logger.info(f"Hybrid search: '{query}' (limit: {limit}, category: {category})")

        try:
            # Step 1: Perform semantic search with higher limit
            semantic_limit = limit * 3
            semantic_results = self.semantic_search(query, semantic_limit, category)

            if not semantic_results:
                logger.warning("No semantic search results found")
                return []

            # Step 2: Build result map from semantic results
            result_map = {}

            for sem_result in semantic_results:
                doc_id = sem_result.get('doc_id')
                if doc_id:
                    result_map[sem_result['id']] = {
                        'id': sem_result['id'],
                        'doc_id': doc_id,
                        'text': sem_result['text'],
                        'semantic_score': sem_result['score'],
                        'graph_score': 0.0,
                        'entity_score': 0.0,
                        'final_score': 0.0,
                        'document': sem_result.get('document', {}),
                        'context': sem_result.get('context', {}),
                        'entities': [],
                    }

                    # Get related documents (graph connections)
                    related_docs = self.neo4j.get_related_documents(doc_id, limit=3)
                    for rel_doc in related_docs:
                        rel_doc_id = rel_doc.get('id')
                        if rel_doc_id:
                            rel_chunks = self.neo4j.get_document_chunks(rel_doc_id)
                            if rel_chunks:
                                rel_chunk = rel_chunks[0]
                                rel_chunk_id = rel_chunk.get('id')
                                if rel_chunk_id not in result_map:
                                    result_map[rel_chunk_id] = {
                                        'id': rel_chunk_id,
                                        'doc_id': rel_doc_id,
                                        'text': rel_chunk.get('text', ''),
                                        'semantic_score': 0.0,
                                        'graph_score': 0.5,
                                        'entity_score': 0.0,
                                        'final_score': 0.0,
                                        'document': rel_doc,
                                        'context': {},
                                        'entities': [],
                                    }

            # Step 3: Entity-based scoring
            entity_results = self.neo4j.search_by_entity(query, limit=limit)
            entity_chunk_ids = set()
            for ent_result in entity_results:
                for mention in ent_result.get("mentions", []):
                    chunk_id = mention.get("chunk_id")
                    if chunk_id:
                        entity_chunk_ids.add(chunk_id)
                        if chunk_id in result_map:
                            result_map[chunk_id]['entity_score'] = 1.0
                            result_map[chunk_id]['entities'].append(ent_result.get("entity_name", ""))
                        else:
                            result_map[chunk_id] = {
                                'id': chunk_id,
                                'doc_id': mention.get('doc_id', ''),
                                'text': mention.get('text', ''),
                                'semantic_score': 0.0,
                                'graph_score': 0.0,
                                'entity_score': 1.0,
                                'final_score': 0.0,
                                'document': {'id': mention.get('doc_id', ''), 'title': mention.get('doc_title', '')},
                                'context': {},
                                'entities': [ent_result.get("entity_name", "")],
                            }

            # Step 4: Calculate final scores
            for result in result_map.values():
                result['final_score'] = (
                    result['semantic_score'] * semantic_weight
                    + result['graph_score'] * graph_weight
                    + result['entity_score'] * entity_weight
                )

            # Step 5: Sort and return
            results = list(result_map.values())
            results.sort(key=lambda x: x['final_score'], reverse=True)

            return results[:limit]
        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            return []

    def entity_search(self, query: str, limit: int = 10) -> List[Dict[Any, Any]]:
        """Search for entities and their associated chunks."""
        logger.info(f"Entity search: '{query}' (limit: {limit})")
        try:
            return self.neo4j.search_by_entity(query, limit)
        except Exception as e:
            logger.error(f"Error in entity search: {str(e)}")
            return []

    def get_entity_graph(self, entity_name: str) -> Dict[Any, Any]:
        """Get an entity's relationship graph."""
        logger.info(f"Getting entity graph for: '{entity_name}'")
        try:
            result = self.neo4j.get_entity_graph(entity_name)
            return result or {}
        except Exception as e:
            logger.error(f"Error getting entity graph: {str(e)}")
            return {}
    
    def expand_context(self, chunk_id: str, context_size: int = 2) -> Dict[Any, Any]:
        """Expand context around a specific chunk"""
        logger.info(f"Expanding context for chunk: {chunk_id} (size: {context_size})")
        
        try:
            # Get chunk context from Neo4j
            context = self.neo4j.get_chunk_context(chunk_id, context_size)
            if not context:
                logger.warning(f"No context found for chunk: {chunk_id}")
                return {}
            
            # Get document info
            doc_id = None
            if context.get('center'):
                chunk = context['center']
                doc_id = self.neo4j.get_document_by_chunk_id(chunk_id)
                if doc_id:
                    doc_info = self.neo4j.get_document_by_id(doc_id)
                    if doc_info:
                        context['document'] = doc_info
            
            return context
        except Exception as e:
            logger.error(f"Error expanding context: {str(e)}")
            return {}
    
    def suggest_related(self, doc_id: str, limit: int = 5) -> List[Dict[Any, Any]]:
        """Suggest related documents based on category and graph connections"""
        logger.info(f"Suggesting related documents for: {doc_id} (limit: {limit})")
        
        try:
            # Get related documents from Neo4j
            related = self.neo4j.get_related_documents(doc_id, limit)
            return related
        except Exception as e:
            logger.error(f"Error suggesting related documents: {str(e)}")
            return []
    
    def get_all_categories(self) -> List[str]:
        """Get all available document categories"""
        logger.info("Getting all document categories")
        
        try:
            return self.neo4j.get_all_categories()
        except Exception as e:
            logger.error(f"Error getting categories: {str(e)}")
            return []
    
    def get_statistics(self) -> Dict[Any, Any]:
        """Get statistics from both databases"""
        logger.info("Getting database statistics")
        
        try:
            neo4j_stats = self.neo4j.get_statistics()
            qdrant_stats = self.qdrant.get_statistics()
            
            return {
                'neo4j': neo4j_stats,
                'qdrant': qdrant_stats
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {} 