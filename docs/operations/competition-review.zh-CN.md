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

工具只读取已有快照，不连接券商。快照总持仓市值/NAV 是观察值，不是官方每日持仓率。同一时点冲突快照会被排除；缺失或不完整的日期保留未知。XNYS 和 XTKS 只是交易日情景，不代表官方全球账户日历。CLI 不会把快照变成完整日事实。纯函数 `daily_rows` 可接受人工核对后的比例数据，但没有任意 Flex XML 导入器。

按[主办方规则第 4.2 条](https://fundconnecthk.com/quant-league/legal/competition-rules/)，全比赛期间日均持仓率至少 50% 且累计空仓交易日不超过十天，**或**日均换手率至少 100%。日内平仓本身不等于空仓日。这影响答辩和评奖候选资格，并非普遍要求频繁调仓。已过去日期的计算不能证明全赛程资格；仍需确认官方日历、指标定义和完整日账本。

草案缺失参数保持 null。`review_decision` 只复核提供的证据：策略未确认、账户不匹配、来源缺失/过期/来自未来或时间顺序不成立时阻塞。完整合成案例可以得到维持候选或需要复核，均不授权交易。策略必须提供基准和申报/模型哈希，限额为正数，缓冲参数为非负整数。来源提供 effective_at 和 available_at，要求实际时点不晚于可用时点、不晚于决策，并按实际时点检查过期。评分须绑定 PIT/投资池/模型父哈希，目标须绑定评分父哈希。来源哈希绑定所提供的引用，不能证明语义正确或外部真实性。工具不训练或验证 Ranker、不核验 PIT 完整性，也不生成可执行目标。

提出配置建议前，需要基准、PIT 投资池和因子来源、模型、带日期评分、Top-K/进退缓冲定义、当前市值权重、风险限额、费用和汇率。价格基线不能冒充申报的基本面 Ranker。历史平均成本不能用来推断当前权重。平台采集与本地采集的新鲜度应分别检查；申报锁定期间的变更按主办方流程处理。
