# Dopamine Cloud Lite V1.0.2

三账号独立业务数据空间 · 可互相只读查看 · 确认后复制覆盖自己的数据。

**与旧版 Dopamine Pricing Web V8 本地版独立共存，不影响其 localStorage 数据。**

## 账号与权限

- 炮台 → `admin01`
- 芋头 → `admin02`
- EE → `admin03`

登录密钥仍使用 V1.0.1 的三组密钥，不修改 Worker `KEY_PEPPER`、不重新导入 users 或 sessions。

每个账号只能修改自己的业务数据。Worker 服务端的 `/api/state` 写入只绑定登录身份，不允许指定其他 `owner`；跨账号只读 GET 可以用 `/api/state?owner=admin02`。同步用 `POST /api/state/sync` 并传 `{ "source": "admin02" }`，只更新当前登录账号。数据库只有一个 `account_documents` 表，每个账号对应独立一行。

## 必须先迁移 D1

**在提交新代码触发自动部署前**，先从现有 V1.0.1 备份 JSON，再到 D1 Console 执行：

- `docs/sql/V1.0.2_D1_Console_初始化.sql`
- `docs/sql/V1.0.2_D1_Console_核验.sql`

确认结果有三个账号行之后再把 ZIP 内容上传 GitHub。

详细步骤：[`docs/V1.0.2_升级部署与验收.md`](docs/V1.0.2_升级部署与验收.md)。

## 主要功能

- 沿用 V8.0.4 产品、组合、套餐、附加费用、折扣利润及 BigInt 高精度算法。
- 每个人维护自己的产品和项目，不会因另一个账号保存而覆盖。
- 顶部「数据空间」可以切换为其他账号；他人数据仅能查看、浏览及导出 JSON。
- 查看他人时「同步到我的数据」需要危险操作确认，**覆盖整个自己的数据空间**，而不是按产品追加或合并。复制对方已保存的数据，源账号不受影响。
- 本人仍然每 5 分钟自动保存改动并刷新；只读查看他人时每 5 分钟只刷新、不保存。
- 关闭标签仅在未保存时显示浏览器原生提醒，不发送静默保存请求。
- JSON 导入/导出兼容本地 V8.0.4（手动文件传输，不是双向实时同步）。

## 命令

```bash
npm install
npm run check
npm run dev
npm run deploy
```

首次从 V1.0.1 升级的生产数据库应按文档先使用 D1 Console 执行迁移，不能仅上传 ZIP 而忽略数据库表。

## 设计和限制

- 旧 `shared_document` 仍完整保留，可作为迁移前历史快照；数据迁移一开始为三人分别克隆该快照。
- 一账号跨设备同时编辑仍按 Last Write Wins，无编辑锁、无历史版本回退。
- 同步到自己会丢弃自己当前保存的所有项目内容，建议先导出个人 JSON 备份。
- 共享源数据为空时不能执行覆盖同步。
- 需要真实 Cloudflare 部署后验收；`workers.dev` 在中国大陆的网络可达性不能保证。

查看具体更新：[`docs/版本变更_V1.0.2.md`](docs/版本变更_V1.0.2.md)。
