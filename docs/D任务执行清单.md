# D（全栈/集成协调）任务执行清单

> 角色：**Hellan-w** ｜ 本分支：`feature/deploy-d`（基于 `origin/develop`）
> 状态口径：✅ 已合入仓库 / 🟡 本 PR 提交 / ⏳ 待 D 人工 / 📋 待团队配合

## 一、D 主责（方案 2.2）

仓库治理、容器化与集成测试、CI/CD、接口契约定义、答辩演示保障。

## 二、任务 → 交付对照（截至本 PR）

| 方案出处 | D 的任务 | 产物/位置 | 状态 |
| --- | --- | --- | --- |
| 步骤2 | 仓库与分支管理 | main / develop / feature/* 已按 Git-Flow 建立；本分支 feature/deploy-d | ✅ |
| 步骤2 | Docker Compose 编排（后端/前端/Redis/Chroma） | `docker-compose.yml`（根，一键启动）+ `deploy/docker-compose.yml`；本 PR 补齐 healthcheck 与依赖条件 | 🟡 已完善 |
| 步骤2 | 前端容器化（多阶段 + Nginx 托管） | `frontend/Dockerfile` + `frontend/nginx.conf`（/api 反代 + SSE 关闭缓冲） | 🟡 新增 |
| 步骤2 | CI 流水线 | `.github/workflows/ci.yml`（后端测试/前端构建/镜像校验/集成测试） | 🟡 新增 |
| 步骤8 | 生产部署流水线 | `.github/workflows/deploy.yml`（GHCR + SSH 自动部署） | 🟡 新增 |
| 步骤8 | 端到端测试 | `tests/e2e/`（conftest + 8 个契约场景 + locust 压测） | 🟡 新增 |
| 步骤8 | 安全检查 | `docs/安全与权限检查清单.md` | 🟡 新增 |
| 步骤8 | 部署文档 | `docs/部署手册.md` | 🟡 新增 |
| 协作机制 | 接口先行 | 契约以 `docs/api-contract.md` 为准（A 实现、B 对齐已完成） | ✅ |
| 步骤1 | 确认服务器（配置/SSH/Docker） | 部署手册第一节清单 | ⏳ 待 D 人工 |

## 三、D 仍需自己完成的人工事项

1. **服务器确认**：申请/确认云服务器，安装 Docker，登记 IP/SSH/配置。
2. **配置 Secrets**：仓库 Settings → Secrets 配置 `DEPLOY_HOST` / `DEPLOY_USER` / `DEPLOY_SSH_KEY` / `GHCR_PAT`（deploy.yml 需要）。
3. **推进合并**：本分支 PR → develop 评审；A/B 分支尽快合入，避免集成冲突。
4. **周末集成主持**：每周合并 develop 跑 E2E，出问题群里同步。
5. **答辩保障**：准备演示脚本、测试账号、典型场景（10月31日初赛材料截止）。

## 四、D 验收标准（方案 2.3）

- [ ] `docker compose up` 一键启动全栈，四服务 healthy
- [ ] CI 绿勾（后端/前端/镜像/集成四类任务）
- [ ] 部署文档齐全（部署手册、安全清单、接口契约）

## 五、遗留与风险提示

- A 的 `feature/backend-init` 尚未合入 develop：其 `backend/Dockerfile` 与 tests 合入后，CI 的 backend 任务与集成任务才会真正跑满；当前 CI 已做容错跳过。
- 管理端鉴权方案待团队确认（建议 `X-Admin-Token`），确认后需 A 在 `admin.py` 落地。
- CORS 当前为 `allow_origins=["*"]`，上线前须收紧（见安全清单）。
