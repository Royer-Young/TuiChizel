# 后端部分说明（人三 · 后端与数据）

项目根目录按分工拆成以下几个目录：

- `backend/` —— 人三负责的后端与数据（本目录）
- `model_rag/` —— 人二负责的模型、提示词与 RAG 检索
- `data/knowledge/` —— 人一负责的知识库
- `frontend/` —— 人四负责的前端页面

后端启动时会自动把 `frontend/` 挂到 `http://127.0.0.1:8000/demo/`。

## 一、我交付了什么

| 文件 | 作用 |
| --- | --- |
| `backend/main.py` | FastAPI 服务：健康检查、评价接口、历史查询、单条详情 |
| `backend/db.py` | SQLite 建表、写入、按学生查询历史 |
| `data/app.db` | 首次启动自动生成（已被 `.gitignore` 排除） |
| `backend/test_backend.py` | 不依赖真实 Key / 向量模型的后端自测 |
| `.env.example` | 环境变量模板（原文件是空的，已补上） |

接口与前端（人四）的约定完全对齐：

```text
GET  /api/health
POST /api/evaluate
     body: {text, student_id, revision_count, adopt_count}
     resp: {scores, comments, citations, overall, refs, elapsed_seconds, session_id}
GET  /api/history/{student_id}      -> 行内包含 score_json 字符串
GET  /api/session/{session_id}      -> 单条详情（调试用）
```

## 二、启动步骤

在项目根目录下：

```bash
# 1. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 配置 Key
copy .env.example .env
#    编辑 .env，填入 DEEPSEEK_API_KEY=sk-...

# 3. 下载本地向量模型（只需一次，约 100MB）
python model_rag/setup_model.py
#    如果下载路径与预期不同，把真实路径写进 .env 的 BGE_MODEL_PATH

# 4. 建立向量索引并验证检索（知识库内容改动后也要重新运行）
python model_rag/rag.py

# 5. 启动后端
uvicorn backend.main:app --reload --port 8000
```

打开：

- 接口文档：<http://127.0.0.1:8000/docs>
- 前端页面：<http://127.0.0.1:8000/demo/>
- 健康检查：<http://127.0.0.1:8000/api/health>

前端也可以直接双击 `frontend/index.html` 打开；默认是正式评价界面，页面底部可进入演示用例。

### 没有模型 / 没有 Key 时

- 没有 Key：`/api/evaluate` 返回 503，并提示去 `.env` 配置；其他接口正常。
- 没有向量模型：服务仍能启动，评价会退回「无知识库依据」模式，
  响应里带 `warning`。先跑 `python model_rag/setup_model.py` 即可恢复 RAG。
- 只想先跑通接口：设置 `RAG_DISABLED=1`。

### 自测

```bash
python backend/test_backend.py
```

期待最后输出 `🎉 后端自测全部通过`。该脚本使用临时数据库和模拟模型回复，
不会调用真实 API。

另外，本机已完成依赖安装、bge 模型下载、45 条知识库向量索引，并用两篇
真实作文跑通了 `/api/evaluate`（DeepSeek 实际调用）与 `/api/history`。
克隆后仍需按上面的步骤配置 `.env`、下载模型并建立索引。

## 三、我对交接内容做的兼容性修改

| 文件 | 原问题 | 修改 |
| --- | --- | --- |
| `model_rag/rag.py` | 模型路径写死为 `D:/Chinese/...`，找不到时 `exit()`；import 时删除 `data/chroma`；所有路径依赖启动目录 | 支持 `BGE_MODEL_PATH` / 默认 `models/` 目录 / HuggingFace 兜底；改为 `ensure_index()` 按需建库；路径统一相对项目根目录 |
| `model_rag/llm.py` | 没有 Key 时 `OpenAI()` 在 import 阶段直接抛异常，后端无法启动 | 改为延迟创建客户端；没有 Key 时接口返回 503 而不是进程崩溃；显式读取项目根目录 `.env`；占位 Key 视为未配置 |
| `.env.example` | 空文件 | 补上 Key、模型路径、RAG_DISABLED 说明 |
| `data/knowledge/build_index.py` | `field()` 只取字段第一行，K002 的多行原文被截断 | 改为读取到下一个字段之前的全部行；`index.json` 已重新生成 |
| `frontend/app.js` | 正式评价界面的「依据」只查演示用的 `DEMO.citeMap`，会显示成「条目 K001」 | 增加 `realRefs`，优先用后端返回的 `refs[].source + refs[].title` 显示真实出处 |

`prompt.py` 和知识库三个 Markdown 的正文未改动。

## 四、检查交接内容时发现的问题

1. **对比实验只有 3/9 个样本**（未改动）：`docs/截图/对比实验/对比实验统计表.md`
   中后 6 行仍是「待填」，实验记录也写明在等人一补 6 个样本。开题演示若只展示
   3 个样本，建议话术上明确说「初步定性观察」。
2. **`源码.txt` 与 `app.js` 内容有差异**：前者像是历史版本，实际运行以 `app.js`
   为准，建议删掉或注明。
3. **前端依赖 CDN**（Vue3、ECharts、Noto 字体）：答辩电脑需要联网；如需离线演示，
   建议提前把三个 CDN 文件下载到本地。
