"""
GraphRAG Hybrid - Document Upload & Management UI
Streamlit application for uploading PDF/Markdown documents into the GraphRAG system.
"""

import os
import sys
import uuid as _uuid
import logging

import streamlit as st

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.database.neo4j_manager import Neo4jManager
from src.database.qdrant_manager import QdrantManager
from src.processors.document_processor import DocumentProcessor
from src.processors.embedding_processor import EmbeddingProcessor
from src.processors.pdf_processor import PDFProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Page config ---
st.set_page_config(
    page_title="GraphRAG - Document Manager",
    page_icon="📄",
    layout="wide",
)

st.title("GraphRAG Document Manager")


# --- Lazy initialization helpers ---
def _get_config():
    if "config" not in st.session_state:
        st.session_state.config = Config()
    return st.session_state.config


def _get_doc_processor():
    if "doc_processor" not in st.session_state:
        st.session_state.doc_processor = DocumentProcessor(_get_config())
    return st.session_state.doc_processor


def _get_pdf_processor():
    if "pdf_processor" not in st.session_state:
        st.session_state.pdf_processor = PDFProcessor()
    return st.session_state.pdf_processor


def _connect_databases():
    """Connect to Neo4j and Qdrant. Returns (neo4j, qdrant, error_message)."""
    if "neo4j" in st.session_state and "qdrant" in st.session_state:
        return st.session_state.neo4j, st.session_state.qdrant, None

    config = _get_config()
    errors = []

    # Neo4j
    try:
        neo4j = Neo4jManager(config)
        neo4j.connect()
        st.session_state.neo4j = neo4j
    except Exception as e:
        errors.append(f"Neo4j: {e}")

    # Embedding + Qdrant
    try:
        if "embedding" not in st.session_state:
            emb = EmbeddingProcessor(config)
            emb.load_model()
            st.session_state.embedding = emb

        qdrant = QdrantManager(config, st.session_state.embedding)
        qdrant.connect()
        st.session_state.qdrant = qdrant
    except Exception as e:
        errors.append(f"Qdrant: {e}")

    if errors:
        return (
            st.session_state.get("neo4j"),
            st.session_state.get("qdrant"),
            "\n".join(errors),
        )
    return st.session_state.neo4j, st.session_state.qdrant, None


# --- Sidebar ---
def show_connection_status():
    """Display database connection status in sidebar."""
    st.sidebar.header("System Status")

    neo4j, qdrant, err = _connect_databases()

    if err:
        st.sidebar.error(err)

    # Neo4j status
    if neo4j and neo4j.driver:
        try:
            with neo4j.driver.session(database=neo4j.database) as session:
                result = session.run("MATCH (d:Document) RETURN count(d) AS cnt")
                doc_count = result.single()["cnt"]
            st.sidebar.success(f"Neo4j: {doc_count} documents")
        except Exception as e:
            st.sidebar.error(f"Neo4j query error: {e}")
    else:
        st.sidebar.warning("Neo4j: not connected")

    # Qdrant status
    if qdrant and qdrant.client:
        try:
            config = _get_config()
            collection_name = config.get("qdrant.collection", "document_chunks")
            info = qdrant.client.get_collection(collection_name)
            vec_count = getattr(info, "vectors_count", getattr(info, "points_count", "?"))
            st.sidebar.success(f"Qdrant: {vec_count} vectors")
        except Exception:
            st.sidebar.warning("Qdrant: collection not found")
    else:
        st.sidebar.warning("Qdrant: not connected")

    if st.sidebar.button("Reconnect"):
        for key in ["neo4j", "qdrant", "embedding"]:
            st.session_state.pop(key, None)
        st.rerun()


