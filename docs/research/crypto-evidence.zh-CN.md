# BTC/ETH价格与AIVIX因子证据

[English](crypto-evidence.md) · [公开实测页面](https://runchengxie.github.io/global-market-research/zh-CN/research/crypto-evidence/)

这轮固定小时/四小时 Ridge 筛查没有支持保留 AIVIX 因子带来预测增量。所有学习组的平均折MSE都差于拟合段均值先验，因子组也差于仅价格组。固定20基点收益门槛下，多数学习规则保持空仓；净收益中位数为零不能证明预测有效。数据准备、历史实验和首批预先预测已经形成工程记录，历史可得时间与独立前瞻证据仍不完整。

## 数据范围

不可变的BTCUSDT/ETHUSDT现货快照覆盖2024-10-01至2026-10-01（结束日不含）：每资产17,520根小时线及4,380根派生四小时线，使用USDT原始价格。读取了48个ZIP和48个校验文件，共96次尝试、2,028,208响应字节和5,747,170解压字节，在112次/32MiB传输/64MiB解压/600秒上限内完成。没有使用凭据或私有服务。先校验再规范化；缺失小时、错误UTC网格、非有限OHLCV、异常ZIP成员、收盘时间及单位错配都会阻塞实验。四小时线只由四根完整对齐小时线生成。

[Binance官方说明](https://github.com/binance/binance-public-data)列明粒度、校验文件、历史修订，以及现货时间戳从2025年1月起改为微秒。保留原始字节与校验文件，后续重新下载作为新版本处理。

外部所有者保留的AIVIX快照含BTC/ETH共2,280条日频记录、三个ID：`CO-A-02-03`、`CO-S-01-01`、`CO-S-01-05`。五字段为`asset`、`indicator`、`period_start_utc`、`period_end_utc`、`value`。指标定义、历史首次发布和修订规则仍未独立确认，所以历史时点可得已验证组仍被阻塞。公开投影只包含研究汇总和来源摘要。

## 固定实验与指标

仅价格Ridge(alpha1)、因子周期结束24/72/192小时后的代理组，以及先验/现金/持有/趋势对照，使用相同时间样本交集；192小时组是在24小时代理上再错位七天。七项价格/资产特征为一根K线、24小时和168小时收益、24小时波动、完整K线振幅/收盘价、24小时相对成交量及ETH标记。缩放只按拟合段估计，并与系数一起保存。

特征截至t，完整延迟一根K线，在t后一根开盘入场、再下一根开盘退出；跨入首个测试决策的拟合标签会清除。三个扩展折分别测试2026年4—5月、6—7月、8—9月。共24次确定性拟合、144个时间折/方法/费用案例，耗时7.2秒，上限36次/600秒。收益门槛固定0.002，单边费用为0/10/25基点，不搜索门槛或参数，不训练神经网络，也不从历史结果晋升赢家。

每资产等额初始资金，只做多或现金，支持分数仓位，计入首次开仓和最终平仓。组合净值是两个子账户净值的平均，回撤包含初始净值1和交易后的净值。持仓比例列统计每根K线有几个资产处于持仓状态、两个资产各占一半；换手先在资产内归一化再平均。收益取折中位数，误差改善/持仓比例/换手取折均值，回撤取最差一折；不同折不拼接。配对区间采用七日时间区块、固定种子抽样2000次，保留资产关联和折边界，不声称已校正多重比较。

## 复现与预算

明确配置`DATA_ROOT`和外部`UV_PROJECT_ENVIRONMENT`；Windows环境使用`Scripts/python.exe`，Unix环境使用`bin/python`。独立包运行`uv sync --locked --group dev --extra predictive`安装锁定的可选线性依赖。

根采集API为`competition_tools.datasets.binance_intraday.freeze_intraday_plan(output, now=aware_utc, source_revision=exact_commit)`及`acquire_intraday(plan_file, new_output, IntradayTransport())`。路径均须在源码外，保留冻结计划、排他标记、原始档案、账本和封存。相同计划不能换目录重复运行；部分结果应检查原因，不重置计数。

```sh
python -m crypto_mm.intraday.cli freeze \
  --dataset '<sealed-hourly-dataset-directory>' \
  --sentiment '<owner-published-factor-snapshot.json>' \
  --sentiment-sha256 '<expected-sha256>' \
  --source-revision '<clean-40-character-commit>' --output '<new-plan-directory>'
python -m crypto_mm.intraday.cli run \
  --plan '<frozen-plan-directory>/plan.json' --output '<new-study-directory>'
```

保留完整状态JSON，只有`completed`结果能够提供公开数据。保存模型须重建分数；系数、逐个预测和账户路径留在外部。前瞻生产器使用冻结wheel，防止后续代码检出变化悄悄改变生产指纹。

## 前瞻记录与有限观察进程

协议冻结最后一折的仅价格小时/四小时模型、生产器指纹、真实UTC时钟及资源上限。根工具通过版本化文件和独立CLI调用研究包。首个成功回执提交了4条未来预测、0条已评分结果。预热数据不算新增及时观察，迟到补录与下次假设入场前收到的K线分开记录。每条预测绑定特征/模型摘要、特征截止、生成及未来入场/退出时间；后续收到结果才评分。修订单列，原评分不重写。这是等待独立审阅的自记证据，不是已注册独立留出。

```sh
python -m competition_tools.evaluation.crypto_observation freeze \
  --study '<sealed-study>' --dataset '<sealed-hourly-dataset>' \
  --producer-python '<stable-external-frozen-producer-python>' --output '<new-protocol>'
python -m competition_tools.evaluation.crypto_observation capture --protocol '<protocol>'
python -m competition_tools.evaluation.crypto_monitor \
  --dataset '<sealed-hourly-dataset>' --study '<sealed-study>' \
  --protocol '<protocol>' --output '<new-local-monitor-directory>'
python -m competition_tools.evaluation.crypto_watch \
  --dataset '<sealed-hourly-dataset>' --study '<sealed-study>' \
  --protocol '<protocol>' --output '<new-task-owned-watch-directory>'
```

可选任务专属进程每小时采集，在协议冻结48小时、累计预算或部分/未知状态时停止。不修改系统定时任务、共享服务或券商。停止并完成保留审查前，保留状态/事件、稳定环境和源码；不自动上传私有报告到Pages。

首轮工作进程启动失败的记录仍保留。替代协议的CLI最初漏传了要求结转的参数；现以不可变补充回执绑定原协议和记录摘要，将替代协议总额度下调为47次采集、95次HTTP尝试和31MiB。协议原字节和4条已提交预测均未改变；后续采集、历史读取和监控都会重新检查扣减证据，更换目录不能重置。修正后的冻结CLI会传递前驱参数；无预测的失败启动可使用`--previous-protocol`。`crypto_observation reconcile --protocol '<current>' --previous-protocol '<failed-start>'`能够追加保守扣减，不改写已有承诺。旧协议中的未知消耗不会盲目重试。

## 公开展示与运行状态

`crypto_monitor`只读本地数据，检查封存的采集、实验与观察证据，显示覆盖、新鲜度、迟到数据、修订、行情/预测/评分独立计数及资源消耗；缺失或无效输入仍标为阻塞。`scripts/crypto_public_projection.py --dataset ... --study ... --protocol ... --monitor ... --output ...`从这些来源显式导出闭合字段的公开汇总，核对来源封存、样本/案例范围，并公开预测记录链末端摘要，便于形成外部发布时间锚点。页面是截至时间快照，不是实时流。

Pages可以展示实测汇总、区间、时间折、成本对照和局限。逐个预测、原始输入、账户记录及私有配置保留在外部；静态及无脚本表格保留完整公开事实。新增校验、图表和控制器使用严格TS，图表代码按需加载。测试拒绝私有字段和过时的合成限制，并要求公开JSON中的投影代码摘要匹配规范化源码。

股票前瞻协议的六项所有者证据缺口和已注册观察治理保持独立。这个加密货币试验不自动解决它们、不扩展执行产品、不晋升研究接受或下单。参见[序列目标实验](sequence-target-study.zh-CN.md)及[观察登记](observation-registry.zh-CN.md)。

[后续研究记录与序列模型对照](crypto-followup.zh-CN.md)
