# 比赛策略私有复核

[English](competition-review.md)

先在 Git 仓库之外保存申报证据，再对照有日期的策略实现和账户记录。策略名称不能证明具体实现；用户粘贴的平台文本应注明来源，不能算独立核验。

安装 `daily-data` 可选依赖后运行离线盘点：

```bash
python -m competition_tools.competition_review.cli \
  --declaration-root "$DATA_ROOT/global-market-research/operations/competition-declaration/<record>" \
  --snapshot-root "$DATA_ROOT/global-market-research/operations/account-dashboard" \
  --output "$DATA_ROOT/global-market-research/research/competition-review/<new-run>"
```

申报目录包含 declaration.json、declaration.md、declaration.zh-CN.md，以及记录这三个文件 SHA-256 的 receipt.json。保存前移除凭据和账户标识。结果仅写入新建私有目录并封存；校验值能发现后续改动，不能证明原始内容真实。

工具只读取已有快照，不连接券商。快照总持仓市值/NAV 是观察值，不是官方每日持仓率。同一时点冲突快照会被排除；缺失或不完整的日期保留未知。XNYS 和 XTKS 只是交易日情景，不代表官方全球账户日历。不提供 `--statement-bundle` 时，CLI 不会填入完整日事实。可选规范化账本支持人工核对后的比例和来源记录，但没有任意 Flex XML 导入器。

按[主办方规则第 4.2 条](https://fundconnecthk.com/quant-league/legal/competition-rules/)，全比赛期间日均持仓率至少 50% 且累计空仓交易日不超过十天，**或**日均换手率至少 100%。日内平仓本身不等于空仓日。这影响答辩和评奖候选资格，并非普遍要求频繁调仓。已过去日期的计算不能证明全赛程资格；仍需确认官方日历、指标定义和完整日账本。

草案缺失参数保持 null。`review_decision` 只复核提供的证据：策略未确认、账户不匹配、来源缺失/过期/来自未来或时间顺序不成立时阻塞。完整合成案例可以得到维持候选或需要复核，均不授权交易。策略必须提供基准和申报/模型哈希，限额为正数，缓冲参数为非负整数。来源提供 effective_at 和 available_at，要求实际时点不晚于可用时点、不晚于决策，并按实际时点检查过期。评分须绑定 PIT/投资池/模型父哈希，目标须绑定评分父哈希。来源哈希绑定所提供的引用，不能证明语义正确或外部真实性。工具不训练或验证 Ranker、不核验 PIT 完整性，也不生成可执行目标。

提出配置建议前，需要基准、PIT 投资池和因子来源、模型、带日期评分、Top-K/进退缓冲定义、当前市值权重、风险限额、费用和汇率。价格基线不能冒充申报的基本面 Ranker。历史平均成本不能用来推断当前权重。平台采集与本地采集的新鲜度应分别检查；申报锁定期间的变更按主办方流程处理。

## 已复核的每日账本

增加 `--statement-bundle /external/inputs/bundle.json` 可纳入明确复核过的导出。规范化 JSON 的 schema 为 `competition.statement_bundle.v1`，必填字段如下。

| 字段 | 含义 |
| --- | --- |
| `declaration_sha256`、`account_ref`、`base_currency` | 已保存申报文件的哈希、账户代号及三字母本位币 |
| `rate_unit`、`reviewed_by` | 单位必须为 `fraction`；记录复核者，不代表认证签名 |
| `sources` | 非空 `{id, path, sha256}` 列表；相对路径必须位于账本所在目录之内 |
| `calendar` | `{id, status, full_period, period_start, period_end, source_ids, sessions}`；status 为 `unconfirmed` 或 `organizer_confirmed`，full_period 必须为 true |
| `calendar.sessions` | 有序且不重复的 `{session_date, opens_at, closes_at}`；带时区，窗口不重叠，位于比赛期间内 |
| `definitions` | `position_rate`、`turnover_rate`、`flat_day` 各提供 `{status, description, source_ids}` |
| `days` | 不重复的已结束交易日标签，以及 `complete_day`、比例或 null、`had_any_position`、`had_any_trade`、`covered_through`、`available_at`、`source_ids` |

完整比赛区间为 2026-10-25T16:00:00Z 至 2027-01-26T22:00:00Z。完整日声明必须覆盖对应收盘时点，且证据在复核时已可用。部分日保持未知；缺失交易日也保留在已过去日期的范围中，不会被删除。杠杆账户比例可以超过 1，但此时不计算无杠杆未来持仓情景。逐日覆盖的账户或币种字段必须与账本一致。创建新结果目录前，工具核对所有来源文件哈希。日历完整性、指标定义和复核者身份仍是来源方声明；工具不会独立认证 `organizer_confirmed`，也不会据此认定评奖资格。

可将 `--policy /external/policy.json --decision-inputs /external/decision-inputs.json` 成对传给现有每日复核器。两份文件必须绑定已保存申报的哈希；若同时提供账本，账户代号也须一致。这只检查提供的权重和因果来源引用，不重建券商持仓或 Ranker 输出。结果包含 `policy-review.json`，没有这组参数时保留 `policy-draft.json`。双语报告和 audit.json 会反映实际输入的账本及复核状态。

## 导出和恢复顺序

1. 获取主办方完整日历、持仓/换手定义、空仓日处理方式和每日评分导出。保留原文件及获取时间，私下确认账户绑定。
2. 获取覆盖完整已过去期间的只读 [IBKR Activity Flex 报告](https://ibkrguides.com/reportingreference/reportguide/activity%20flex%20query%20reference.htm)：Trades、Cash Transactions、NAV Summary in Base，以及对账所需的 Open Positions 市值/汇率字段。可用字段取决于查询配置；Token 和登录信息不进入账本。
3. 对齐本位币净值、持仓市值、总成交额、成交/费用、出入金和日期覆盖。仅凭日末零持仓不能确定空仓日，还要看日内活动和结转持仓。不能根据现有列自行发明主办方公式。
4. 由复核者准备带来源哈希和定义的规范化账本。未解决定义保留 unconfirmed；文件校验记录不能证明数据正确。
5. 写入新的私有目录，与上次封存报告比较覆盖和阻塞项。具备当前市值和申报模型证据后，再判断配置调整。

实现盘点要区分数据下载断点、价格/CNN 研究、合成测试和训练好的基本面 Ranker。保留搜索范围与排除项；没有搜到某个文件名，不代表团队其他成员一定没有相应实现。
