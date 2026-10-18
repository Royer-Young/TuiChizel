"""FastAPI 服务（人三 · 后端与数据）

启动方式（在项目根目录下）：
    uvicorn backend.main:app --reload --port 8000

接口：
    GET  /api/health                健康检查
    POST /api/evaluate              评价作文 + 落库
    GET  /api/history/{student_id}  成长曲线数据
    GET  /api/session/{session_id}  单条评价详情（调试用）

前端（人四）的约定：
    请求体 {text, student_id, revision_count, adopt_count}
    响应体 {scores, comments, citations, overall, refs, elapsed_seconds, ...}
    （think_seconds 为兼容字段，实际耗时由服务端按处理过程记录）
    /api/history 返回的每一行包含 score_json（JSON 字符串）
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from backend import db
from model_rag import llm, rag
from model_rag.llm import chat, parse_result
from model_rag.prompt import build_prompt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_CANDIDATES = [
    PROJECT_ROOT / "frontend",  # 人四的前端，随项目一起放在仓库内
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("writing-agent")

DIMENSIONS = ("语言表达", "思维品质", "文化理解")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    logger.info("SQLite 已就绪：%s", db.get_db_path())

    if not llm.cleaned_key:
        logger.warning(
            "未配置 DEEPSEEK_API_KEY，/api/evaluate 会返回 503。"
            "请复制 .env.example 为 .env 并填入 Key。"
        )

    if os.getenv("RAG_DISABLED") == "1":
        logger.warning("RAG_DISABLED=1，跳过向量索引初始化")
    elif not rag.has_local_model():
        logger.warning(
            "未找到本地向量模型，RAG 检索会不可用。"
            "请运行 python model_rag/setup_model.py，或用 BGE_MODEL_PATH 指定模型目录。"
        )
    else:
        try:
            count = await asyncio.to_thread(rag.ensure_index)
            logger.info("RAG 索引已就绪：%d 条", count)
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG 索引初始化失败，评价接口将退回无检索模式：%s", exc)
    yield


app = FastAPI(title="推敲 Tuiqiao · 中学写作评价与教学辅助智能体", lifespan=lifespan)

# 前端是本地静态页（file:// 或 127.0.0.1 其他端口），统一放开跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EssayIn(BaseModel):
    text: str = Field(..., description="学生作文全文")
    student_id: str = Field("test001", max_length=64)
    think_seconds: int = Field(0, ge=0, le=10_000_000)
    revision_count: int = Field(0, ge=0, le=10_000_000)
    adopt_count: int = Field(0, ge=0, le=10_000_000)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("作文内容不能为空")
        return value

    @field_validator("student_id")
    @classmethod
    def student_id_not_blank(cls, value: str) -> str:
        value = value.strip()
        return value or "test001"


def _score(value: Any) -> int:
    """容忍模型返回 8 / "8" / "8分" / 8.0 等写法。"""
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        value = match.group(0) if match else 0
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(10, number))


def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    """把模型返回的结果收敛成前端稳定可用的结构。"""
    if not isinstance(result, dict):
        result = {}
    scores_in = result.get("scores") if isinstance(result.get("scores"), dict) else {}
    comments_in = (
        result.get("comments") if isinstance(result.get("comments"), dict) else {}
    )

    scores = {dim: _score(scores_in.get(dim, 0)) for dim in DIMENSIONS}
    comments = {
        dim: str(comments_in.get(dim) or "（该维度暂无评语）") for dim in DIMENSIONS
    }

    citations = result.get("citations")
    if isinstance(citations, str):
        citations = [citations]
    if not isinstance(citations, list):
        citations = []
    # 模型有时会返回 "K001、T001"、"[K001]" 或带解释的写法，
    # 统一用正则抠出 K/T/P + 三位数字的编号。
    split: list[str] = []
    for item in citations:
        for citation_id in re.findall(r"[KTP]\d{3}", str(item)):
            if citation_id not in split:
                split.append(citation_id)

    return {
        "scores": scores,
        "comments": comments,
        "citations": split,
        "overall": str(result.get("overall") or "（模型未返回总评）"),
    }


def validate_citations(
    citations: list[str], refs: list[dict[str, Any]]
) -> tuple[list[str], str | None]:
    """只保留本次真正检索到的条目编号，避免模型编造出处。"""
    if not refs:
        if citations:
            return [], "本次未检索到知识库依据，已忽略模型给出的引用编号"
        return [], None

    valid_ids = {r["id"] for r in refs}
    kept = [c for c in citations if c in valid_ids]
    dropped = [c for c in citations if c not in valid_ids]
    if dropped:
        return kept, f"模型引用了未检索到的条目 {dropped}，已过滤"
    return kept, None


def safe_search(text: str, top_k: int = 5) -> tuple[list[dict[str, Any]], str | None]:
    """检索失败不应让整次评价失败：返回空依据 + 一条 warning。"""
    if os.getenv("RAG_DISABLED") == "1":
        return [], "RAG 已禁用（RAG_DISABLED=1），本次评价未使用知识库依据"
    try:
        return rag.search(text, top_k=top_k), None
    except Exception as exc:  # noqa: BLE001
        logger.warning("检索失败，本次使用无依据模式：%s", exc)
        return [], f"知识库检索不可用：{exc}"


@app.get("/api/health")
def health() -> dict[str, Any]:
    rag_info = rag.status()
    return {
        "status": "ok",
        "llm_configured": bool(llm.cleaned_key),
        "rag": rag_info,
        "database": str(db.get_db_path()),
    }


@app.post("/api/evaluate")
def evaluate(data: EssayIn) -> dict[str, Any]:
    if not llm.cleaned_key:
        raise HTTPException(
            status_code=503,
            detail="未配置 DEEPSEEK_API_KEY，请在项目根目录创建 .env 文件后重启服务。",
        )

    started_at = time.perf_counter()
    refs, rag_warning = safe_search(data.text, top_k=5)
    prompt = build_prompt(data.text, refs)

    try:
        raw = chat(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("大模型调用失败")
        raise HTTPException(
            status_code=502, detail=f"大模型调用失败：{exc}"
        ) from exc

    result = normalize_result(parse_result(raw))
    result["refs"] = refs

    citations, citation_warning = validate_citations(result["citations"], refs)
    result["citations"] = citations
    warnings = [w for w in (rag_warning, citation_warning) if w]
    if warnings:
        result["warning"] = "；".join(warnings)

    # 构思时长以服务端实际处理耗时为准（检索 + 模型调用 + 结果整理）
    elapsed_seconds = max(0, int(round(time.perf_counter() - started_at)))
    result["elapsed_seconds"] = elapsed_seconds

    try:
        result["session_id"] = db.save_session(
            student_id=data.student_id,
            essay_text=data.text,
            result=result,
            think_seconds=elapsed_seconds,
            revision_count=data.revision_count,
            adopt_count=data.adopt_count,
        )
    except Exception as exc:  # noqa: BLE001
        # 存库失败不影响本次结果返回，但要在日志里留痕
        logger.exception("写入 SQLite 失败")
        prefix = result["warning"] + "；" if result.get("warning") else ""
        result["warning"] = prefix + f"本次结果未写入数据库：{exc}"

    return result


@app.get("/api/history/{student_id}")
def history(student_id: str, limit: int = 100) -> list[dict[str, Any]]:
    return db.get_history(student_id, limit=limit)


@app.get("/api/session/{session_id}")
def session_detail(session_id: int) -> dict[str, Any]:
    row = db.get_session(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return row


# 方便本地演示：若存在前端目录，额外挂到 /demo/（不影响 API）
for candidate in FRONTEND_CANDIDATES:
    if candidate.exists():
        app.mount("/demo", StaticFiles(directory=str(candidate), html=True), name="demo")
        logger.info("前端已挂载：http://127.0.0.1:8000/demo/")
        break
