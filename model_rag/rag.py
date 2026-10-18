"""向量检索模块（人二 · 模型与提示词；人三做后端集成时做了兼容性调整）

改动点（相对交接包里的原版）：
1. 模型路径不再写死后直接 exit()：优先读 BGE_MODEL_PATH，再按常见目录查找，
   最后才回退到 HuggingFace 模型名。找不到时只抛出明确异常，不会杀掉后端进程。
2. 不再在 import 时删除 data/chroma，改为 ensure_index() 按需建库；
   后端启动时可以安全地调用。
3. 所有数据路径都相对项目根目录解析，不依赖启动时的工作目录。
4. 延迟加载模型与 Chroma，缺少依赖时后端仍可启动（/api/health 会给出状态）。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_INDEX = PROJECT_ROOT / "data" / "knowledge" / "index.json"
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma"
COLLECTION_NAME = "wenhua"

_MODEL_CANDIDATES = [
    # setup_model.py 在本机实际产生的路径（models/models/…）
    PROJECT_ROOT / "models" / "models" / "AI-ModelScope--bge-small-zh-v1.5" / "snapshots" / "master",
    # 交接文档里写过的路径
    PROJECT_ROOT / "models" / "AI-ModelScope" / "bge-small-zh-v1.5" / "snapshots" / "master",
    PROJECT_ROOT / "models" / "AI-ModelScope--bge-small-zh-v1.5" / "snapshots" / "master",
]

_model = None
_model_path: str | None = None
_model_error: str | None = None
_model_lock = threading.Lock()

_client = None
_collection = None
_client_error: str | None = None
_client_lock = threading.Lock()

_encode_lock = threading.Lock()
_build_lock = threading.Lock()


def local_model_path() -> str | None:
    """检查本机是否已有 bge 模型目录；没有则返回 None。"""
    env_path = os.getenv("BGE_MODEL_PATH", "").strip()
    candidates = ([Path(env_path)] if env_path else []) + _MODEL_CANDIDATES
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def has_local_model() -> bool:
    return local_model_path() is not None


def _resolve_model_path() -> str:
    """返回本地模型路径；没有本地模型时回退到模型名（首次会联网下载）。"""
    return local_model_path() or "BAAI/bge-small-zh-v1.5"


def _get_model():
    global _model, _model_path, _model_error
    if _model is not None:
        return _model
    if _model_error:
        raise RuntimeError(_model_error)
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # noqa: BLE001
            _model_error = f"未安装 sentence-transformers：{exc}"
            raise RuntimeError(_model_error) from exc
        try:
            _model_path = _resolve_model_path()
            _model = SentenceTransformer(_model_path)
        except Exception as exc:  # noqa: BLE001
            _model_error = (
                "向量模型加载失败。请先运行 python model_rag/setup_model.py 下载 "
                f"bge-small-zh-v1.5，或用 BGE_MODEL_PATH 指定本地路径。原始错误：{exc}"
            )
            raise RuntimeError(_model_error) from exc
    return _model


def _get_collection():
    global _client, _collection, _client_error
    if _collection is not None:
        return _collection
    if _client_error:
        raise RuntimeError(_client_error)
    with _client_lock:
        if _collection is not None:
            return _collection
        try:
            import chromadb
            try:
                from chromadb.config import Settings

                settings = Settings(anonymized_telemetry=False)
                _client = chromadb.PersistentClient(
                    path=str(CHROMA_DIR), settings=settings
                )
            except Exception:  # 旧版本没有 Settings，直接建客户端
                _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            _collection = _client.get_or_create_collection(COLLECTION_NAME)
        except Exception as exc:  # noqa: BLE001
            _client_error = f"向量库初始化失败：{exc}"
            raise RuntimeError(_client_error) from exc
    return _collection


def _load_items() -> list[dict[str, Any]]:
    if not KNOWLEDGE_INDEX.exists():
        raise FileNotFoundError(f"知识库索引不存在：{KNOWLEDGE_INDEX}")
    return json.loads(KNOWLEDGE_INDEX.read_text(encoding="utf-8"))


def _item_text(item: dict[str, Any]) -> str:
    return (
        f"{item.get('title', '')}。{item.get('origin', '')}。"
        f"可用于评价：{item.get('usable', '')}"
    )


def build_index(force: bool = False) -> int:
    """从 data/knowledge/index.json 建向量索引，返回条目数。

    force=True 时先清空旧集合再重建。
    """
    items = _load_items()
    if not items:
        raise RuntimeError("知识库为空，无法建立索引")

    with _build_lock:
        collection = _get_collection()
        if force:
            try:
                _client.delete_collection(COLLECTION_NAME)
            except Exception:  # noqa: BLE001
                pass
            collection = _client.get_or_create_collection(COLLECTION_NAME)
            globals()["_collection"] = collection
        elif collection.count() == len(items):
            return len(items)

        # 数量不一致（或强制重建）时整体清空，避免残留重复 id
        if collection.count() > 0:
            existing = collection.get(include=[])["ids"]
            if existing:
                collection.delete(ids=existing)

        model = _get_model()
        texts = [_item_text(it) for it in items]
        with _encode_lock:
            vectors = model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            ).tolist()

        batch_size = 64
        for start in range(0, len(items), batch_size):
            end = start + batch_size
            chunk = items[start:end]
            collection.add(
                ids=[it["id"] for it in chunk],
                embeddings=vectors[start:end],
                documents=texts[start:end],
                metadatas=[
                    {
                        "id": it["id"],
                        "source": it.get("source", ""),
                        "title": it.get("title", ""),
                    }
                    for it in chunk
                ],
            )
    print(f"✅ 成功索引 {len(items)} 条知识库数据！")
    return len(items)


def ensure_index() -> int:
    """确保向量库与知识库条数一致；不一致就重建。"""
    collection = _get_collection()
    item_count = len(_load_items())
    if collection.count() != item_count:
        return build_index(force=False)
    return item_count


def search(essay: str, top_k: int = 5) -> list[dict[str, Any]]:
    """检索与作文最相关的 top_k 条知识单元。"""
    ensure_index()
    collection = _get_collection()
    count = collection.count()
    if count == 0:
        return []
    model = _get_model()
    with _encode_lock:
        vec = model.encode(
            [essay], normalize_embeddings=True, show_progress_bar=False
        ).tolist()
    res = collection.query(query_embeddings=vec, n_results=min(top_k, count))
    out: list[dict[str, Any]] = []
    for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
        out.append(
            {
                "id": meta.get("id", ""),
                "text": doc,
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
            }
        )
    return out


def status() -> dict[str, Any]:
    """轻量状态查询，不加载模型、不建库。"""
    info: dict[str, Any] = {
        "model_loaded": _model is not None,
        "model_path": _model_path,
        "model_error": _model_error,
        "index_count": 0,
        "index_error": _client_error,
    }
    try:
        info["index_count"] = _get_collection().count()
    except Exception as exc:  # noqa: BLE001
        info["index_error"] = str(exc)
    return info


if __name__ == "__main__":
    build_index(force=True)
    print("\n--- 测试检索功能（搜家国情怀）---")
    for r in search("我站在江边，想起了那些为国捐躯的先烈。"):
        print(f"[{r['id']}] {r['source']}")
