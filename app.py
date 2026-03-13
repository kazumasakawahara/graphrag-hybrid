"""
GraphRAG Hybrid - ドキュメントアップロード・管理 UI
PDF/Markdown ドキュメントを GraphRAG システムに取り込む Streamlit アプリケーション
"""

import logging
import os
import sys
import uuid as _uuid

import streamlit as st

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.database.neo4j_manager import Neo4jManager
from src.database.qdrant_manager import QdrantManager
from src.processors.document_processor import DocumentProcessor
from src.processors.embedding_processor import EmbeddingProcessor
from src.processors.entity_extractor import EntityExtractor
from src.processors.pdf_processor import PDFProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ページ設定 ---
st.set_page_config(
    page_title="GraphRAG - ドキュメント管理",
    page_icon="📄",
    layout="wide",
)

st.title("GraphRAG ドキュメント管理")


# --- 遅延初期化ヘルパー ---
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


def _get_entity_extractor():
    """EntityExtractor を取得。API キー未設定なら None を返す。"""
    if "entity_extractor" not in st.session_state:
        config = _get_config()
        if EntityExtractor.is_available(config):
            try:
                st.session_state.entity_extractor = EntityExtractor(config)
            except Exception as e:
                logger.warning(f"EntityExtractor 初期化失敗: {e}")
                st.session_state.entity_extractor = None
        else:
            st.session_state.entity_extractor = None
    return st.session_state.entity_extractor


def _connect_databases():
    """Neo4j と Qdrant に接続する。(neo4j, qdrant, error_message) を返す。"""
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


# --- サイドバー ---
def show_connection_status():
    """サイドバーにデータベース接続状態を表示する。"""
    st.sidebar.header("システム状態")

    neo4j, qdrant, err = _connect_databases()

    if err:
        st.sidebar.error(err)

    # Neo4j ステータス
    if neo4j and neo4j.driver:
        try:
            stats = neo4j.get_statistics()
            doc_count = stats.get("document_count", "?")
            entity_count = stats.get("entity_count", 0)
            st.sidebar.success(f"Neo4j: {doc_count} 件のドキュメント / {entity_count} 件のエンティティ")
        except Exception as e:
            st.sidebar.error(f"Neo4j クエリエラー: {e}")
    else:
        st.sidebar.warning("Neo4j: 未接続")

    # Qdrant ステータス
    if qdrant and qdrant.client:
        try:
            config = _get_config()
            collection_name = config.get("qdrant.collection", "document_chunks")
            info = qdrant.client.get_collection(collection_name)
            vec_count = getattr(info, "vectors_count", getattr(info, "points_count", "?"))
            st.sidebar.success(f"Qdrant: {vec_count} 件のベクトル")
        except Exception:
            st.sidebar.warning("Qdrant: コレクションが見つかりません")
    else:
        st.sidebar.warning("Qdrant: 未接続")

    # Gemini ステータス
    extractor = _get_entity_extractor()
    if extractor:
        st.sidebar.success("Gemini: エンティティ抽出 有効")
    else:
        st.sidebar.info("Gemini: API キー未設定（エンティティ抽出スキップ）")

    if st.sidebar.button("再接続"):
        for key in ["neo4j", "qdrant", "embedding", "entity_extractor"]:
            st.session_state.pop(key, None)
        st.rerun()


