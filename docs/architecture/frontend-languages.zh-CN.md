# 前端语言边界

[English](frontend-languages.md)

序列研究的新增业务模块使用 TypeScript，原有合成摘要校验/图表与新增实测结果校验、图表、控制器一并迁移。`npm run build` 先对 `src/lib/sequence-*.ts` 和 `src/scripts/sequence-*.ts` 运行严格的 `tsc --noEmit`，再构建 Astro。这是渐进迁移，不表示全部旧 JavaScript 或 `.astro` 文件已经获得完整类型覆盖。JSON 输入仍须运行时校验。

使用 Node24.12 或更新版本。单元和浏览器测试保留 `.mjs`；Node 原生类型剥离执行导入的 `.ts`，独立编译器负责类型检查。测试核对公开数值、拒绝私有/原始序列，并验证语言、无脚本、主题和手机交互。锁文件固定 TypeScript7.0.2。Astro 能转译 TypeScript，不等于自动检查类型，参见 [Astro TypeScript](https://docs.astro.build/en/guides/typescript/) 与 [Node TypeScript](https://nodejs.org/api/typescript.html)。

现有模型、数据和账本继续使用 Python，本轮不引入 Java 应用服务。独立管理的 IBKR Gateway Java 运行时，不构成把 Python 研究或执行模块改写为 Java 的理由。以后确有可测量的常驻服务需求，再单独设计部署、责任和语言选择。

站点私有包及临时浏览器测试输出统一采用 `global-market-research` 名称，不改变历史研究 schema、供应商身份或已消耗的数据预算。
