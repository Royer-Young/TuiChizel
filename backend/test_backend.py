"""后端接口自测（不需要真实 API Key / 不需要向量模型）

运行（项目根目录）：
    python backend/test_backend.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TMP_DIR = Path(tempfile.mkdtemp(prefix="writing-agent-test-"))
os.environ["APP_DB_PATH"] = str(TMP_DIR / "app.db")
os.environ["RAG_DISABLED"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

import backend.main as main  # noqa: E402

FAKE_RESULT = {
    "scores": {"语言表达": 11, "思维品质": "8", "文化理解": 7},
    "comments": {
        "语言表达": "语言通顺。",
        "思维品质": "立意清晰。",
        "文化理解": "用典自然。",
    },
    "citations": ["K001", "T001"],
    "overall": "整体不错。",
}


def fake_chat(prompt: str, temperature: float = 0.0) -> str:
    assert "学生作文" in prompt
    return json.dumps(FAKE_RESULT, ensure_ascii=False)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"✅ {message}")


def run() -> None:
    main.chat = fake_chat
    main.llm.cleaned_key = "sk-test"

    with TestClient(main.app) as client:
        # 1. 健康检查
        resp = client.get("/api/health")
        check(resp.status_code == 200, "GET /api/health 返回 200")
        body = resp.json()
        check(body["status"] == "ok", "健康检查 status=ok")
        check(body["llm_configured"] is True, "健康检查能读到 API Key 状态")

        # 2. 空作文拦截
        resp = client.post("/api/evaluate", json={"text": "   "})
        check(resp.status_code == 422, "空白作文返回 422")

        # 3. 评价接口
        payload = {
            "text": "面对要不要坚持，我总想起“虽千万人，吾往矣”。",
            "student_id": "test001",
            "revision_count": 3,
            "adopt_count": 1,
        }
        resp = client.post("/api/evaluate", json=payload)
        check(resp.status_code == 200, "POST /api/evaluate 返回 200")
        result = resp.json()
        check(result["scores"] == {"语言表达": 10, "思维品质": 8, "文化理解": 7},
              "分数被截断到 0-10 且字符串分数被转成整数")
        check(result["citations"] == [], "无检索依据时过滤模型自拟的引用编号")
        check(result["refs"] == [], "RAG_DISABLED 时 refs 为空")
        check("warning" in result, "RAG 关闭时返回 warning")
        check("引用编号" in result["warning"], "warning 说明了引用编号被忽略")
        check(isinstance(result.get("session_id"), int), "返回 session_id")
        check(isinstance(result.get("elapsed_seconds"), int), "返回服务端计时")

        # 4. 历史查询（前端成长曲线依赖 score_json 字段）
        resp = client.get("/api/history/test001")
        check(resp.status_code == 200, "GET /api/history/test001 返回 200")
        rows = resp.json()
        check(len(rows) == 1, "历史记录写入 1 条")
        saved = json.loads(rows[0]["score_json"])
        check(saved["scores"]["文化理解"] == 7, "score_json 可被前端解析")
        check(rows[0]["think_seconds"] == result["elapsed_seconds"], "构思时长已落库")
        check(rows[0]["revision_count"] == 3, "修改次数已落库")
        check(rows[0]["adopt_count"] == 1, "采纳条数已落库")

        # 5. 单条详情
        sid = result["session_id"]
        resp = client.get(f"/api/session/{sid}")
        check(resp.status_code == 200 and resp.json()["id"] == sid, "单条详情可查询")

        # 6. 未配置 Key 时的提示
        main.llm.cleaned_key = ""
        resp = client.post("/api/evaluate", json={"text": "测试"})
        check(resp.status_code == 503, "未配置 Key 时返回 503")
        main.llm.cleaned_key = "sk-test"


if __name__ == "__main__":
    try:
        run()
        print("\n🎉 后端自测全部通过")
    finally:
        # 关闭 SQLite 连接后清理临时目录
        import shutil

        shutil.rmtree(TMP_DIR, ignore_errors=True)