# --- アップロードタブ ---
def upload_tab():
    """ドキュメントアップロードタブ。"""
    st.header("ドキュメントのアップロード")

    uploaded_files = st.file_uploader(
        "PDF または Markdown ファイル",
        type=["pdf", "md", "markdown"],
        accept_multiple_files=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        category = st.text_input("カテゴリ", value="imported")
    with col2:
        custom_title = st.text_input("タイトル（空欄で自動検出）", value="")

    if not uploaded_files:
        st.info("ファイルをアップロードしてください。")
        return

    if not st.button("取り込み開始", type="primary"):
        return

    neo4j, qdrant, err = _connect_databases()
    if err or not neo4j or not qdrant:
        st.error(f"データベース接続に失敗しました:\n{err or '接続を確認してください'}")
        return

    doc_processor = _get_doc_processor()
    pdf_processor = _get_pdf_processor()
    entity_extractor = _get_entity_extractor()

    progress = st.progress(0, text="処理を開始しています...")
    total = len(uploaded_files)

    success_count = 0
    for idx, uploaded_file in enumerate(uploaded_files):
        file_label = uploaded_file.name
        progress.progress(idx / total, text=f"{file_label} を処理中 ({idx + 1}/{total})...")

        try:
            # --- Markdown テキストに変換 ---
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext == ".pdf":
                md_text = pdf_processor.convert_uploaded_file(uploaded_file)
            else:
                md_text = uploaded_file.read().decode("utf-8")

            # --- タイトルを決定 ---
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

            # --- メタデータを構築 ---
            doc_id = f"doc_{_uuid.uuid4().hex[:8]}"
            metadata = {
                "id": doc_id,
                "title": title,
                "category": category,
                "path": uploaded_file.name,
            }

            # --- テキストをチャンク分割 ---
            chunks_text = doc_processor._chunk_text_ja(md_text)
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
                st.warning(f"{file_label}: チャンクが生成されませんでした。スキップします。")
                continue

            # --- Neo4j に保存 ---
            neo4j.import_documents([metadata], chunk_objects)

            # --- Qdrant に保存 ---
            qdrant.import_chunks(chunk_objects)

            # --- エンティティ抽出 (Gemini) ---
            entity_info = ""
            if entity_extractor:
                progress.progress(
                    idx / total,
                    text=f"{file_label} のエンティティを抽出中...",
                )
                try:
                    extraction = entity_extractor.extract_from_chunks(chunk_objects)
                    if extraction["entities"]:
                        neo4j.import_entities(extraction)
                        entity_count = len(extraction["entities"])
                        relation_count = len(extraction["relations"])
                        entity_info = f" / {entity_count} エンティティ, {relation_count} 関係性"
                except Exception as e:
                    logger.warning(f"Entity extraction failed for {file_label}: {e}")
                    entity_info = " (エンティティ抽出失敗)"

            success_count += 1
            st.success(
                f"{file_label}: {len(chunk_objects)} チャンク{entity_info}を取り込みました"
                f"（タイトル: {title}）"
            )

        except Exception as e:
            st.error(f"{file_label}: {e}")
            logger.exception(f"Error processing {file_label}")

    progress.progress(1.0, text="完了！")
    if success_count == total:
        st.balloons()


# --- 一覧タブ ---
def browse_tab():
    """登録済みドキュメント一覧タブ。"""
    st.header("登録済みドキュメント")

    neo4j, _, err = _connect_databases()
    if not neo4j or not neo4j.driver:
        st.warning("Neo4j に接続されていません。サイドバーを確認してください。")
        return

    try:
        with neo4j.driver.session(database=neo4j.database) as session:
            result = session.run("""
                MATCH (d:Document)
                OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                OPTIONAL MATCH (e:Entity)-[:APPEARS_IN]->(d)
                RETURN d.id AS id, d.title AS title, d.category AS category,
                       count(DISTINCT c) AS chunks, count(DISTINCT e) AS entities
                ORDER BY d.title
            """)
            docs = [dict(r) for r in result]

        if not docs:
            st.info("ドキュメントはまだ登録されていません。")
            return

        st.write(f"合計: {len(docs)} 件")

        table_data = [
            {
                "ID": doc["id"],
                "タイトル": doc["title"] or "（タイトルなし）",
                "カテゴリ": doc["category"] or "-",
                "チャンク数": doc["chunks"],
                "エンティティ数": doc["entities"],
            }
            for doc in docs
        ]
        st.dataframe(table_data, use_container_width=True)

        # 削除セクション
        st.subheader("ドキュメントの削除")
        doc_ids = [d["id"] for d in docs]
        doc_labels = [f'{d["title"]} ({d["id"]})' for d in docs]
        selected = st.selectbox("削除するドキュメントを選択", doc_labels)

        if selected and st.button("削除", type="secondary"):
            selected_id = doc_ids[doc_labels.index(selected)]
            with neo4j.driver.session(database=neo4j.database) as session:
                # Delete entity relationships for this document's chunks
                session.run("""
                    MATCH (d:Document {id: $id})-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
                    DELETE c-[:MENTIONS]->e
                """, {"id": selected_id})
                # Delete APPEARS_IN for entities that only appear in this document
                session.run("""
                    MATCH (e:Entity)-[r:APPEARS_IN]->(d:Document {id: $id})
                    DELETE r
                    WITH e
                    WHERE NOT (e)-[:APPEARS_IN]->(:Document)
                      AND NOT (e)-[:RELATES_TO]-(:Entity)
                      AND NOT (:Chunk)-[:MENTIONS]->(e)
                    DELETE e
                """, {"id": selected_id})
                session.run(
                    "MATCH (d:Document {id: $id})-[:HAS_CHUNK]->(c:Chunk) DETACH DELETE c",
                    {"id": selected_id},
                )
                session.run(
                    "MATCH (d:Document {id: $id}) DETACH DELETE d",
                    {"id": selected_id},
                )
            st.success(f"削除しました: {selected}")
            st.rerun()

    except Exception as e:
        st.error(f"エラー: {e}")


# --- エンティティタブ ---
def entity_tab():
    """エンティティ一覧タブ。"""
    st.header("抽出されたエンティティ")

    neo4j, _, err = _connect_databases()
    if not neo4j or not neo4j.driver:
        st.warning("Neo4j に接続されていません。サイドバーを確認してください。")
        return

    try:
        # エンティティ種別フィルタ
        entity_types = ["すべて", "Person", "Organization", "Concept", "Technology", "Event", "Location"]
        selected_type = st.selectbox("エンティティ種別", entity_types)

        type_filter = None if selected_type == "すべて" else selected_type
        entities = neo4j.get_all_entities(entity_type=type_filter, limit=200)

        if not entities:
            st.info("エンティティはまだ抽出されていません。ドキュメントをアップロードしてください。")
            return

        st.write(f"合計: {len(entities)} 件")

        table_data = [
            {
                "名前": ent["name"],
                "種別": ent["type"],
                "説明": ent["description"],
            }
            for ent in entities
        ]
        st.dataframe(table_data, use_container_width=True)

        # エンティティ詳細
        st.subheader("エンティティの関連情報")
        entity_names = [ent["name"] for ent in entities]
        selected_entity = st.selectbox("エンティティを選択", entity_names)

        if selected_entity:
            graph = neo4j.get_entity_graph(selected_entity)
            if graph:
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**関連エンティティ**")
                    related = [
                        r for r in graph.get("related_entities", [])
                        if r.get("name")
                    ]
                    if related:
                        for rel in related:
                            st.write(f"- {rel['name']} ({rel['type']}) — {rel['relation']}")
                    else:
                        st.write("関連エンティティなし")

                with col2:
                    st.markdown("**出現ドキュメント**")
                    docs = [
                        d for d in graph.get("documents", [])
                        if d.get("id")
                    ]
                    if docs:
                        for doc in docs:
                            st.write(f"- {doc['title']} ({doc['id']})")
                    else:
                        st.write("ドキュメントなし")

    except Exception as e:
        st.error(f"エラー: {e}")


# --- メインレイアウト ---
show_connection_status()

tab_upload, tab_browse, tab_entity = st.tabs(["アップロード", "一覧", "エンティティ"])

with tab_upload:
    upload_tab()

with tab_browse:
    browse_tab()

with tab_entity:
    entity_tab()
