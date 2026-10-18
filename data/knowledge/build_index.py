# build_index.py
# 作用：从本目录下三个 Markdown 提取知识单元，生成 index.json
# 运行：python build_index.py（在哪个目录运行都可以）

import json
import pathlib
import re

KNOW = pathlib.Path(__file__).resolve().parent
FILES = ["课标条目.md", "教材篇目.md", "经典评点.md"]

items = []

for fname in FILES:
    path = KNOW / fname
    if not path.exists():
        print(f"[警告] 找不到文件：{path}，跳过")
        continue

    text = path.read_text(encoding="utf-8")

    # 按 "## K001 标题" 这样的行切开
    for block in re.split(r"\n(?=## )", text):
        m = re.match(r"##\s+([KTP]\d{3})\s+(.+)", block)
        if not m:
            continue

        kid, title = m.group(1), m.group(2).strip()

        def field(name):
            """取 "- 字段：" 后的内容；支持字段内容跨行（如 K002 的原文）。"""
            lines = block.splitlines()
            for i, line in enumerate(lines):
                mm = re.match(r"-\s*" + name + r"[：:]\s*(.*)", line)
                if not mm:
                    continue
                parts = [mm.group(1).strip()]
                for nxt in lines[i + 1:]:
                    if re.match(
                        r"-\s*(出处|原文|可用于评价|关联主题|文化主题)[：:]", nxt
                    ) or nxt.startswith("## "):
                        break
                    if nxt.strip():
                        parts.append(nxt.strip())
                    else:
                        break
                return "\n".join(p for p in parts if p)
            return ""

        items.append({
            "id": kid,
            "title": title,
            "source": field("出处"),
            "origin": field("原文"),
            "usable": field("可用于评价"),
            "file": fname,
        })

# 写 index.json
out_path = KNOW / "index.json"
out_path.write_text(
    json.dumps(items, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"共生成 {len(items)} 条")
