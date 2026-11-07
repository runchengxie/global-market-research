# Frontend language boundary

[简体中文](frontend-languages.zh-CN.md)

New sequence-research business modules use TypeScript, including the existing synthetic summary validator/chart and the new measured-result validator, chart and controller. `npm run build` first runs strict `tsc --noEmit` over `src/lib/sequence-*.ts` and `src/scripts/sequence-*.ts`, then builds Astro. The scope is an incremental migration, not a claim that all legacy JavaScript or `.astro` files have full type coverage. Runtime projection validation remains necessary for JSON inputs.

Use Node24.12 or newer. Unit and browser test files remain `.mjs`; Node's native type stripping executes imported `.ts` modules, while the separate compiler performs type checking. Tests assert published values, reject private/raw series and verify locale, no-JavaScript, theme and mobile behavior. TypeScript7.0.2 is pinned in the lockfile. Astro's built-in transpilation alone does not check types; see [Astro TypeScript](https://docs.astro.build/en/guides/typescript/) and [Node TypeScript](https://nodejs.org/api/typescript.html).

Keep Python for existing models, data and accounting. This task introduces no Java application service. The separately managed IBKR Gateway Java runtime does not require rewriting Python research or execution modules in Java. Reconsider service language only for a measured operational requirement, with an independent deployment/ownership design.

Java is a candidate for a future resident market-data or execution service if measured requirements justify it: many concurrent feeds, bounded queue backpressure, durable restart recovery, or multiple consumers of one typed API. A finer candle interval alone is not evidence that Python is inadequate. Benchmark representative feed replay, queue growth, tail latency, memory and recovery before choosing a language. Java virtual threads target I/O concurrency and throughput rather than inherently reducing latency ([Oracle documentation](https://docs.oracle.com/en/java/javase/22/core/virtual-threads.html)). IBKR supports both Java and Python, so broker access alone does not decide the language ([IBKR API documentation](https://www.interactivebrokers.com/docs/)).

If such a service is justified, keep one authoritative order lifecycle and connect it to research through the existing versioned file/API contracts. Do not duplicate risk/accounting rules in two runtimes. Start with an offline replay comparison and an explicit service boundary; no new broker connectivity or order authorization follows from this language assessment.

The private site package and temporary browser-test output use the `global-market-research` name. This changes no historical research schema, provider identity or consumed data budget.
