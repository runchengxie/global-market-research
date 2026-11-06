# Frontend language boundary

[简体中文](frontend-languages.zh-CN.md)

New sequence-research business modules use TypeScript, including the existing synthetic summary validator/chart and the new measured-result validator, chart and controller. `npm run build` first runs strict `tsc --noEmit` over `src/lib/sequence-*.ts` and `src/scripts/sequence-*.ts`, then builds Astro. The scope is an incremental migration, not a claim that all legacy JavaScript or `.astro` files have full type coverage. Runtime projection validation remains necessary for JSON inputs.

Use Node24.12 or newer. Unit and browser test files remain `.mjs`; Node's native type stripping executes imported `.ts` modules, while the separate compiler performs type checking. Tests assert published values, reject private/raw series and verify locale, no-JavaScript, theme and mobile behavior. TypeScript7.0.2 is pinned in the lockfile. Astro's built-in transpilation alone does not check types; see [Astro TypeScript](https://docs.astro.build/en/guides/typescript/) and [Node TypeScript](https://nodejs.org/api/typescript.html).

Keep Python for existing models, data and accounting. This task introduces no Java application service. The separately managed IBKR Gateway Java runtime does not require rewriting Python research or execution modules in Java. Reconsider service language only for a measured operational requirement, with an independent deployment/ownership design.

The private site package and temporary browser-test output use the `global-market-research` name. This changes no historical research schema, provider identity or consumed data budget.
