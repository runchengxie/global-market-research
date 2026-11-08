# 固定配置与波动控制研究

[English](volatility-study.md) · [ETF代理计算](etf-rehearsal.zh-CN.md)

这项离线研究检验：在控制平均敞口、调整节奏和费用后，动态仓位是否改善描述性的风险收益。输入是已有封存行情和外部封存方案，不连接网络、券商或凭据，不产生账户目标，也不安装定时任务。现有正式账本回放的验收条件保持不变。

[Moreira与Muir的论文](https://www.nber.org/papers/w22208)提供研究时变风险的背景，但其逆方差因子组合不是本次有上限的逆波动ETF配置。不能拿论文结果证明本次策略有效。

## 先封存方案，再计算结果

在新的外部目录保存protocol.json并使用既有证据封存格式。schema为 `competition.volatility_study_protocol.v1`。必需字段包括：带时区frozen_at、manifest_sha256、symbol/currency（当前适配器仅USMV/USD）；按顺序且校准/评价不重叠的四个交易日calibration_start/calibration_end/evaluation_start/evaluation_end；lookback_returns（2–252）；annualization（整数1–366）；target_volatility（正比例且≤1）；cap为1（不加杠杆）；fixed_reference_weight（0–1）；排序去重的one_way_cost_bps（0–100，最多8项）；正buffer_sensitivity≤1；cash_return为0；leverage_allowed/parameter_optimization/execution_authorized均为false；正match_tolerance≤0.0001。参数保存在私有研究方案中，不能自动变成账户政策。

校验方案、行情清单和原始来源/回执哈希。采集时间须不晚于封存，封存须不晚于本次运行。这是**现在对历史实验的封存**，不是历史事前登记；供应方调整行情不能独立证明当时特征可得，也不能称为独立未见样本外证据。

```bash
python -m competition_tools.competition_review.volatility_study \
  --manifest /external/sealed-inputs/manifest.json \
  --protocol /external/sealed-protocol \
  --output /external/new-study
```

## 怎样比较才公平

全部方案采用同一USD调整开盘代理价格、零收益USD剩余现金和相同评价区间。验证既有四来源清单，但本实验仅使用USMV；日本与FX数据不会增加本实验样本量。要求完整XNYS交易日和预热历史，不补值。以此前已完成调整收盘价的简单收益样本标准差估计波动，再年化，用“目标波动÷估计波动”决定仓位，上限100%。零波动或缺失会阻断，不能自动满仓。信号时点按前一收盘后30分钟建模，月度调整在下一开盘代理点进行；期间固定单位持有，不每天恢复目标权重。

五组对照：fixed_reference为固定参考仓位；calibration_fixed仅依据更早校准期平均敞口确定固定仓位，不优化收益；volatility_control为主波动控制；buffer_sensitivity为缓冲敏感性；hindsight_exposure_matched为事后敞口匹配。最后一组使用评价期实际平均持仓权重反推固定仓位，**不可部署**，只用于排查“是否因为仓位更低才改善”。保留匹配残差和容差。匹配只针对主实验的零缓冲方案；缓冲组另看交易频率影响。平均敞口相等不等于实际风险相等，更不证明有超额能力。

每组从现金净值1开始，按实际股票金额变动支付入场/月度调整费用，并在最后估值点按同费率清仓。费用与扣费后目标权重联立计算，不借用现金。回撤包含扣费前净值1；日收益波动把入场费计入首个区间、清仓费计入最后区间。这是开盘估值点风险，不是盘中风险。换手合计是各次股票金额变动绝对值除以当次调仓前净值之和，不是官方日换手率。年化收益与波动只描述样本，不预测未来。

封存的双语报告和study.json保留全部信号窗口、时间、路径、流水、费用/缓冲场景、校准方法及局限。调整开盘单位不是可直接成交的报价；历史发布、公司行动口径仍未独立验证。零现金模型没有真实利息、FX、税、价差、冲击或融资。单ETF/单时段和费用敏感性不是独立验证次数。不能自动调参、选赢家、配置账户或判定比赛资格，之前冻结的前瞻周期不变。
