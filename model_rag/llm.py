import os
import json
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 无论从哪个目录启动服务，都优先读项目根目录的 .env
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)
load_dotenv(override=True)

# 强制清洗：把首尾的空白字符全部抹掉
raw_key = os.getenv("DEEPSEEK_API_KEY", "")
cleaned_key = raw_key.strip().lstrip("\ufeff").replace("\r", "").replace("\n", "")

# .env.example \u91cc\u7684\u5360\u4f4d Key\uff08\u5982 sk-\u5728\u8fd9\u91cc\u586b\u4f60\u81ea\u5df1\u7684key\uff09\u4e0d\u7b97\u5df2\u914d\u7f6e\uff0c
# \u5426\u5219\u670d\u52a1\u4f1a\u62ff\u5b83\u53bb\u8bf7\u6c42\uff0c\u8fd4\u56de\u4e00\u4e2a\u770b\u4e0d\u61c2\u7684 401\uff0c\u800c\u4e0d\u662f\u660e\u786e\u7684 503\u3002
if len(cleaned_key) < 20 or any(ord(ch) > 127 for ch in cleaned_key):
    cleaned_key = ""

client = None


def _get_client() -> OpenAI:
    """延迟创建客户端：没有 Key 时也让 FastAPI 能正常启动。"""
    global client
    if client is None:
        if not cleaned_key:
            raise RuntimeError(
                "未配置 DEEPSEEK_API_KEY，请在项目根目录创建 .env 文件后重启服务。"
            )
        client = OpenAI(
            api_key=cleaned_key,
            base_url="https://api.deepseek.com",  # 官方标准 base_url
            timeout=60.0,
        )
    return client


def chat(prompt: str, temperature: float = 0.0) -> str:
    resp = _get_client().chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content


def parse_result(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "scores": {"语言表达": 0, "思维品质": 0, "文化理解": 0},
        "comments": {
            "语言表达": "解析失败",
            "思维品质": "解析失败",
            "文化理解": "解析失败",
        },
        "citations": [],
        "overall": "模型返回格式异常，请重试",
    }


if __name__ == "__main__":
    print("正在调用 API...")
    print(chat("用一句话说明什么是作文自动评分。"))