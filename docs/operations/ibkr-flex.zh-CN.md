# IBKR Flex 只读报表

[English](ibkr-flex.md) · [比赛复核](competition-review.zh-CN.md)

Flex 用 Current Token 和 Query ID 读取预先保存的报表查询，每次获取不需要 TWS/Gateway 或券商登录。它提供账单数据，不是实时持仓流。[IBKR 配置说明](https://www.interactivebrokers.com/docs/web-api/flex-web-service/client-portal-configuration)

在 `CONFIG_ROOT/projects/global-market-research/ibkr-flex.json` 保存唯一私有配置，位于 Git 外；POSIX 权限为 0600，Windows 使用对应的仅所有者 ACL：

```json
{
  "token": "",
  "query_id": "",
  "expected_account": "",
  "account_ref": "competition-paper",
  "base_currency": ""
}
```

Token 和 Query ID 按字符串填写，保留引号。`account_ref` 为报告代号。账户尚未填写时可以先发现报表元数据；正式采集需要明确的完整预期账户。本位币可在来源元数据确认前留空；未知币种保持未知，不会自动换汇或生成净值权重。配置后，账户或币种不匹配会阻塞采集。工具不生成/重置 Token，也不修改查询模板；关联账户范围取决于 Query 的账户选择。[Token 范围说明](https://www.interactivebrokers.com/docs/web-api/flex-web-service/client-portal-configuration/enable-and-create-access-token)

## 配置报表

使用 **Activity Flex Query，输出 XML**。持仓需要 Open Positions 的 **Summary** 明细，包含 Account ID、Report Date、Symbol/Conid、Currency、Quantity、Mark Price、Position Value、Multiplier、FX Rate to Base。Account Information 只需账户 ID 和本位币 Currency。对账还需 Trades、Cash Transactions、NAV Summary in Base；Corporate Actions、现金余额和换汇记录有助于完整复核。字段和账户在 Client Portal 中选择，CLI 不编辑查询。

[Open Positions 字段](https://ibkrguides.com/reportingreference/reportguide/open%20positionsfq.htm) 区分 Summary 与 Lot。解析器不会把 LOT、ORDER、标的汇总和成交明细相加。持仓市值保留来源字段，不擅自换算；券商 Percent of NAV 字段也不能直接当成全账户权重。

## 手动运行

使用锁定依赖安装根包，或使用保留的发布 wheel。以下命令不创建定时任务：

```bash
python -m competition_tools.competition_review.flex_cli check-config \
  --config "$CONFIG_ROOT/projects/global-market-research/ibkr-flex.json"
python -m competition_tools.competition_review.flex_cli discover \
  --config "$CONFIG_ROOT/projects/global-market-research/ibkr-flex.json" \
  --output "$DATA_ROOT/global-market-research/operations/ibkr-flex/<new-discovery>"
python -m competition_tools.competition_review.flex_cli collect \
  --config "$CONFIG_ROOT/projects/global-market-research/ibkr-flex.json" \
  --from-date 2026-10-26 --to-date 2026-11-06 \
  --output "$DATA_ROOT/global-market-research/operations/ibkr-flex/<new-collection>"
python -m competition_tools.competition_review.flex_cli inspect \
  --config "$CONFIG_ROOT/projects/global-market-research/ibkr-flex.json" \
  --report /external/prior-report.xml \
  --output "$DATA_ROOT/global-market-research/operations/ibkr-flex/<new-inspection>"
```

发现模式仅保存私有账户/币种/区间元数据，不保存未绑定的原始报表或持仓。Inspect 不联网。起止日期须成对提供，否则采用已保存查询的期间。检查返回区间及逐行日期：请求了某段日期不代表已经覆盖每天。历史复核优先使用已结束的报表日。

客户端仅使用固定 HTTPS SendRequest/GetStatement 端点及 v3，忽略返回 URL，拒绝重定向，限制响应大小和轮询次数。只发起一次生成请求，获取时每次间隔十秒；网络、认证、权限错误会停止，不切换凭据、不立即重试 HTTP 限流错误。避免同一 Token 的并发进程，并考虑其他消费者的请求。[生成](https://www.interactivebrokers.com/docs/web-api/flex-web-service/using-flex-web-service/generate-the-report) · [获取](https://www.interactivebrokers.com/docs/web-api/api-reference/get-statement)

成功结果包含原始 `report.xml`、`observation.json`、`ledger.json`、不含凭据的 receipt 及 seal。新目录为 0700、文件为 0600，已有目录不覆盖。失败只保存脱敏错误码，不记录原始错误文本或含凭据的 URL。封存能发现文件改动，不能独立认证来源。完整账户号仅保存在授权的私有原文/发现结果中，不显示在 CLI 摘要里。以后若单独授权定时运行，使用版本化安装，不使用临时 worktree。

## 账本能说明什么

账本分别统计唯一**成交记录**和券商订单标识，一笔订单可能分成多笔成交。按 conid 区分合约，缺少身份时标记问题，成交日期须位于对应报表期间；相同 ID 的重复记录去重，冲突 ID 阻塞；涉及冲正或非标准成交时需要另行复核。手续费按币种保留，现金流水按 transaction ID 去重。股票敞口代理是所提供报表日期中的股票总市值/NAV，不是官方每日持仓率；缺失净值日期不填补。未经官方公式和日历复核，不把该代理映射到规范账本的正式持仓率字段。

没有 Open Positions 表示缺少持仓证据，不是零持仓。缺少期初余额、公司行动和完整覆盖时，成交无法证明期初或当前持仓。期末持仓不能证明每日历史或空仓日；净值变动也不直接等于剔除资金流后的策略收益。报告不生成目标、订单或交易授权。确认来源、定义和账户绑定后，再进入[私有复核](competition-review.zh-CN.md)。

## 观察到的股票与现金快照

采集和离线检查还会生成 `snapshot.json`；receipt 和 CLI 摘要单列 `reconciliation_status`，区分读取成功与估值对账通过。它选择股票/NAV 观察值的最新日期，要求净值在同一天，不退回较早但恰好匹配的日期。先核对数量×价格×乘数与当地币种持仓市值，再用行内明确汇率换算，并与 NAV 股票净值/总市值核对；通过后才输出观察到的权重，不是目标仓位。LOT 不重复计算。缺身份/价格、模型范围含糊或市值不符时阻塞股票权重。

现金仅使用 Currency 级别、明确截止日期匹配的 CashReportCurrency，BASE_SUMMARY 不与各币种明细相加。保留负余额。仅用同日“来源币种→本位币”的 ConversionRates，不反推、不串联、不沿用旧汇率。换算现金与 NAV 现金核对。NAV 桥接单列股票、现金、应计利息、应计股息及差额；未覆盖的非零资产即使正负抵消也保留可见。这是指定组成部分的对账，不是通用会计引擎。

固定容差为：当地币种市值 0.01 单位，本位币总额/桥接 0.02 单位，持仓汇率与汇率表一致性为 1e-8×max(abs(FX),1)。原值和差额保留供检查；容差不是经济风险限额。缺表、尚未支持的纯现金账户或模型范围得到 needs_review，不伪造零持仓。对账通过不代表完整每日历史、实时持仓、平台绑定或官方资格已认证，也不生成订单。BreakoutByDay=No 的区间报表期末持仓，不能描述为完整每日持仓历史。

选择最新日期前先检查原始持仓行，不因字段缺失丢掉最新日期。当前 Summary 不完整时阻塞股票权重；不支持的持仓行和来源检查问题保持可见，即使对应 NAV 字段缺失或为零。正常排除 LOT 与未覆盖风险分开记录。
