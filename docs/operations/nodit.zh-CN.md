# Nodit 每日链上统计

[English](nodit.md) · [数据服务](environment-and-providers.zh-CN.md)

使用 Python 标准库手动采集以太坊主网每日活跃账户数和交易笔数。这些是研究输入，尚未证明预测能力或比赛品种资格，也不提供股票时点基本面。

## 采集与校验

在源码之外现有私人项目 `.env` 中添加 `NODIT_API_KEY=` 并在本机填写。POSIX 文件权限使用 `0600`。显式提供绝对路径：只解析该项，不执行文件内容。不要将凭据放进 URL 或命令参数。先在 shell 中配置 `CONFIG_ROOT`、`DATA_ROOT`。

```bash
python -m competition_tools.datasets.nodit collect \
  --credential-file "$CONFIG_ROOT/projects/global-market-research/.env" \
  --start 2026-08-18 --end 2026-11-15 \
  --output "$DATA_ROOT/global-market-research/research/nodit/<new-run>" \
  --max-requests 2 --max-cu 300 --max-seconds 120
python -m competition_tools.datasets.nodit verify \
  --output "$DATA_ROOT/global-market-research/research/nodit/<new-run>"
```

每次使用新输出目录。示例包含首尾共 90 个 UTC 日期，需显式调整日期。一次最多 100 个完整日，并预留 30 分钟发布延迟：UTC 00:29 尚不接受昨天，00:30 起才接受。拒绝源码仓库内的目标路径和符号链接路径。POSIX 输出文件仅属主可读写。

## 未知额度与请求预算

比赛赠送权限的额度和到期时间可能未知。每次运行默认及最高预算为四个请求、600 **估算 CU**、120 秒，每个响应最多 1 MiB。时间预算在网络操作前后检查，剩余时间缩短时也缩短 socket 超时；但阻塞的 DNS、TLS、响应头或分块读取可能超时返回，因此这不是强制终止进程的期限。操作返回时若已过期，就停止，不发布成功结果、不再请求。成功采集使用两个请求，按当前文档各 150 CU，调用间隔至少两秒。预算只约束本次运行，不覆盖并发调用、整个账户消耗或实际计费；账户若已配置超额计费，本地预算不能阻止服务商扣费。扩大采集前需查明赠送条款。不查询或修改套餐、自动扩容和付款设置。

请求前先在 `receipt.json` 记录次数和估算 CU。HTTP 错误，包括 401/403/429 和重定向，立即停止。网络失败保留消耗不确定的记录。不重试、不自动续传、不安装调度、不调用其他接口。人工重新运行前先复核失败回执。错误正文不保存、不回显。缺日、重复日、区间外日期、负数或非整数计数、无效 JSON 和密钥回显均阻断成功。返回成功但统计语义不合格的安全响应仍保留为原始证据。部分完成只保留回执及已有安全响应，不生成成功清单。

## 留存证据

成功目录包含 `plan.json`、`receipt.json`、两份 `raw/*.json`、`normalized.csv`、`manifest.json`。计划冻结日期和预算，不含凭据。CSV 按日期排序，列为 `date,active_accounts,transactions`，计数不是金额成交量。离线校验核对完整清单、SHA-256、原始序列，并重建 CSV。哈希可检测相对于清单的改动，不能证明来源或清单本身真实。

采集时间不能证明历史首次发布时间。历史修订政策、回测时点可得性、更广覆盖和比赛赠送权限的数据使用权仍需单独证据。结果保持 `accepted_research=false`、`execution_authorized=false`，不下券商订单、不修改策略申报。价格接口不在本采集器范围内：Nodit 文档说明其价格来自定期更新的 CoinMarketCap，不能当成独立的交易所实时价格。

官方参考：[鉴权](https://developer.nodit.io/en/data/data-api/api-key/)、[活跃账户](https://developer.nodit.io/en/data/data-api/getdailyactiveaccountsstats/)、[交易笔数](https://developer.nodit.io/en/data/data-api/getdailytransactionsstats/)、[CU 计费](https://developer.nodit.io/en/guides/compute-unit/)、[代币价格](https://developer.nodit.io/en/data/data-api/gettokenpricesbycontracts/)。
