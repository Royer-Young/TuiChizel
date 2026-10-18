import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_rag.llm import chat

# 这就是第 1 天指南里说的最普通的提示词（没有任何文化维度和含蓄提醒）
BASIC_PROMPT = "请作为一名中学语文老师，点评下面这段作文：\n\n{essay}"

essays = {
    "留白": "外婆走的那天，我没有哭。院子里那棵她种下的桂花，今年开得比哪一年都香。",
    "用典": "面对要不要坚持，我总想起“虽千万人，吾往矣”。这一次，我也没回头。",
    "含蓄": "爷爷的背，像一张拉满又慢慢松开的弓，几十年，没断过弦。",
}

for name, essay in essays.items():
    print("\n" + "=" * 50)
    print(f"正在测试【对照组 A】：{name}")
    print(f"【原文】{essay}")
    
    # 直接调用，不加任何知识库和特殊要求
    prompt = BASIC_PROMPT.format(essay=essay)
    raw = chat(prompt)
    
    print("【普通大模型的回复】")
    print(raw)