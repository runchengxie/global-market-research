# 同账本基线决策

[English](baseline-decision.md) · [研究候选](research-candidates.zh-CN.md)

先在相同数据、日期和记账规则下比较少量假设，再评估是否增加模型容量。离线基线研究复用既有现金约束 USD 调整单位模拟器，保留全部请求案例，将缺少申报绑定模型的 Ranker 明确记为不可用。结果保存在私有目录，不生成目标仓位或订单。

## 协议与范围

在外部目录密封 `protocol.json`，schema 为 `competition.baseline_decision_protocol.v1`。绑定源清单 SHA256、源码版本和适配器文件 SHA256。记录带时区的 `frozen_at`，USMV 与 USD，按顺序排列的 XNYS `start`、`end`，整数 `sma_lookback`（2 至 252），正数 `stock_weight`（不超过一），有序且唯一的 `one_way_cost_bps`（0 至 100，最多八项，至少含一个正费用），数值容差、正数改善门槛和正数通过比例分子分母。`history_previously_examined` 必须为 true，`parameter_optimization` 与 `execution_authorized` 必须为 false。采集早于当前回顾性冻结，全部估值点必须位于保留响应的可得范围内。

输入沿用 [ETF 演练](etf-rehearsal.zh-CN.md)的四来源密封清单。适配器核对这些文件，只有 USMV 贡献收益和样本数量。要求完整 XNYS 日期与正数开盘、收盘值，不填补数据。历史调整与模拟时钟无法认证当年的可得性或独立价格。本轮不请求供应方数据，也不训练新模型。

```bash
python -m competition_tools.competition_review.baseline_decision \
  --manifest /external/sealed-inputs/manifest.json \
  --protocol /external/sealed-protocol \
  --output /external/new-baseline-study
```

使用锁定的根包 daily-data/test 环境。输出为新的外部密封目录，包含 study.json 和双语报告，已有目录会被拒绝。代码变化需要新的实现绑定及明确的新版本记录，旧结果继续保留。

## 方案与共同记账

| 方案 | 定义 |
| --- | --- |
| `cash` | USD 零收益现金 |
| `buy_hold` | 初次满仓后固定单位持有 |
| `partial_hold` | 初次使用协议股票权重，随后固定单位，允许敞口漂移 |
| `fixed_monthly` | 月度开盘检查时恢复协议股票权重 |
| `sma_monthly` | 在相同检查点，前一已完成收盘严格高于均线时才使用协议权重 |
| `declared_ranker` | 未提供与申报绑定的拟合模型，指标保留为空 |

全部方案使用相同开盘估值和入场、调仓、期末费用，按扣费后净值确定权重，并由现金承担成本。均线包含前一已完成交易日，且只用入场之前的收盘。有效相等时选现金，缺少历史时阻断。月度信号不会触发每日调仓。回撤包含入场前净值一，完整保存信号、持仓、现金与费用。风险只按开盘估值衡量，年化指标用于样本描述。

每个年度从净值一重置，部分年保留展示并排除在完整年度筛选之外，不拼接重置后的曲线。USD 调整单位估计省略账户本位币汇率和实际融资。当前挑选的 ETF 历史不能代表当时的全市场成员样本。本轮不据此确认超额收益或真实账户表现。

## 决策记录

均线与同频固定仓位配对，保留每个费用下的收益差和回撤差。冻结的共同改善比例只筛选这套规则的研究优先级。两者敞口仍有差异，不宣称风险匹配。每个正费用都须达到门槛，缺少请求案例时结论为未知。申报模型结果缺失时，模型与基线的比较继续被阻断，实际采用授权始终为 false。

此前的[波动控制停止决定](volatility-robustness.zh-CN.md)和[前瞻周期](research-candidates.zh-CN.md)保持原样。完整指标和独立持有轨迹复核保存在私有目录。审阅数据质量和账户绑定之后，再决定哪些假设值得进入新的观察，不根据结果修改参数。

参评资格与融资仍单独核对。[官方比赛规则](https://fundconnecthk.com/quant-league/legal/competition-rules/)使用平台持仓率和换手率，模拟换手与目标权重无法认证这些指标。平台定义和分币种结算事实未解决时应保留缺口，不能靠制造交易活动填补。