# --- Upload tab ---
def upload_tab():
    """Document upload tab."""
    st.header("Upload Documents")

    uploaded_files = st.file_uploader(
        "PDF or Markdown files",
        type=["pdf", "md", "markdown"],
        accept_multiple_files=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        category = st.text_input("Category", value="imported")
    with col2:
        custom_title = st.text_input("Title (blank = auto-detect)", value="")

    if not uploaded_files:
        st.info("Upload files to get started.")
        return

    if not st.button("Ingest Documents", type="primary"):
        return

    neo4j, qdrant, err = _connect_databases()
    if err:
        st.error(f"Database connection failed:\n{err}")
        return

    doc_processor = _get_doc_processor()
    pdf_processor = _get_pdf_processor()

    progress = st.progress(0, text="Starting...")
    total = len(uploaded_files)

    success_count = 0
    for idx, uploaded_file in enumerate(uploaded_files):
        file_label = uploaded_file.name
        progress.progress(idx / total, text=f"Processing {file_label} ({idx + 1}/{total})...")

        try:
            # --- Convert to Markdown text ---
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext == ".pdf":
                md_text = pdf_processor.convert_uploaded_file(uploaded_file)
            else:
                md_text = uploaded_file.read().decode("utf-8")

            # --- Determine title ---
            title = custom_title
            if not title:
                for line in md_text.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        title = stripped[2:].strip()
                        break
            if not title:
                title = (
                    os.path.splitext(uploaded_file.name)[0]
                    .replace("_", " ")
                    .replace("-", " ")
                    .title()
                )

            # --- Build metadata ---
            doc_id = f"doc_{_uuid.uuid4().hex[:8]}"
            metadata = {
                "id": doc_id,
                "title": title,
                "category": category,
                "path": uploaded_file.name,
            }

            # --- Chunk text ---
            chunks_text = doc_processor._chunk_text(md_text)
            chunk_objects = [
                {
                    "id": str(_uuid.uuid4()),
                    "text": chunk_text,
                    "doc_id": doc_id,
                    "position": pos,
                    "metadata": metadata,
                }
                for pos, chunk_text in enumerate(chunks_text)
            ]

            if not chunk_objects:
                st.warning(f"{file_label}: no chunks generated, skipping.")
                continue

            # --- Store in Neo4j ---
            neo4j.import_documents([metadata], chunk_objects)

            # --- Store in Qdrant ---
            qdrant.import_chunks(chunk_objects)

            success_count += 1
            st.success(f"{file_label}: {len(chunk_objects)} chunks ingested (title: {title})")

        except Exception as e:
            st.error(f"{file_label}: {e}")
            logger.exception(f"Error processing {file_label}")

    progress.progress(1.0, text="Done!")
    if success_count == total:
        st.balloons()


# --- Browse tab ---
def browse_tab():
    """Browse existing documents tab."""
    st.header("Registered Documents")

    neo4j, _, err = _connect_databases()
    if not neo4j or not neo4j.driver:
        st.warning("Neo4j is not connected. Check sidebar for details.")
        return

    try:
        with neo4j.driver.session(database=neo4j.database) as session:
            result = session.run("""
                MATCH (d:Document)
                OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                RETURN d.id AS id, d.title AS title, d.category AS category,
                       count(c) AS chunks
                ORDER BY d.title
            """)
            docs = [dict(r) for r in result]

        if not docs:
            st.info("No documents registered yet.")
            return

        st.write(f"Total: {len(docs)} documents")

        table_data = [
            {
                "ID": doc["id"],
                "Title": doc["title"] or "(no title)",
                "Category": doc["category"] or "-",
                "Chunks": doc["chunks"],
            }
            for doc in docs
        ]
        st.dataframe(table_data, use_container_width=True)

        # Delete section
        st.subheader("Delete Document")
        doc_ids = [d["id"] for d in docs]
        doc_labels = [f'{d["title"]} ({d["id"]})' for d in docs]
        selected = st.selectbox("Select document to delete", doc_labels)

        if selected and st.button("Delete", type="secondary"):
            selected_id = doc_ids[doc_labels.index(selected)]
            with neo4j.driver.session(database=neo4j.database) as session:
                session.run(
                    "MATCH (d:Document {id: $id})-[:HAS_CHUNK]->(c:Chunk) DETACH DELETE c",
                    {"id": selected_id},
                )
                session.run(
                    "MATCH (d:Document {id: $id}) DETACH DELETE d",
                    {"id": selected_id},
                )
            st.success(f"Deleted: {selected}")
            st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")


# --- Main layout ---
show_connection_status()

tab_upload, tab_browse = st.tabs(["Upload", "Browse"])

with tab_upload:
    upload_tab()

with tab_browse:
    browse_tab()
