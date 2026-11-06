# 现金支持的 Paper 仓位分配

[English](paper-allocation.md) · [文档目录](../README.zh-CN.md)

新的分配 CLI 默认只做离线计算。第一版支持一只以美元交易的美国股票或 ETF，可选新加坡元兑美元资金准备，账户估值币种为新加坡元。研究侧 `targets.json` 不能充当本功能的执行授权；需要单独的私有规格，明确账户、已确认合约、当前时间窗口和风险参数。

**尚未完成真实 Paper 券商验证。** 单元测试使用合成数据和模拟客户端；恢复过程中没有下单、登录 Gateway 或创建计划任务。按照项目要求，执行链 PR 必须等真实 Paper 生命周期验证通过后才能合并。

## 规格与离线计算

规格保存在源码外的部署配置目录。`apps.execution_runner.paper_spec` 中的 `AllocationSpec.to_dict()` 输出完整 `paper-allocation.v1` 格式。顶层必须包含 `schema`、`run_id`、`account`、`symbol`、`con_id`、`primary_exchange`、`window_start`、`window_end`、`policy`、`allowed_positions` 和 `settings`；未知或重复字段会被拒绝。任务 ID 为 1–24 位 ASCII 字母、数字、下划线或连字符。必须明确指定 `DU` 模拟账户和 Paper 端口（4002 或 7497），适配器还会核对券商实际返回的账户。美股代码使用 `.US` 后缀。时间窗口必须包含时区、最长 30 分钟，并处于合约确认的同一个常规交易时段内。

策略需要总敞口目标权重（大于 0、不超过 1）、新加坡元目标上限、整数股数上限、前期参考收盘价及日期、股票和外汇最小报价单位。Decimal 数值在 JSON 中写成字符串；`max_shares` 为整数。序列化规格还明确包含股票价差 `.005`、外汇价差 `.003`、股票限价偏移 `.002`、外汇限价偏移 `.0005`、现金缓冲 `.005` 和参考价格偏离 `.015` 等库默认容差；每项最多 `.05`。这些数值不是仓位建议。旧脚本的 55%、USMV 和十月参考价格均不会自动沿用。

离线快照包含字符串数值 `nav_sgd`、`gross_sgd`、`sgd_cash`、`usd_cash`、`sgd_settled`、`usd_settled`，以及 `stock`、`fx` 报价。报价字段为字符串 `bid`/`ask`、含时区的 ISO 时间 `at` 和布尔值 `live`。要求实时行情，时间范围为当前时间之前 15 秒到之后 1 秒。演示也需要新鲜的合成快照；保存过久的报价会被拒绝。限价按报价单位向上取整、股数向下取整，只使用已结算资金。

```bash
python -m competition_tools.run_paper_allocation \
  --spec "$CONFIG_ROOT/deployments/global-market-research/allocation.json" \
  --snapshot "$DATA_ROOT/global-market-research/paper-demo/snapshot.json"
```

离线计算不会连接券商、预占任务或创建结果目录，输出 `status=offline_plan` 和 `submitted=false`。

## 明确执行与恢复

在另行授权一笔具体、当前有效的 Paper 操作后，才使用相同 `--spec` 并添加 `--mode submit --execute-paper --data-root "$DATA_ROOT"`。CLI 沿用项目数据根目录选择规则，所有账户共用项目下固定的 `paper-allocation` 状态空间。不要另建数据根目录绕过历史尝试。其他 runner 使用的 `settings.dry_run` 不能替代本 CLI 的明确模式和开关；离线模式不会提交。

流程将现有 `OrderIntent` 包在明确的 IOC 限价命令中，将提交请求、券商结果和成交 ID 分别记录，不使用市价单。换汇完全成交后仍需重新检查美元已结算余额、持仓、挂单、报价、窗口、STOP 和 what-if。换汇部分成交会阻止买股。结果不明的资金或订单操作会阻止同账户所有新任务 ID。超时后请求撤单，再观察撤单结果；不会自动重试。

在项目 `paper-allocation` 目录创建 `STOP` 可阻止后续提交，但不会追溯撤销已发送的订单。连接、普通请求和 what-if 超时均为 8 秒，行情等待最多 8 秒，订单观察 45 秒，撤单结果观察 10 秒。Python 调用方也可传入现有 `KillSwitch`。

```bash
python -m competition_tools.run_paper_allocation --mode reconcile \
  --spec "$CONFIG_ROOT/deployments/global-market-research/allocation.json" \
  --data-root "$DATA_ROOT"
```

对账对券商只读，要求规格保持不变，并核对已完成订单、成交、持仓及无挂单状态。历史记录不完整时保留 unknown，不能从“查不到”推断拒单。任务记录和账户阻断跨重启及新旧数据根目录别名保留；对账不会在换汇中断后继续买股。可用 `EventJournal.rebuild_projection()` 从日志重建状态。不要删除历史尝试或阻断标记来重试。账户锁由操作系统管理，进程退出后自动释放；磁盘上的锁文件本身不代表仍被占用。历史尝试和账户阻断仍然保留，只有核对证据的对账才能清除不确定状态。

退出码：0 为离线计划或已对账，2 为阻止，3 为部分成交，4 为结果不明。已对账也可能包含最终撤销的订单，或换汇中断后没有买股；应查看各笔订单事实。

## 恢复来源与真实 Paper 验证

恢复的计算代码归入 `packages/execution_policies/paper_allocation.py`，旧 runner 的职责归入 `apps/execution_runner/paper_*` 和 `adapters/ibkr/paper_allocation.py`。原始五份代码、测试及方案继续保留，哈希和处置说明写入项目私有保留清单，没有删除原始恢复文件或历史结果。

合并前先准备有人监督的、有明确边界的 Paper 验证方案，列出账户、合约、时段、股数、价格和现金上限、可选换汇及撤单步骤，再取得这些具体操作的当前授权。分别记录连接、合约确认、what-if、下单、撤单、成交、重启恢复与对账证据。还需验证中断或不确定结果会阻止不同任务 ID，且只读对账不发送订单。使用稳定、已审查的源码版本；计划部署不能依赖临时工作树。任一必需证据缺失时，PR 保持未合并并注明未验证。
