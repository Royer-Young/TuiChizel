import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_rag.llm import chat
from model_rag.rag import search

print("--- 开始环境体检 ---")

# 1. 检查 Key
try:
    print("1. 测试大模型 API...")
    res = chat("说一句你好")
    print(f"✅ API 通畅！模型回复: {res[:10]}...")
except Exception as e:
    print(f"❌ API 报错，请检查 .env 文件中的 Key 是否正确。报错: {e}")

# 2. 检查 RAG
try:
    print("\n2. 测试本地知识库检索...")
    refs = search("家国情怀")
    print(f"✅ 知识库检索通畅！找到 {len(refs)} 条依据。")
except Exception as e:
    print(f"❌ 知识库报错，请检查模型路径是否配置正确。报错: {e}")

print("\n--- 体检结束 ---")