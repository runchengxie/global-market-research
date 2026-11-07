# 加密因子来源复核

[English](crypto-factor-provenance.md) · [加密研究](crypto-evidence.zh-CN.md)

目前能核实两个指标的文字定义，但历史首次发布时间仍未核实。已保留的日频快照可以用于探索性代理对齐，尚不足以支持严格时点可得的情绪交易结论。

| 指标 | 当前公开文档的含义 | 仍缺少的证据 |
| --- | --- | --- |
| CO-A-02-03 | 正面与负面情绪占比之差 | 历史计算方法及版本、首次发布时间 |
| CO-S-01-01 | 当前情绪相对历史常态的标准化偏离 | 标准化窗口、历史版本、首次发布时间 |
| CO-S-01-05 | 本轮未独立核实定义 | 定义、版本、首次发布时间 |

2026年11月7日查阅：[官方CO-A-02-03](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/api-list/co-real-time-data/indicators/co-a-02-03)、[官方CO-S-01-01](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/api-list/co-real-time-data/indicators/co-s-01-01)及[官方目录](https://cryptoracle.gitbook.io/cryptoracle-docs/co-indicator-repository)。当前页面跳转至名称含`co-private-data`的文档路径；读取的是公开文档，没有调用私有API或使用凭证。示例支持日频请求，返回周期开始和结束时间，但这不等于首次发布、获取或修订时间，也没有由此证明UTC含义。目录中部分指标列出更细更新频率，并不能证明我们的权限或当前快照拥有该粒度。

本轮通过文档浏览服务取得上述证据。另有四次有额度限制的直接文档下载返回HTTP错误，失败记录已经保留，没有伪称已下载源文档归档。没有调用供应商数据API。当前归一化快照只有资产、指标、周期开始/结束和值；增加延迟无法补出缺失的历史发布时间。因此24/72/192小时对齐仍是假设。

下一步需要供应商拥有并版本化的数据约定：指标公式及版本、周期边界与时区、首次可用时间、修订规则、获取时间与原始响应摘要。未来逐次记录首次见到的数据，可以证明未来可用性，但不能倒推出旧数据当时可得。在此之前，前瞻预测继续只用价格，严格历史因子组保持阻塞。
