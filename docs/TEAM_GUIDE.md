# 「小嘉」图书馆AI智能体 (AssistantJia) 四人团队开工手册

> 认领身份后，把对应章节整段丢给 AI 编程助手（如 Cursor / VS Code）即可开工。

---

## 一、启动准备（全员必读，D 负责执行）

### 1.1 代码仓库与协作规范
统一使用 GitHub：[https://github.com/ovoME/AssistantJia](https://github.com/ovoME/AssistantJia)
由 D 统一管控主分支，其他三人作为协作者（Collaborators）加入。

#### 协作者加入步骤：
1. 注册 GitHub 账号并安装 Git：[https://git-scm.com/downloads](https://git-scm.com/downloads)
2. 配置本地身份：
   ```bash
   git config --global user.name "你的名字"
   git config --global user.email "你的GitHub邮箱"
   ```
3. 在 GitHub 接受仓库邀请邮件：[Settings -> Collaborators]
4. 克隆仓库到本地：
   ```bash
   git clone https://github.com/ovoME/AssistantJia.git
   cd AssistantJia
   ```

### 1.2 全员软件安装清单

| 软件 | 谁要装 | 下载地址 / 说明 | 验证命令 |
| :--- | :--- | :--- | :--- |
| **Git** | 全员 | [git-scm.com](https://git-scm.com/) | `git --version` |
| **Python 3.10+** | 全员（重点 A/C/D） | [python.org](https://www.python.org/) | `python --version` |
| **Node.js 20 LTS**| 全员（重点 B/D） | [nodejs.org](https://nodejs.org/) | `node -v` |
| **Docker Desktop** | D（全员联调时都要） | [docker.com](https://www.docker.com/) | `docker --version` |
| **Cursor / VS Code** | 全员 | [cursor.com](https://cursor.com/) | 能够打开即可 |
| **Redis** | 不用单独装 | Docker 启动 | `docker compose up redis` |

---

### 1.3 分支策略（全员遵守）

| 分支 | 用途 | 维护人 |
| :--- | :--- | :--- |
| **`main`** | 稳定可运行版本，仅接受 PR 合并 | D 管控，禁止直接 push |
| **`develop`** | 日常开发集成分支 | 所有人功能分支最终合到这里 |
| **`feature/backend-xxx`** | A 的后端功能分支 | A |
| **`feature/frontend-xxx`**| B 的前端功能分支 | B |
| **`feature/data-xxx`** | C 的数据功能分支 | C |
| **`feature/deploy-xxx`** | D 的部署/集成功能分支 | D |

#### 日常开发工作流：
```bash
git checkout develop
git pull origin develop             # 每天开工第一件事拉最新代码
git checkout -b feature/xxx         # 新建自己的功能分支
# ... 编写代码并自测 ...
git add .
git commit -m "feat: 描述你做了什么"
git push origin feature/xxx
# 然后去 GitHub 发起 Pull Request，指定一人 Review 并合并到 develop
```

---

### 1.4 大模型 API 密钥（A 负责，第 0 步）
1. 访问 [platform.deepseek.com](https://platform.deepseek.com) 注册并充值少量测试额度（10元可支撑开发很久）。
2. 创建 API Key，在 `backend/` 或项目根目录复制 `.env.example` 为 `.env`：
   ```env
   LLM_API_KEY=sk-your-deepseek-key
   LLM_BASE_URL=https://api.deepseek.com
   LLM_MODEL=deepseek-chat
   ```
   > ⚠️ 注意：`.env` 文件已被 `.gitignore` 忽略，切勿提交到 Git 仓库！

---

## 二、角色 A：Agent 后端工程师开工手册

### A0. 你的职责
- 搭建 FastAPI 后端骨架和 `/chat` 对话接口
- 封装图书馆业务工具（查馆藏、续借、预约、推荐）为 LangChain Tool
- 用 LangChain 搭建 ReAct Agent，自主选择工具、多步编排、结合 RAG 知识库
- 实现系统提示词（小嘉人设、幻觉兜底、转人工规则）
- 多轮对话记忆管理、流式输出 (SSE)

### A1. 后端骨架 Prompt
```text
我要做一个"图书馆AI智能体小嘉"的后端，技术栈 FastAPI + LangChain + ChromaDB，Python 3.11。
请帮我搭建完整的项目骨架和目录结构，要求：
1. 目录结构：
   app/main.py（FastAPI入口，含CORS）
   app/config.py（用pydantic-settings读取环境变量，.env里有LLM_API_KEY、LLM_BASE_URL、LLM_MODEL、REDIS_URL）
   app/api/chat.py（对话接口，POST /chat支持流式SSE，GET /chat/history）
   app/api/health.py（GET /health健康检查）
   app/agent/agent.py（Agent编排器）
   app/agent/tools/（工具目录，每个工具一个文件）
   app/agent/prompts.py（系统提示词）
   app/rag/retriever.py（向量库检索）
   app/schemas/（pydantic请求/响应模型）
2. 用 OpenAI兼容接口 接入大模型（base_url和api_key从环境变量读，DeepSeek是OpenAI兼容的）
3. /chat 接口先实现简单的“大模型直连+流式返回”，让我能跑通端到端，工具调用后面再加
4. 提供启动脚本，用 uvicorn app.main:app --reload --port 8000
5. 写好 requirements.txt 和每个文件的详细注释
请逐个文件生成完整代码，不要省略。生成后告诉我如何启动、如何测试 /chat。
```

### A2. 系统提示词 Prompt（小嘉人设）
```text
请帮我编写图书馆AI智能体“小嘉”的系统提示词（中文），要求：
1. 人设：22岁热情靠谱的学长型馆员，闽南籍但默认普通话，业务极熟，热络不油腻、专业不说教、示弱不硬撑
2. 明确规则：能查、能办的事调用对应工具；回答简洁口语化；涉及图书给书名作者索书号架位
3. 幻觉兜底：超出权限或不确定的事，明确说“这个我帮不了你，建议咨询人工服务台（电话xxx）”，绝不编造
4. 工具使用规范：需要实时数据（馆藏、可借状态、个人借阅）必须调工具，不能凭记忆回答
5. 安全红线：不输出图书全文、不提供他人借阅信息、不回答与图书馆无关的问题
把提示词写成Python字符串常量 SYSTEM_PROMPT，方便我在Agent里引用。
```

### A3. 封装图书馆工具清单

| 工具名 | 功能 | 输入 | 输出 |
| :--- | :--- | :--- | :--- |
| `search_books` | 查馆藏/架位/可借状态 | query, limit | 书单列表（含索书号、架位、可借状态） |
| `renew_book` | 一键续借 | reader_id, 财产号 | 续借结果（新还书日期/失败原因） |
| `reserve_book` | 预约图书 | reader_id, isbn | 预约结果（排队位置） |
| `get_user_borrows`| 查个人借阅 | reader_id | 当前借阅列表、到期日 |
| `recommend_books` | 个性化推荐 | reader_id 或 query | 推荐书单（C的算法） |
| `search_knowledge`| 查规则知识库 | question | RAG检索结果+回答 |

---

## 三、角色 B：Web 前端工程师开工手册

### B0. 你的职责
- 读者端对话界面（聊天窗口、流式输出、书单卡片、预约/续借操作按钮）
- 管理端数据看板（借阅趋势、热门图书、分类统计、AI采购建议/书评展示）
- 前后端联调，响应式适配（移动端 375px + PC 端 1200px）

### B1. 前端骨架 Prompt
```text
我要做一个图书馆AI智能体的Web前端，技术栈 Vue3 + Vite + TypeScript + Pinia + Vue Router +
Naive UI（或Element Plus）+ ECharts + Axios。请帮我搭建项目骨架：
1. 用 npm create vite 创建Vue3+TS项目，配置好依赖
2. 目录：src/views/（reader读者端、admin管理端）、src/components/、src/api/（请求层）、
   src/stores/（Pinia）、src/router/、src/assets/
3. 路由：/（读者对话）、/admin（管理看板），管理端可先不加登录
4. axios 封装请求层：baseURL指向 http://localhost:8000，处理流式SSE响应（/chat是流式）
5. 配置 Vite 代理，开发时 /api 转发到后端8000，解决跨域
6. 整体风格：简洁现代，主色调用图书馆的蓝绿色系，移动端优先
7. 给出完整文件代码和 npm install / npm run dev 启动步骤
```

---

## 四、角色 C：数据工程师开工手册

### C0. 你的职责
- 清洗 36,908 条借阅数据，做统计分析（热门图书、中图法分类、读者画像）
- 对接 OPAC 馆藏数据源（或构建本地检索库）
- 建设 RAG 知识库（规章制度、开馆时间、借阅限制等切块向量化）
- 实现图书推荐算法（热门推荐、分类偏好、协同过滤）
- 提供管理端统计分析接口数据

---

## 五、角色 D：全栈集成协调开工手册

### D0. 你的职责
- 代码仓库治理、接口契约制定、Docker Compose 一键启动维护
- 容器化 backend、frontend、redis、chroma 全栈服务
- 配置 GitHub Actions 自动化 CI/CD
- 编写端到端集成测试、把控整体进度、答辩材料统筹

---

## 六、集成联调顺序

```text
[1. 接口契约确认] (D & A)
       │
       ▼
[2. 数据清洗与统计] (C) ───► [3. 工具与Agent实现(Mock)] (A) ───► [4. 前端页面搭好(Mock)] (B)
                                          │                                 │
                                          ▼                                 ▼
                             [5. 真实数据与算法接入] (C 替换 A)   [6. 真实 /chat 接口联调] (A 替换 B)
                                                                            │
                                                                            ▼
                                                                [7. 全栈容器化与集成测试] (D)
```
