# 🤖 AssistantJia (小嘉 · 图书馆AI智能体)

> **厦门大学嘉庚学院第二届AI应用创新大赛参赛项目**  
> **主题赛道**：设计2030年的嘉庚学院图书馆 · AI赋能前沿技术应用 & 智慧读者服务

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)](https://www.python.org/)
[![Node: 20 LTS](https://img.shields.io/badge/Node.js-20%20LTS-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org/)
[![LangChain](https://img.shields.io/badge/LangChain-v0.2-1C3C3C.svg)](https://www.langchain.com/)

---

## 📖 项目简介

**AssistantJia（小嘉）** 是专为厦门大学嘉庚学院图书馆打造的新一代自主型 AI 智能体（Agent）。小嘉以“22岁热情靠谱的学长型馆员”为人设，结合学校 3.7 万条真实借阅历史与规章制度知识库，打通馆藏检索、架位精准导航、借阅与一键续借/预约全流程，并为馆方提供基于借阅趋势的智能采购决策与数据看板。

### ✨ 核心特性
- 💬 **智能馆员全流程闭环**：支持自然语言查书、索书号智能解析与三维/立体架位指引、在线预约、一键续借。
- 📚 **RAG 规则检索**：接入图书馆规章、借期规范、研修室预约制度，具备事实核验与幻觉兜底（超纲主动转人工）。
- 🎯 **个性化阅读推荐**：基于中图法大类与借阅协同过滤算法，为读者量身推荐馆藏图书。
- 📊 **管理端数据洞察看板**：36,908 条借阅数据可视化分析、借阅趋势监控、AI 智能采购建议与图书书评自动生成。
- ⚡ **现代化技术架构**：前后端解耦（FastAPI + LangChain + ChromaDB + Vue 3 + ECharts），支持 SSE 流式打字机输出与 Docker 一键容器化部署。

---

## 🗂️ 目录结构说明

```text
AssistantJia/
├── backend/                # 角色 A 的工作目录：FastAPI + LangChain Agent 后端服务
│   ├── app/                # 核心应用代码（API、Agent、Tools、RAG、Schemas）
│   ├── tests/              # 单元与集成测试 (pytest)
│   ├── requirements.txt    # 后端 Python 依赖
│   └── Dockerfile          # 后端容器构建
├── frontend/               # 角色 B 的工作目录：Vue 3 + Vite + TypeScript 前端
│   ├── src/                # 页面、组件、状态管理 (Pinia)、API封装
│   ├── package.json        # 前端依赖配置
│   └── Dockerfile          # 前端多阶段构建与 Nginx 托管
├── data/                   # 角色 C 的工作目录：数据处理、推荐算法与向量库
│   ├── raw/                # 原始借阅数据 (Excel等，已被 gitignore，本地存放)
│   ├── processed/          # 清洗后的结构化数据 (CSV/JSON)
│   ├── knowledge/          # 知识库原始文件 (规章制度 PDF/Word/Markdown)
│   └── scripts/            # 数据清洗、分析与推荐算法脚本
├── deploy/                 # 角色 D 的工作目录：Docker 编排与部署脚本
│   ├── docker-compose.yml  # 全栈服务容器编排 (Backend + Frontend + Redis + Chroma)
│   └── nginx/              # Nginx 反代与 SSE 流式输出优化配置
├── docs/                   # 接口契约、大赛材料与设计文档
│   ├── TEAM_GUIDE.md       # 团队四人开工手册详细指导 (必读)
│   ├── CONTEST_INFO.md     # 第二届AI应用创新大赛背景与提交流程
│   └── api-contract.md     # 前后端 API 接口契约
├── prompts/                # 团队共享的系统提示词、评测 Case 与 Prompt 库
├── .env.example            # 环境变量配置模板
├── .gitignore              # Git 忽略配置
├── docker-compose.yml      # 根目录一键启动编排
├── LICENSE                 # MIT 开源协议
└── README.md               # 项目主说明文档
```

---

## 👥 四人团队分工与成员名单

| 角色 | 负责人 (GitHub) | 负责人职责 | 核心任务与技术栈 |
| :--- | :--- | :--- | :--- |
| **角色 A：后端 Agent 工程师** | [@ovoME](https://github.com/ovoME) (项目Owner) | 智能体大脑与业务中枢 | FastAPI、LangChain、ReAct Agent 架构、6大业务工具封装、SSE流式输出、幻觉兜底 |
| **角色 B：Web 前端工程师** | [@bakashinji1204](https://github.com/bakashinji1204) | 读者端与管理端交互呈现 | Vue 3、Vite、TypeScript、Naive UI / Element Plus、ECharts、流式打字效果 |
| **角色 C：数据与算法工程师** | [@haidann](https://github.com/haidann) | 数据清洗、推荐算法与知识库 | 3.7万借阅数据清洗与画像、中图法分类与协同过滤推荐、ChromaDB RAG 向量库构建 |
| **角色 D：全栈集成与项目协调** | [@Hellan-w](https://github.com/Hellan-w) | 仓库治理、容器化与集成测试 | 仓库与分支管理、接口契约定义、Docker Compose 编排、CI/CD、答辩演示保障 |

> 📌 详细的角色实操手册与现成 Prompt 请参考 [docs/TEAM_GUIDE.md](docs/TEAM_GUIDE.md)。

---

## 🚀 快速启动指南

### 1. 克隆仓库
```bash
git clone https://github.com/ovoME/AssistantJia.git
cd AssistantJia
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 LLM_API_KEY 与模型配置
```

### 3. 一键容器化运行 (推荐)
```bash
docker compose up -d
```
启动后访问：
- 读者端与管理端 Web 界面：`http://localhost`
- 后端 FastAPI 交互式接口文档 (Swagger)：`http://localhost:8000/docs`

### 4. 本地开发模式

#### 后端启动 (Backend)
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 前端启动 (Frontend)
```bash
cd frontend
npm install
npm run dev
```

---

## 数据清洗与统计 C1

在仓库根目录运行：

```bash
python -m pip install -r data/requirements.txt
python -m data.scripts.generate_demo --rows 36908
python -m data.scripts.clean_data --input data/demo/borrow_records_demo.csv --dataset-label simulated
python -m data.scripts.analyze
python -m unittest discover -s data/tests -v
```

清洗、质量报告和统计结果写入 `data/processed/`。输入字段、真实 Excel 导入及前端字段映射见 [数据模块说明](data/README.md) 和 [C1 数据交付约定](docs/c-data-contract.md)。模拟数据和生成结果由本地命令创建。

---

## 🌿 Git 分支策略与协作规范

团队采用标准 Git-Flow 精简工作流：

1. **`main` 分支**：生产发布分支，仅存放稳定可运行版本，仅接受 Pull Request 合并，禁止直接 `git push`。
2. **`develop` 分支**：日常集成主干，所有功能开发最终合并到此分支。
3. **功能分支**：
   - 后端开发：`feature/backend-xxx`
   - 前端开发：`feature/frontend-xxx`
   - 数据/算法：`feature/data-xxx`
   - 运维/集成：`feature/deploy-xxx`

### 每日开发流程
```bash
git checkout develop
git pull origin develop             # 保持代码最新
git checkout -b feature/xxx         # 建立自己的特性分支
# 开发并测试完毕后提交
git add .
git commit -m "feat: 简要描述新增的功能"
git push origin feature/xxx
# 在 GitHub 上提交 PR 到 develop 分支，邀请队友 Review
```

---

## 📅 大赛里程碑

- **10月31日**：初赛方案及相关支撑材料提交截止
- **11月上旬**：初赛评审与入围名单公布
- **12月**：决赛答辩与现场展示演示

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。
