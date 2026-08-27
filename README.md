# 他山助手

面向中国科学院大学 AI 实训课程的文本答疑与教学反馈闭环系统。

学生在网页中选择课程，直接描述疑问、粘贴代码或报错；系统用 DeepSeek V4 Flash 进行多轮答疑，并把问题自动结构化为 Case 写入飞书多维表格。课后可生成课程诊断报告，用于发现高频问题、未解决问题、AI 错误回答和课程改进点。

## 核心流程

```text
他山官网
  ↓
选择第 1–9 课
  ↓
他山助手多轮答疑
  ↓
[解决了] [还没解决] [回答有问题]
  ↓
结构化 Case → 飞书多维表格
  ↓
课后统计 + LLM 归纳
  ↓
飞书 LessonReports
```

教师侧统一使用飞书。

## 已实现

- 9 节课程选择与独立课程上下文
- DeepSeek V4 Flash 文本答疑
- 多轮会话与刷新恢复
- `解决了 / 还没解决 / 回答有问题`
- 一个问题一个 Case；新问题不会污染旧 Case
- Markdown、代码块与复制回答
- 匿名浏览器 ID，用于统计参与人数，不要求学生登录
- 自动 Case 分类、问题摘要、根因与方案抽取
- 飞书多维表格写入与更新
- 课后课程统计与诊断报告
- 常见 API Key / Token / Password 自动脱敏
- 本地开发模式：没有 DeepSeek / 飞书凭证也能跑
- Docker 部署
- GitHub Actions CI

## 架构

```text
frontend/index.html
        │
        ▼
    FastAPI
     │   │
     │   ├── DeepSeek Responses API：学生答疑
     │   ├── DeepSeek JSON Output：Case 结构化
     │   └── DeepSeek：课后课程诊断
     │
     └── Feishu Bitable
          ├── Cases
          └── LessonReports
```

DeepSeek Responses API 当前支持 `deepseek-v4-flash`：
- https://api-docs.deepseek.com/api/create-response/
- https://api-docs.deepseek.com/guides/responses_api/

## 快速运行

要求 Python 3.12+。

```bash
git clone <your-repo-url>
cd tashan-assistant

python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
uvicorn app.main:app --reload
```

打开：

```text
http://127.0.0.1:8000
```

如果 `.env` 没有填写 DeepSeek 和飞书凭证，系统自动进入本地开发模式：

- AI 使用内置模拟回答
- Case 写入 `data/cases.jsonl`
- 报告写入 `data/reports.jsonl`

也可以直接双击 `frontend/index.html` 查看纯前端演示。

## DeepSeek 配置

在 `.env` 中填写：

```env
DEEPSEEK_API_KEY=your_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash

# 学生答疑优先速度
TUTOR_REASONING_EFFORT=none

# 课后分析优先质量
ANALYST_REASONING_EFFORT=high
```

DeepSeek API 是无状态的，多轮历史由本项目后端自行维护并回传。

## 飞书配置

### 1. 创建企业自建应用

在飞书开放平台创建企业自建应用，开通多维表格读写权限，并允许该应用访问用于本项目的数据表。

取得：

```env
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_APP_TOKEN=
FEISHU_CASE_TABLE_ID=
FEISHU_REPORT_TABLE_ID=
```

### 2. 建立 `Cases` 表

字段名必须与下列名称一致：

| 字段 | 建议类型 |
| --- | --- |
| Case ID | 文本 |
| 匿名学员ID | 文本 |
| 课次 | 数字 |
| 课程版本 | 文本 |
| 原始问题 | 多行文本 |
| 问题摘要 | 多行文本 |
| 一级分类 | 文本 |
| 二级分类 | 文本 |
| 根因 | 多行文本 |
| 解决方案 | 多行文本 |
| 状态 | 文本 |
| 对话轮数 | 数字 |
| 首次回答解决 | 复选框 |
| 最新进展 | 多行文本 |
| 最新回答 | 多行文本 |
| 对话记录 | 多行文本 |
| 最近反馈类型 | 文本 |
| AI回答被纠错 | 复选框 |
| 反馈意见 | 多行文本 |
| FAQ候选 | 复选框 |
| 创建时间 | 文本 |
| 更新时间 | 文本 |
| 解决时间 | 文本 |

