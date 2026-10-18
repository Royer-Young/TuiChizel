# 模型与检索模块（人二 · 提示词 + RAG）

本目录原样接收人二交付的模型、提示词与检索代码，并做了少量兼容性调整，
使它可以被 `backend/` 直接 import、在本机稳定运行。

## 文件说明

| 文件 | 来源 | 作用 |
| --- | --- | --- |
| `prompt.py` | 人二 | 三维度（语言表达 / 思维品质 / 文化理解）提示词模板，`build_prompt(essay, refs)` |
| `rag.py` | 人二 | 读取 `data/knowledge/index.json`，用 bge-small-zh-v1.5 建 Chroma 索引并检索 |
| `llm.py` | 人二 | DeepSeek 调用与 JSON 解析（延迟创建客户端，无 Key 也能启动） |
| `setup_model.py` | 人二 | 从魔搭下载 bge-small-zh-v1.5 到项目根目录 `models/` |
| `test_env.py` | 人二 | Key + 知识库检索的连通性体检 |
| `test_prompt.py` | 人二 | 完整链路（检索 → 提示词 → 模型 → 解析）测试 |
| `test_group_a.py` | 人二 | 对比实验 A 组（普通大模型） |
| `docs/` | 人二 | 交接指南、对比实验记录与截图 |

## 常用命令（均在项目根目录下执行）

```bash
# 下载 / 校验向量模型（只需一次）
python model_rag/setup_model.py

# 建立或重建向量索引，并跑一条检索示例
python model_rag/rag.py

# 环境体检（需要真实 Key 和模型）
python model_rag/test_env.py

# 完整链路测试（需要真实 Key 和模型）
python model_rag/test_prompt.py
```

## 人三做的兼容性调整

1. 模型路径不再写死 `D:/Chinese/...`，也不在 import 时 `exit()`；按
   `BGE_MODEL_PATH` → 项目 `models/` → HuggingFace 顺序查找。
2. 不在 import 时删除 `data/chroma`，改为 `ensure_index()` 按需建库。
3. 所有路径相对项目根目录解析，不依赖启动时的工作目录。
4. 延迟创建 OpenAI 客户端：没有 Key 时 FastAPI 仍能启动，评价接口返回 503。

`prompt.py` 的提示词正文未改动。详细说明见
[`docs/模型与检索模块交接指南.md`](docs/模型与检索模块交接指南.md)。
