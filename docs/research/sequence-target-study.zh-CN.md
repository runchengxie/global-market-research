# 序列目标方案与前瞻准备

[English](sequence-target-study.md)

本轮比较原有“大幅上涨概率”方案与下一期开盘收益回归，检验现有特征是否含有可用信息，再考虑扩大专家容量。目标、损失和仓位门槛一起变化，因此不能把结果单独归因于标签。历史窗口都已被观察。

## 固定的对照

两种方案使用相同十只股票的拆股调整快照、十项相对特征、20日窗口、下一期开盘至再下一期开盘收益与清洗后的时间折。分类用BCE预测收益超过0.2%；回归用MSE，目标只按拟合段均值/标准差标准化，再恢复收益单位。比较拟合先验、线性模型（Logistic/Ridge alpha1）、参数量匹配的单LSTM、等权专家、真正分发的top2 MoE。线性每目标每折只拟合一次；神经种子11/23/37，最多30轮、早停5轮、batch128、Adam.001、两线程。七折计划共140次拟合/175案例，上限180次、6小时；三个种子属于探索筛查。

固定决策为概率>.5或预测收益>.001；回归门槛近似双边5基点成本，在0/5/20/40基点场景中保持不变。验证段从各自五个预设阈值中选择，同时形成冻结敞口对照。所有尝试都保留；验证段还曾用于早停。展示实际敞口与波动率，不按测试未来风险精确配仓。沿用现金支付费用、分数长仓、首次开仓和最终平仓，不含股息或融资。

分类使用Brier/AUC，回归使用原单位MSE/MAE，均与拟合先验比较；两者都看每日横截面对未来收益的秩相关，常数排名明确不可定义，不把回归值称为概率。配对区间按20日区块、2000次抽样，先按市场日期平均种子，保持折边界，不连接净值，不声称做过多重比较校正。

## 使用命令

叶子包安装锁定的 `predictive` 与 `neural` 依赖，环境和输出放在源码之外。先冻结计划：

```bash
python -m equity_lab.study.sequence.target_cli plan --manifest '<manifest>' --expected-sha256 '<sha256>' --output '<new-plan.json>'
python -m equity_lab.study.sequence.target_cli run --manifest '<manifest>' --expected-sha256 '<sha256>' --plan '<frozen-plan.json>' --output '<new-run-directory>'
python -m equity_lab.study.sequence.target_cli analyze --run '<sealed-run-directory>' --output '<new-analysis-directory>'
python -m equity_lab.study.sequence.target_cli calendar --start 2026-11-09 --end 2027-02-05 --output '<new-calendar.json>'
```

每个案例保存目标变换、特征缩放器、检查点/线性系数、验证与测试分数表、路由负载和账户，结束前重建分数。预算在训练batch和案例处理间检查；中断案例不计入完成数。未完成或无效结果不能通过继续条件。封存前复核输入，不覆盖旧结果。分析输出可检查的JSON和简洁Markdown报告，原概率浏览器不会混读回归结果。

## MoE 何时值得继续

每个完整目标方案中，稀疏固定规则在5基点下对线性、单LSTM、等权的收益差配对95%区间下界都必须为正；对每个基线分别要求20基点均值改善、七折至少五折日均收益差为正。还要相对拟合先验的Brier/原单位MSE改善区间下界为正，以及超过自身验证敞口对照。这是未校正多重比较的回顾性研发规则，不是统计确认。即使通过也仅为值得继续观察；独立前瞻证据完成前，扩大模型、研究接受和执行仍不自动通过。各项失败原因及风险差保持可见。

## 证据与前瞻准备

根工具仅用标准库消费叶子包输出的XNYS建模日历与冻结计划的准确摘要，复用数据所有者的六项阻塞审计。清单/回执只能当候选资料，不是独立证明：

```bash
python -m competition_tools.evaluation.sequence_readiness \
  --manifest '<manifest>' --expected-sha256 '<sha256>' \
  --calendar '<calendar.json>' --calendar-sha256 '<sha256>' \
  --plan '<plan.json>' --plan-sha256 '<sha256>' \
  --source-revision '<commit>' --output '<new-packet-directory>'
```

冻结全部候选和目标，不按历史结果选赢家。日历含最后信号后的两个开盘，但它是交易所日历模型，不是实际可得时间。状态为准备已冻结但被阻塞；不创建权威留出预约、研究接受、交易商请求、采集任务或共享指针。当前旧快照不提供未来特征。证券身份、时点股票池、公司行动/股息、历史可得、所有者来源/使用权、留出访问治理仍需独立证据。

## 数字货币迁移问题

区分实际保留粒度和服务能力。本轮检查的完整八币Binance输入是日频；BTC/ETH AIVIX因子快照也是日频，历史可得时间缺独立证据；小时DEX试验被阻塞。不能从API支持小时、因子时间戳或压缩包按日命名，推断已有完整小时行情。日线也不是盘口事件。下一轮BTC/ETH现货4小时/1小时筛查，应先验证不可变的因果OHLCV覆盖、缺口、价格/计价身份、执行延迟和成本敏感性。没有对应数据和账本前，不引入永续资金费率或做市假设。更细采样不会按比例增加独立观察。

参见[研究页面](https://runchengxie.github.io/global-market-research/zh-CN/research/lstm-moe/)及[已训练模型诊断](sequence-diagnostics.zh-CN.md)。

[已完成的BTC/ETH小时筛查与单独观察记录](crypto-evidence.zh-CN.md)现提供完整小时覆盖、24次固定线性拟合及明确因子可得局限。加密货币MoE尚未训练。
