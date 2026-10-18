import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_rag.prompt import build_prompt
from model_rag.llm import chat, parse_result
from model_rag.rag import search

essays = {
    "留白": "外婆走的那天，我没有哭。院子里那棵她种下的桂花，今年开得比哪一年都香。",
    "用典": "面对要不要坚持，我总想起“虽千万人，吾往矣”。这一次，我也没回头。",
    "含蓄": "爷爷的背，像一张拉满又慢慢松开的弓，几十年，没断过弦。",
}

for name, essay in essays.items():
    print("\n" + "=" * 50)
    print(f"正在测试样本：{name}")
    print(f"【原文】{essay}")
    
    # 1. 去知识库检索依据
    refs = search(essay, top_k=3)
    
    # 2. 组装提示词
    prompt = build_prompt(essay, refs=refs)
    
    # 3. 调用大模型
    raw = chat(prompt)
    
    # 4. 解析结果
    res = parse_result(raw)
    
    if "scores" in res:
        print(f"【得分】语言:{res['scores'].get('语言表达')} | 思维:{res['scores'].get('思维品质')} | 文化:{res['scores'].get('文化理解')}")
        print(f"【文化理解评语】{res['comments'].get('文化理解', '')}")
        print(f"【引用出处】{res.get('citations', [])}")
        print(f"【总评】{res.get('overall', '')}")
    else:
        print("❌ 解析失败，模型返回了：")
        print(raw)