`FEISHU_STORE_TRANSCRIPT=false` 为默认值：飞书不保存完整对话，只保存结构化信息和最新回答。

如果明确完成了学员告知/授权并确实需要完整轨迹，可改为：

```env
FEISHU_STORE_TRANSCRIPT=true
```

### 3. 建立 `LessonReports` 表

| 字段 | 建议类型 |
| --- | --- |
| 课次 | 数字 |
| 课程版本 | 文本 |
| 生成时间 | 文本 |
| 参与学员数 | 数字 |
| Case数 | 数字 |
| 确认解决率 | 数字 |
| AI回答被纠错数 | 数字 |
| 报告正文 | 多行文本 |

## 课后生成教学报告

先在 `.env` 配置一个随机长字符串：

```env
ADMIN_TOKEN=replace-with-a-long-random-string
```

查询某节课的统计：

```bash
curl \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN" \
  http://127.0.0.1:8000/api/admin/lessons/1/stats
```

生成第 1 课教学诊断，并自动写入飞书 `LessonReports`：

```bash
curl -X POST \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN" \
  http://127.0.0.1:8000/api/admin/lessons/1/report
```

精确数量、比例和平均轮数由程序计算；LLM 只负责归纳：

- 高频问题
- 共性根因
- 未解决 / 被纠错问题
- 候选 FAQ
- 下一版课程修改建议

## Case 状态

```text
NEW
 ↓
ANSWERED
 ├─ 解决了 ───────→ RESOLVED
 ├─ 还没解决 ─────→ CONTINUING → ANSWERED
 ├─ 回答有问题 ───→ FLAGGED    → ANSWERED
 └─ 主动新对话 ───→ ABANDONED
```

只有学生主动点击 `解决了` 才计入确认解决。

`ANSWERED`、`ABANDONED` 都不等于“确认未解决”。

## 课程内容

课程目录来自当前课程表：

```text
knowledge/lessons.json
knowledge/lessons/01.md ... 09.md
```

目前每个 Markdown 只是课程上下文骨架。后续拿到主讲人的 PPT、讲义、Demo、软件版本后，直接更新对应课程 Markdown 即可，不需要修改程序。

第一版故意不引入向量数据库和复杂 RAG。当前课程材料规模用单课上下文更简单、更稳定。

## Docker

```bash
cp .env.example .env
# 编辑 .env

docker compose up -d --build
```

默认监听：

```text
http://localhost:8000
```

## 测试

```bash
pip install -r requirements-dev.txt
pytest -q
```

GitHub Actions 会在每次 push 和 pull request 时自动执行：

```text
Python compile → pytest
```

## 目录

```text
tashan-assistant/
├── .github/workflows/ci.yml
├── app/
│   ├── analytics.py
│   ├── config.py
│   ├── deepseek.py
│   ├── feishu.py
│   ├── local_store.py
│   ├── main.py
│   ├── models.py
│   ├── prompts.py
│   └── sanitize.py
├── frontend/
│   └── index.html
├── knowledge/
│   ├── lessons.json
│   └── lessons/
├── tests/
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## 上线前检查

- 不要提交 `.env`
- 不要把 DeepSeek Key、飞书 Secret 写进前端
- `ADMIN_TOKEN` 必须替换
- 若前后端跨域部署，设置 `ALLOWED_ORIGINS`
- 通过 HTTPS 对外提供服务
- 根据课程的数据治理要求决定是否开启完整对话保存
- 在网关层增加基础访问频率限制

---

当前版本聚焦一个目标：先把“学生真实问题 → AI 答疑 → 结构化 Case → 飞书教学诊断”闭环跑稳，再根据真实课堂数据决定是否加入 RAG、Harness、自动告警或人工接管。
