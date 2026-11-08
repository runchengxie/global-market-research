# 参数不变的波动控制稳健性检验

[English](volatility-robustness.md) · [原仓位研究](volatility-study.zh-CN.md)

用事先冻结的研究停止规则决定某套仓位配置是否值得继续投入。它不是通用投资效用标准、独立价格认证、历史事前登记或账户策略验收。原仓位计算与比赛前瞻周期均不改变。

## 先冻结意图，再取得结果

在获取/评价新结果前，封存外部intent.json（schema为competition.volatility_robustness_intent.v1），绑定原封存方案哈希和原样核心参数：lookback_returns、annualization、target_volatility、cap、fixed_reference_weight、one_way_cost_bps、buffer_sensitivity、cash_return、leverage_allowed、parameter_optimization、execution_authorized、match_tolerance。聚合器与原方案逐项规范化比较类型/值；不能同时改新意图和结果就悄悄替换原参数。

意图还包含带时区frozen_at、calibration_start/end、按时间排列的episodes（id/evaluation_start/end/full_calendar_year/previously_examined/include_in_decision）、从原费用列表选择的正decision_fees、required_share_numerator/denominator、numerical_tolerance、material_improvement，以及execution_authorized为false。重新核对XNYS完整年度边界及与原校准/评价期的重叠；只有新完整年度计入分母，既有和部分年度仍展示。所需通过数向上取整，不向下舍入。没有新完整年度时结论未知。

公开来源采集需限时限量并保留字节/回执，不绕过登录或浏览器验证、不使用券商凭据。发行人原始工作簿不修改，只读提取且不执行公式。净值、原始市场收盘、复权价格和收益指数不是一回事；分红日期/舍入金额吻合不认证独立复权OHLC、拆分史或历史可得性。来源与上游关系不明时明确说明，不以净值冒充可成交开盘价，不公开原始受限/授权文件。

采集后，为每个区间生成绑定来源的原方案副本，保持意图与核心参数不变，用已有volatility_study命令计算。各年度从现金净值1重置，并支付入场/期末费用，不能拼成连续多年账户。封存runs.json（competition.volatility_robustness_runs.v1），包括recorded_at、intent_sha256、source_manifest_file/source_manifest_sha256及每项id/root/study_sha256。计划区间缺少结果时保留缺口，不删掉该年。

## 按完整证据汇总

```bash
python -m competition_tools.competition_review.volatility_robustness \
  --intent /external/sealed-intent \
  --original-protocol /external/original-sealed-protocol \
  --runs /external/sealed-runs-manifest \
  --corroboration /external/optional-sealed-source-audit \
  --output /external/new-robustness-report
```

离线命令校验封存、字节哈希、采集/冻结/报告时间、核心参数、区间日期、来源/资产/币种和每组费用/方案。封存研究是所提供的计算证据；聚合器不会重新执行价格账本。敞口匹配对照必须标明事后且不可部署，实际平均敞口残差须在冻结容差内。

收益差＝波动控制减匹配固定仓位；回撤差＝波动控制最大回撤减匹配固定仓位最大回撤，因此正值表示损失更小。两者均不小于负numerical_tolerance，且至少一项不小于material_improvement，才算通过。**每个**决策费率都需达到指定比例的新完整年度通过。敏感性费用仍展示，任何计划年份/方案/费率缺失都会令整体结论未知。看过结果后不调整阈值。

robustness.json和双语报告保留全部年度/费用比较、排除理由、向上取整计算、匹配核对、来源哈希和局限。研究决定为按冻结规则继续候选、移出主候选，或明确的未知状态。独立来源范围另列：可选佐证包schema为competition.volatility_source_corroboration.v1，须绑定同一清单哈希；兼容/上游标签仍是归属声明。任何结果下实际采用均为false，不证明策略普遍无效或存在超额能力，不产生订单、券商/平台变更、自动任务或可执行目标。
