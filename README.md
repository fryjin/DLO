# Dopamine Cloud Lite V1.0 — 独立云端协作版

**与 Dopamine Pricing Web V8.0.4 本地版完全隔离。** 本仓库是新的 GitHub/Worker/D1 部署单元，不应上传至旧仓库或旧 Cloudflare 项目。

## 能做什么

- 沿用已验收的 V8.0.4 高保真界面、产品/组合/套餐/费用/折扣、BigInt 12 位精度及批量多行粘贴。
- **三名固定账号** `admin01`、`admin02`、`admin03`，权限完全相同。只有部署人员在本机生成随机登录密钥，云端只保存基于 Worker `KEY_PEPPER` 的 HMAC-SHA256 摘要。
- 单一 D1 数据库中保存一份共享的业务 JSON 文档，三个账号看到相同项目集合。
- 显式保存、5 分钟自动保存（有更改才写入）和每 5 分钟获取最新云端数据；最新保存覆盖旧文档（Last Write Wins）。
- 关闭标签：仅在 dirty 时浏览器原生离开警告，不自动保存。**浏览器安全限制使关闭标签时无法弹三按钮对话框并等待网络保存。** 点击应用内「退出登录」可选择「保存并退出 / 不保存退出 / 继续编辑」。
- 本地 V8 JSON ↔ Cloud Lite JSON 互导：导出备份、恢复备份（导入后**需点击保存**才能同步到 D1）。

## 安全与限制

- 不开放注册、无邮箱/短信验证、无管理员角色、无编辑锁。
- 只有一个共享数据文档。任何用户的**整份保存**都会覆盖整个 D1 文档，包括另一个账号刚保存的其他项目修改。该行为是用户明确选择的「最后保存者获胜」；本版本不提供项目级合并/撤销记录。
- 自动保存只在浏览器正在运行、请求成功的情况下生效。电脑睡眠时无运行能力。
- 如果账号 1 正在输入，账号 2 保存了新版本，前端会推迟刷新当前编辑区域；如随后账号 1 执行保存，其旧快照将覆盖账号 2 的修改。建议三个账号避免同时编辑同一项目，尤其不同项目也共用一份文档。
- D1 单行数据遵守本工具 **850 KB UTF-8** 上限。未来超过时需升级为按项目分表/多行存储，不能直接修改前端限制。
- 本版本依赖 Cloudflare `workers.dev` / Worker 网络可达性，**中国大陆无法保证稳定访问**；需实际在目标网络验收，不能把部署成功等同大陆访问成功。
- Cloudflare Free 有请求数、D1 读写和存储上限，超额可能出现错误或需要升级；此版本在免费限额内使用，无强制付费依赖。
- JSON 数据为经营数据，不要将 `.private`、`.dev.vars`、业务备份、登录密钥提交到 GitHub。

## 一次性部署（新仓库 / 新 Worker）

详情见 [`docs/部署说明.md`](docs/部署说明.md)。

```bash
npm install
npx wrangler login
npx wrangler d1 create dopamine-cloud-lite
# 将终端返回的 database_id 填写到 wrangler.jsonc
npm run db:migrate:remote
npm run credentials:create
# 读取 .private/login-credentials.txt 的 KEY_PEPPER；设置：
npx wrangler secret put KEY_PEPPER
# 输入/粘贴 KEY_PEPPER（不要提交文件）
npx wrangler d1 execute dopamine-cloud-lite --remote --file=.private/seed-users.sql
npm run deploy
```

如果之前在同个数据库生成过账号，再运行 `credentials:create` 会**轮换三个人的密钥**，旧密钥立即失效；已创建的会话未自动失效，如需吊销执行 SQL 删除 sessions 表数据。

## 本地验证

```bash
npm test
npm run build
node --check app.js
node --check src/worker.js
```

`npm run dev` 使用 `wrangler dev` 模拟 Worker/D1，需先安装 Wrangler 且在本地配置 D1 migration 和登录密钥。运行时没有第三方 CDN。

## 数据互通

- Local V8.0.4 → Cloud：在本地版点「导出备份」→ 保存 `*.json` → Cloud 版登录 →「数据管理 → 恢复备份」→ 检查 → 点击「保存」。
- Cloud → Local：Cloud 版点「导出备份」→ Local V8.0.4「恢复备份」→ 检查 → 保存。
- 这属于**手动整体替换**，不是双向实时同步，也不支持合并。
- 两边使用同一业务 `version:4` JSON 结构，Cloud 使用独立 D1，不读取本地浏览器旧 key。

## 架构

```
新 GitHub 仓库
    ↓ 部署
Cloudflare Worker（静态资源 + /api/*）
    ├── Three fixed users / secure session cookie
    └── D1 shared_document（单份 JSON）

本地独立 V8.x：原 GitHub + Pages + localStorage，不受影响
```

R2、独立 Pages 服务、邮件、短信、自动更新、实时编辑和权限管理均不是一期需要。

## 本次交付验证边界

已执行：`node --check`、`node --test`、纯前端构建及 Chromium DOM 登录/产品编辑/云端保存/退出的模拟 API 冒烟测试。

**尚未执行真实 Cloudflare 远端部署、真实 D1 数据库事务或目标大陆网络联通性验收。** 由于当前运行环境外部 npm 包安装超时，未运行 Wrangler 本地模拟器；部署完成后须按部署说明进行实际三账号验收，再正式用于重要业务数据。
