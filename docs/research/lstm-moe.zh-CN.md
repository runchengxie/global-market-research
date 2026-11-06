[English](lstm-moe.md) | [简体中文](lstm-moe.zh-CN.md)

# LSTM 与混合专家研究

LSTM/MoE 后续研究迁入 `research/equity-lab`。这套可选离线实验比较可学习门控与参数量匹配单 LSTM、固定等权专家、独立集成和简单基线。[原 moe-lstm 仓库](https://github.com/runchengxie/moe-lstm) 保留历史实现与结果。新实现依据数学结构独立编写，未复制原仓库缺少许可证的源码。

## 安装与运行

在 `research/equity-lab` 下，先将 `UV_PROJECT_ENVIRONMENT` 指向所有者数据目录下一个新的外部环境目录，再运行：

```bash
uv sync --locked --group dev --extra predictive --extra neural
uv run --locked --extra predictive --extra neural python -m equity_lab.study.sequence.cli plan --manifest /external/dataset/manifest.json --expected-sha256 MANIFEST_SHA256 --output /external/runs/sequence-plan.json
uv run --locked --extra predictive --extra neural python -m equity_lab.study.sequence.cli run --smoke --manifest /external/dataset/manifest.json --expected-sha256 MANIFEST_SHA256 --output /external/runs/sequence-smoke
uv run --locked --extra predictive --extra neural python -m equity_lab.study.sequence.cli run --manifest /external/dataset/manifest.json --expected-sha256 MANIFEST_SHA256 --output /external/runs/sequence-primary
uv run --locked --extra predictive --extra neural python -m equity_lab.study.sequence.cli inspect --output /external/runs/sequence-primary
```

目标目录必须不存在。smoke 只跑一个 SPY 切分、一个种子、一个 epoch，用于检查工程流程，不评价模型有效性。主股票面板不使用 SPY 训练。`--secondary` 使用独立配置运行 top-1、共享门控、共享编码器及双专家架构对照，对应 60 日输入；`--transformer` 单独运行 Transformer 对照，不能与 20 日主实验混为同一对照。不连接券商，不采集新数据，不自动优化阈值，也不修改研究验收状态。

## 数据与时间

输入要求明确指定摘要的 `competition.dataset_manifest.v2` 美股 IBKR 日线快照，含标准 OHLCV、已采集 receipt、拆股调整价格、美元及 XNYS 日历。缺少交易日、价格非法或文件变化会失败，不前向填充，源数据只读，训练后再次核验摘要。

现有快照含 10 只当前选定股票和 SPY，覆盖 2023-01-03 至 2026-10-20 的 953 个交易日。它标记为 `accepted_research=false`，历史已被研究使用；历史当时可得、完整公司行动证据和公开发布权仍未核实。当前股票池可能存在幸存者偏差，只能作为探索性历史输入，不能称全新盲测。

特征截至 t 日收盘，假设 15 分钟后可用；t+1 开盘入场、t+2 开盘退出。标签使用相同开盘到开盘收益，超过 0.2% 为 1，否则为 0；预测概率超过 0.5 才做多，0 类空仓。标签在退出时可用。滚动段使用 400 日拟合、80 日验证和 63 日测试，按标签可用时间清除越界样本，额外隔离一个信号日，并预留假设的 12 小时模型就绪预算。逐行审计表保留实际时间和有效样本数。

## 模型、评估与产物

三个完整 LSTM 窗口专家在表示层混合。dense 路径调用全部专家；稀疏路径先按选中样本 gather，跳过空批次，计算后 scatter 加权表示。top-2 归一化选中权重；top-1 保留原始选中 softmax 概率，让预测任务梯度可传回门控。稀疏路径另加 0.01 权重的负载均衡损失，它本身不能证明分工有效。保留实际分发量、概率及表示探针。

主对照包括现金、持有、固定均线动量规则、逻辑回归、LSTM-64、按实际参数量匹配的 LSTM、等权专家、独立预测平均、dense 门控及 top-2 分发。合并训练只使用合格股票拟合窗口，缩放器也只看拟合段。训练用 5 个固定种子、最多 50 epochs、patience 5、batch 32。主阶段限制 600 次拟合及 6 小时，独立集成每个成员计一次；清单超预算时不启动。中断保留部分完成状态和待运行配置。

每折从现金开始，终止时清仓。股票初始等额独立资金袖套，使用拆股调整研究价格单位；不计分红、做空、杠杆和利息。这不是基于原始价格和完整公司行动的真实执行账本。每边 0/5/20/40 基点费用包括首次入场和最终退出，核对持仓、现金、费用与估值。回撤包含初始净值 1；未定义 Sharpe/AUC 和零交易有明确原因。不拼接独立折净值冒充连续业绩。

运行包包括配置、来源版本、环境、输入摘要、样本与切分时间、概率、模型和缩放器、路由、训练损失、成交及估值、分类与账户指标、配对 Brier 诊断及校验和。区块抽样先汇总同日股票，只在各折内部抽日期块；结果是描述性诊断。记录实际 CPU 分发量及重复推理耗时，少调用专家不自动等于速度更快。

## 公开展示

[交互研究页面](https://runchengxie.github.io/global-market-research/zh-CN/research/lstm-moe/) 默认使用明确标记的合成数据；真实投影要有具体发布权证明和资料所有者审阅。按需加载 ECharts，支持缩放和切换模型，保留可访问数值表。混淆矩阵适合普通表格，界面样例不编造实测数量。既有公开研究快照保持原样。

完整限制及后续实验见[设计文档](../superpowers/specs/2026-11-06-lstm-moe-integration-design.zh-CN.md)。测试通过、实验跑完都不等于策略盈利，也不构成执行授权。

独立后续运行：`--secondary` 比较路由变体；`--transformer` 比较单 FFN 与稀疏 Transformer；`--features levels|correlation|kmeans|som` 比较价格水平特征及拟合段筛选。每阶段各有 240 次拟合、6 小时预算。

本机生产构建实测：懒加载图表的完整依赖链约 187 KB（gzip），原来两张 PNG 合计约 120 KB。只有读者加载交互图时才请求图表库。因此这里增加了交互并延后下载，没有缩小冷启动的完整图表体积。数字对应本次构建，不含页面共用资源。

要在不重新训练的情况下检验门控，使用 `audit --run /external/runs/sequence-primary`，传入相同 manifest/摘要并指定新输出目录。先校验模型重载概率，再固定等权、逐一移除专家，以及使用共享输出头逐一探测专家。产物与已封存主运行分开；这些干预与重新训练双专家架构是不同的对照。

概率、敞口、风险和数据证据的进一步探索见[已训练模型诊断与本地浏览器](sequence-diagnostics.zh-CN.md)。

下一轮[目标方案对照与前瞻准备](sequence-target-study.zh-CN.md)固定输入，比较分类和收益回归。
