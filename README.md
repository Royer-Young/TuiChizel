# 推敲 TuiChizel

**TuiChizel** = Tuition（辅导）+ Chisel（雕琢）：以辅导促修改，以雕琢成文章。

**AI Chinese Writing Coach** · 中学写作评价与教学辅助智能体

按分工把交付内容拆成以下几个目录，互不混放：

```text
TuiChizel/
├── backend/          # 人三：FastAPI 服务 + SQLite + 后端自测
├── model_rag/        # 人二：提示词、DeepSeek 调用、RAG 检索、实验脚本
├── frontend/         # 人四：Vue3 + ECharts 静态页面
├── data/
│   ├── knowledge/    # 人一：45 条知识库条目（K15 / T20 / P10）+ index.json
│   └── chroma/       # 向量索引（自动生成，已 gitignore）
├── models/           # 本地 bge 向量模型（自动下载，已 gitignore）
├── requirements.txt
├── .env.example
└── .env              # 本地环境变量（自己填写）
```

前端在 [`frontend/`](frontend/)，启动后端后会自动挂到
`http://127.0.0.1:8000/demo/`；也可以直接双击 `frontend/index.html` 打开。
默认就是正式评价界面，页面底部的「查看演示用例」可查看固定示例。

## 快速启动

```bash
git clone <仓库地址>
cd <仓库目录>

pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

copy .env.example .env          # Windows；macOS / Linux 用 cp
# 编辑 .env，填入 DEEPSEEK_API_KEY

python model_rag/setup_model.py # 首次下载 bge-small-zh-v1.5
python model_rag/rag.py         # 建向量索引（应输出 45 条）

uvicorn backend.main:app --reload --port 8000
```

以下内容不随仓库上传，需要在本机生成或配置：

- `.env`：API Key 等本地配置，按 `.env.example` 创建
- `models/`：本地向量模型，运行 `setup_model.py` 下载
- `data/chroma/`：向量索引，运行 `rag.py` 生成
- `data/app.db`：评价历史，首次启动自动创建

打开：

- 前端页面：<http://127.0.0.1:8000/demo/>
- 接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

## 接口

```text
GET  /api/health
POST /api/evaluate
     body: {text, student_id, revision_count, adopt_count}
     resp: {scores, comments, citations, overall, refs, elapsed_seconds, session_id}
GET  /api/history/{student_id}
GET  /api/session/{session_id}
```

## 自测

```bash
python backend/test_backend.py
```

不调用真实 API，也不加载向量模型；全部通过会输出
`🎉 后端自测全部通过`。

## 没有 Key / 没有模型时

- 没有 Key（包括 `.env` 里还是占位 Key）：服务正常启动，`/api/evaluate`
  返回 503 并提示配置，其他接口可用。
- 没有向量模型：服务正常启动，评价退回「无知识库依据」模式并在响应里带
  `warning`；跑一次 `python model_rag/setup_model.py` 即可恢复。
- 只想调接口：设置 `RAG_DISABLED=1`。

更多细节见 [`backend/README.md`](backend/README.md) 和
[`model_rag/README.md`](model_rag/README.md)。
