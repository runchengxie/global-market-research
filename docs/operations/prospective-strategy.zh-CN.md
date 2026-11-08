# 面向未来的策略与影子观察

[English](prospective-strategy.md) · [比赛证据复核](competition-review.zh-CN.md)

先写清实际准备执行的策略，再记录决策，最后评价之后的观察。当前持仓和平台策略名称都不能证明已经存在训练好的 Ranker 或已批准的风险预算。这些手动工具只保存私有离线证据，不启动交易、定时任务或平台修改。

## 草案与记录

沿用已绑定申报和 Flex 对账快照的[实际文件复核 case](competition-review.zh-CN.md)：

```bash
python -m competition_tools.competition_review.shadow_cli prepare \
  --case /external/case.json --output /external/new-charter
python -m competition_tools.competition_review.shadow_cli record \
  --case /external/case.json --output /external/new-entry
python -m competition_tools.competition_review.shadow_cli nav \
  --snapshot /external/sealed-flex-bundle --output /external/new-nav-bridge
```

输出必须是新的仓库外目录，不能与输入证据重叠。工具封存结果并限制 Unix 权限。封存只能检测变化，本机时钟不是独立认证的时间戳。CLI 不提供回填历史时间的选项；`record` 使用当前 UTC，并单列持仓报表日期。证据阻断不等于决定继续持有。可以在取得新完整报表并复核策略后手动运行；工具不会安装定时任务。

草案把方法、基准、目标权重、风险限额、复核日历/责任人和确认信息留空。确认前写清投资范围、配置理由、个股/行业/总仓位上限、现金与汇率处理、换手与费用限制、复核触发和暂停条件。观察权重仅作描述。如果申报的基本面 Ranker 已存在，恢复其输入、模型和带日期评分；否则如实记录面向未来的实际策略，遵循平台锁定与主办方变更流程，不补写历史理由。工具不会自动把草案变成 case 中的已确认策略。

## 后续配对观察

对未阻断的记录，提供仓库外 JSON，schema 为 `competition.shadow_outcome.v1`：

| 字段 | 含义与约束 |
| --- | --- |
| `decision_sha256` | 已封存记录中 decision.json 的 SHA256 |
| `account_ref`、`base_currency` | 与原记录完全相同的账户代号、币种 |
| `start`、`end`、`available_at` | 带时区，满足记录时间 ≤ 开始 < 结束 ≤ 可得 ≤ 评价时间 |
| `returns` | 原当前/目标 conid 的精确并集；每项为同币种有限、有符号、不小于 −1 的总收益小数 |
| `non_stock_return`、`benchmark_return` | 同区间、同币种的所提供总收益小数，有限且不小于 −1 |
| `one_way_cost_bps` | 有限、非负、不超过 10000 基点的初始单边线性股票交易费用假设 |

```bash
python -m competition_tools.competition_review.shadow_cli evaluate \
  --entry /external/sealed-entry --outcome /external/outcome.json \
  --output /external/new-comparison
```

原目标文件必须仍与记录哈希一致。仅支持股票权重非负、各方案总和不超过 1。计算假设区间起点持有记录中的权重，以证券收益和剩余非股票部分的收益加权；目标方案另扣初始 `sum(abs(target−current)) × cost_bps/10000`。展示配对差值和相对基准结果。剩余部分含现金/应计项目，不是实际可用资金。这是单区间假设计算，不是券商业绩、执行回放或多期回测；未模拟成交、资金流、税、非线性冲击、融资、持续再平衡和期末清仓费用。收益和时间仍来自所提供声明。一次有利结果不足以证明优越，重叠区间不能当成独立样本。先冻结数据、费用、基准、时间和选择规则，再积累多个配对样本外区间，评估不确定性时保留时间依赖。未来观察缺失时继续保留缺失。

## 解释报表净值变动

`nav` 验证 Flex 封存和原始哈希，重算持仓，并把 ChangeInNAV 期末净值与同日报表快照比较。仅支持账户、本位币和区间明确的一个 MTM 模式记录，以本位币绝对 0.02 为容差核对带符号分项，并展示缺项。不支持的模式、未知非零字段、冲突或剩余差额会在输出前报错；相同重复记录不重复相加。TWR 保留原始值，不重算、不猜单位。

[IBKR Change in NAV 说明](https://www.ibkrguides.com/reportingreference/reportguide/changeinnav_fq.htm)区分损益模式并解释 MTM、汇率等字段。工具只核对列示字段的算术，不声称已独立分离经济意义上的股价和汇率损益。MTM 可能包含汇率影响，单列汇率字段也不等于全部汇率归因。不要把其他栏目中的手续费、现金和 MTM Performance 再加一次。入账利息及应计变化可能对应其他经济期间。完整股价/汇率归因还需要日期一致的数量、价格、汇率、资金流与交易账本，并在统一时间网格上对账；本工具不作此声称。

## 三条研究路径分开推进

| 路径 | 下一步证据 | 边界 |
| --- | --- | --- |
| 比赛 | 前瞻策略、与申报一致的模型链、账户市值、配对影子区间 | 不自动交易、不认证参评资格 |
| 加密货币 | 价格/情绪的可得时间与覆盖、实际成本、场所/产品、简单价格基线与去掉情绪的对照 | 更细 K 线不自动增加独立样本；研究不授权比赛品种 |
| MoE | 参数接近的单模型、固定等权/普通集成对照、路由诊断、多种子和多个前推区间 | 架构解释和合成示例不等于策略业绩 |

先确定研究问题和验收协议，再选择结果。各研究子包保留各自的数据、时间和记账假设，根工具通过文件读取结果，不导入研究实现。转入执行需要独立的证据与交接审查，不能凭研究目录名称或一张好看的图决定。

若准备后续评价，case 必须事先包含 `shadow_window: {start, end}`，时间带时区且开始不早于记录。记录冻结这个区间、已核验策略的基准和 case 的单边费用假设；outcome 的开始/结束、`benchmark` 标识和费用必须一致。未登记区间仍可保存日记，但不能评价，避免看到结果后挑选区间和基准。

现有[加密货币后续研究](../research/crypto-followup.zh-CN.md)已有 39 次拟合的回顾比较：学习型稠密路由的平均预测能力没有超过参数匹配/等权对照。六份回执的前向审计明确截至 2026-11-07，不是实时监控。下一项有用探索是按冻结的生产器审计后续保留的观察，以及补齐供应方的历史发布时间/版本元数据；不要从已经看过的测试日期重新挑赢家，也不在本流程中修改活动生产器。

股票/MoE 的[目标研究](../research/sequence-target-study.zh-CN.md)也已定义分类与收益回归、线性/参数匹配/等权/稀疏对照、配对区块区间和继续条件。应复用其封存结果和未来准备门槛，而不是从比赛日记再启动一轮架构搜索。历史窗口已经暴露；新的未来区间需要独立冻结协议。这些是可继续检查的具体工作，不代表已经证明 MoE 或情绪能改善比赛收益。
