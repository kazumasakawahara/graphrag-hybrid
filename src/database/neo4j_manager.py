"""
Neo4j database manager for GraphRAG
"""

import logging
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)

class Neo4jManager:
    """Manager for Neo4j document graph operations"""
    
    def __init__(self, config):
        """Initialize Neo4j manager with configuration"""
        self.config = config
        self.uri = config.get('neo4j.uri', 'bolt://localhost:7687')
        self.username = config.get('neo4j.username', 'neo4j')
        self.password = config.get('neo4j.password', 'password')
        self.database = config.get('neo4j.database', 'neo4j')
        self.driver = None
        
    def connect(self):
        """Connect to Neo4j database"""
        try:
            logger.info(f"Connecting to Neo4j at {self.uri}")
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
            # Test connection
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS test")
                test_value = result.single()["test"]
                if test_value != 1:
                    raise Exception("Connection test failed")
            logger.info("Successfully connected to Neo4j")
            return True
        except AuthError as e:
            logger.error(f"Neo4j authentication error: {str(e)}")
            raise
        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise
            
    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
            
    def setup_schema(self):
        """Set up the document graph schema with constraints"""
        logger.info("Setting up Neo4j schema with constraints")
        
        # Queries to create constraints
        constraints = [
            # Document uniqueness constraint
            """
            CREATE CONSTRAINT document_id IF NOT EXISTS
            FOR (d:Document) REQUIRE d.id IS UNIQUE
            """,
            # Chunk uniqueness constraint
            """
            CREATE CONSTRAINT chunk_id IF NOT EXISTS
            FOR (c:Chunk) REQUIRE c.id IS UNIQUE
            """,
            # Entity uniqueness constraint (name is the unique key)
            """
            CREATE CONSTRAINT entity_name IF NOT EXISTS
            FOR (e:Entity) REQUIRE e.name IS UNIQUE
            """,
        ]
        
        try:
            with self.driver.session(database=self.database) as session:
                for constraint in constraints:
                    session.run(constraint)
                logger.info("Neo4j schema constraints created successfully")
            return True
        except Exception as e:
            logger.error(f"Error setting up Neo4j schema: {str(e)}")
            raise
            
    def clear_database(self):
        """Clear all nodes and relationships from the database"""
        logger.warning("Clearing all data from Neo4j database")
        
        try:
            with self.driver.session(database=self.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info("Neo4j database cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing Neo4j database: {str(e)}")
            raise
            
    def import_documents(self, documents, chunks):
        """Import documents and chunks into Neo4j"""
        logger.info(f"Importing {len(documents)} documents with {len(chunks)} chunks to Neo4j")
        
        # Batch processing parameters
        doc_batch_size = 50
        chunk_batch_size = 200
        
        try:
            with self.driver.session(database=self.database) as session:
                # Import documents in batches
                for i in range(0, len(documents), doc_batch_size):
                    batch = documents[i:i+doc_batch_size]
                    self._create_documents_batch(session, batch)
                    logger.debug(f"Imported document batch {i//doc_batch_size + 1}")
                
                # Import chunks in batches
                for i in range(0, len(chunks), chunk_batch_size):
                    batch = chunks[i:i+chunk_batch_size]
                    self._create_chunks_batch(session, batch)
                    logger.debug(f"Imported chunk batch {i//chunk_batch_size + 1}")
                
                # Create relationships between documents based on shared category
                session.run("""
                MATCH (d1:Document), (d2:Document)
                WHERE d1.category = d2.category AND d1.id <> d2.id
                MERGE (d1)-[:RELATED_TO]->(d2)
                """)
            logger.info("Documents and chunks successfully imported to Neo4j")
            return True
        except Exception as e:
            logger.error(f"Error importing documents to Neo4j: {str(e)}")
            raise
            
    def _create_documents_batch(self, session, documents):
        """Create document nodes in batch"""
        # Prepare parameters for batch creation
        params = {'documents': []}
        
        for doc in documents:
            # Prepare document properties
            doc_data = {
                'id': doc['id'],
                'title': doc.get('title', ''),
                'category': doc.get('category', ''),
                'path': doc.get('path', '')
            }
            
            # Add optional properties if they exist
            for key in ['author', 'date', 'tags', 'description']:
                if key in doc:
                    doc_data[key] = doc[key]
                    
            params['documents'].append(doc_data)
        
        # Execute batch creation
        session.run("""
        UNWIND $documents AS doc
        MERGE (d:Document {id: doc.id})
        SET d += doc
        """, params)
        
    def _create_chunks_batch(self, session, chunks):
        """Create chunk nodes and relationships in batch"""
        # Prepare parameters for batch creation
        params = {'chunks': []}
        
        for chunk in chunks:
            # Prepare chunk properties
            chunk_data = {
                'id': chunk['id'],
                'text': chunk['text'],
                'doc_id': chunk['doc_id'],
                'position': chunk['position']
            }
            
            params['chunks'].append(chunk_data)
        
        # Execute batch creation with relationships
        session.run("""                    
        UNWIND $chunks AS chunk
        MERGE (c:Chunk {id: chunk.id})
        SET c.text = chunk.text,
            c.position = chunk.position,
            c.doc_id = chunk.doc_id
        WITH c, chunk
        MERGE (d:Document {id: chunk.doc_id})
        MERGE (d)-[:HAS_CHUNK]->(c)
        WITH c, chunk
        MATCH (prev:Chunk {doc_id: chunk.doc_id, position: chunk.position - 1})
        MERGE (prev)-[:NEXT]->(c)
        """, params)
    def get_document_by_id(self, doc_id):
        """Get a document by ID"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document {id: $id})
                RETURN d
                """, {'id': doc_id})
                
                record = result.single()
                if record:
                    return dict(record['d'])
                return None
        except Exception as e:
            logger.error(f"Error getting document by ID: {str(e)}")
            return None
            
    def get_document_chunks(self, doc_id):
        """Get all chunks for a document ordered by position"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document {id: $id})-[:HAS_CHUNK]->(c:Chunk)
                RETURN c
                ORDER BY c.position
                """, {'id': doc_id})
                
                return [dict(record['c']) for record in result]
        except Exception as e:
            logger.error(f"Error getting document chunks: {str(e)}")
            return []
            
    def get_related_documents(self, doc_id, limit=5):
        """Get related documents by category relationship"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document {id: $id})-[:RELATED_TO]->(related:Document)
                RETURN related
                LIMIT $limit
                """, {'id': doc_id, 'limit': limit})
                
                return [dict(record['related']) for record in result]
        except Exception as e:
            logger.error(f"Error getting related documents: {str(e)}")
            return []
            
    def get_document_by_chunk_id(self, chunk_id):
        """Get the parent document of a chunk"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk {id: $id})
                RETURN d
                """, {'id': chunk_id})
                
                record = result.single()
                if record:
                    return dict(record['d'])
                return None
        except Exception as e:
            logger.error(f"Error getting document by chunk ID: {str(e)}")
            return None
            
    def get_chunk_context(self, chunk_id, context_size=1):
        """Get surrounding chunks for context"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (c:Chunk {id: $id})
                OPTIONAL MATCH (c)<-[:NEXT*1..2]-(prev:Chunk)
                OPTIONAL MATCH (c)-[:NEXT*1..2]->(next:Chunk)
                WITH c, collect(prev) as prevs, collect(next) as nexts
                RETURN c as center, prevs, nexts
                """, {'id': chunk_id, 'context_size': context_size})
                record = result.single()
                if record:
                    return {
                        'center': dict(record['center']),
                        'previous': [dict(chunk) for chunk in record['prevs']],
                        'next': [dict(chunk) for chunk in record['nexts']]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting chunk context: {str(e)}")
            return None
            
    def search_by_category(self, category, limit=10):
        """Search for documents by category"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document)
                WHERE d.category = $category
                RETURN d
                LIMIT $limit
                """, {'category': category, 'limit': limit})
                
                return [dict(record['d']) for record in result]
        except Exception as e:
            logger.error(f"Error searching by category: {str(e)}")
            return []
            
    def get_all_categories(self):
        """Get all document categories"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document)
                RETURN DISTINCT d.category AS category
                """)
                
                return [record['category'] for record in result]
        except Exception as e:
            logger.error(f"Error getting all categories: {str(e)}")
            return []
            
    def import_entities(self, extraction_result):
        """Import extracted entities and relationships into Neo4j.

        Args:
            extraction_result: Dict with 'entities', 'relations', 'chunk_entity_map' keys.
        """
        entities = extraction_result.get("entities", [])
        relations = extraction_result.get("relations", [])
        chunk_entity_map = extraction_result.get("chunk_entity_map", [])

        if not entities:
            return

        logger.info(
            f"Importing {len(entities)} entities, {len(relations)} relations, "
            f"{len(chunk_entity_map)} chunk-entity links to Neo4j"
        )

        try:
            with self.driver.session(database=self.database) as session:
                # 1. Create Entity nodes
                session.run("""
                UNWIND $entities AS ent
                MERGE (e:Entity {name: ent.name})
                SET e.type = ent.type,
                    e.description = ent.description
                """, {"entities": entities})

                # 2. Create MENTIONS relationships (Chunk -> Entity)
                session.run("""
                UNWIND $mappings AS m
                MATCH (c:Chunk {id: m.chunk_id})
                MATCH (e:Entity {name: m.entity_name})
                MERGE (c)-[:MENTIONS]->(e)
                """, {"mappings": chunk_entity_map})

                # 3. Create APPEARS_IN relationships (Entity -> Document)
                session.run("""
                UNWIND $mappings AS m
                MATCH (e:Entity {name: m.entity_name})
                MATCH (d:Document {id: m.doc_id})
                MERGE (e)-[:APPEARS_IN]->(d)
                """, {"mappings": chunk_entity_map})

                # 4. Create RELATES_TO relationships (Entity -> Entity)
                if relations:
                    session.run("""
                    UNWIND $relations AS rel
                    MATCH (src:Entity {name: rel.source})
                    MATCH (tgt:Entity {name: rel.target})
                    MERGE (src)-[r:RELATES_TO {type: rel.relation}]->(tgt)
                    """, {"relations": relations})

            logger.info("Entities imported successfully")
        except Exception as e:
            logger.error(f"Error importing entities: {str(e)}")
            raise

    def search_by_entity(self, entity_name, limit=10):
        """Search for chunks and documents that mention an entity."""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($name)
                OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(e)
                OPTIONAL MATCH (d:Document)-[:HAS_CHUNK]->(c)
                RETURN e.name AS entity_name, e.type AS entity_type,
                       e.description AS entity_description,
                       collect(DISTINCT {
                           chunk_id: c.id,
                           text: c.text,
                           doc_id: d.id,
                           doc_title: d.title
                       })[0..$limit] AS mentions
                LIMIT $limit
                """, {"name": entity_name, "limit": limit})

                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Error searching by entity: {str(e)}")
            return []

    def get_entity_graph(self, entity_name, depth=1):
        """Get an entity and its related entities."""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (e:Entity)
                WHERE toLower(e.name) = toLower($name)
                OPTIONAL MATCH (e)-[r:RELATES_TO]-(related:Entity)
                OPTIONAL MATCH (e)-[:APPEARS_IN]->(d:Document)
                RETURN e.name AS name, e.type AS type, e.description AS description,
                       collect(DISTINCT {
                           name: related.name,
                           type: related.type,
                           relation: r.type
                       }) AS related_entities,
                       collect(DISTINCT {
                           id: d.id,
                           title: d.title
                       }) AS documents
                """, {"name": entity_name})

                record = result.single()
                if record:
                    return dict(record)
                return None
        except Exception as e:
            logger.error(f"Error getting entity graph: {str(e)}")
            return None

    def get_all_entities(self, entity_type=None, limit=100):
        """Get all entities, optionally filtered by type."""
        try:
            with self.driver.session(database=self.database) as session:
                if entity_type:
                    result = session.run("""
                    MATCH (e:Entity {type: $type})
                    RETURN e.name AS name, e.type AS type, e.description AS description
                    ORDER BY e.name
                    LIMIT $limit
                    """, {"type": entity_type, "limit": limit})
                else:
                    result = session.run("""
                    MATCH (e:Entity)
                    RETURN e.name AS name, e.type AS type, e.description AS description
                    ORDER BY e.name
                    LIMIT $limit
                    """, {"limit": limit})

                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Error getting all entities: {str(e)}")
            return []

    def get_chunks_by_entity(self, entity_name, limit=10):
        """Get chunks that mention a specific entity."""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
                WHERE toLower(e.name) = toLower($name)
                MATCH (d:Document)-[:HAS_CHUNK]->(c)
                RETURN c.id AS chunk_id, c.text AS text, c.doc_id AS doc_id,
                       d.title AS doc_title
                ORDER BY c.position
                LIMIT $limit
                """, {"name": entity_name, "limit": limit})

                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Error getting chunks by entity: {str(e)}")
            return []

    def get_statistics(self):
        """Get database statistics"""
        try:
            with self.driver.session(database=self.database) as session:
                doc_count = session.run("MATCH (d:Document) RETURN count(d) AS count").single()['count']
                chunk_count = session.run("MATCH (c:Chunk) RETURN count(c) AS count").single()['count']
                category_count = session.run("MATCH (d:Document) RETURN count(DISTINCT d.category) AS count").single()['count']
                entity_count = session.run("MATCH (e:Entity) RETURN count(e) AS count").single()['count']
                relation_count = session.run("MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS count").single()['count']

                return {
                    'document_count': doc_count,
                    'chunk_count': chunk_count,
                    'category_count': category_count,
                    'entity_count': entity_count,
                    'relation_count': relation_count,
                }
        except Exception as e:
            logger.error(f"Error getting database statistics: {str(e)}")
            return {}