# Paper Gateway 登录辅助脚本

[English](gateway-login.md)

这套 Windows 脚本检查单独安装的 IBC，并准备私有的 Paper 启动器。手机二次验证仍由人完成。`check`、`dry-run` 和 `status` 只检查本地配置，不登录、不连接 API 或历史行情服务。返回的 `authentication`、`api` 和 `historical_data` 均为 `not_checked`。发现正在运行的 Gateway 或任何 Java 进程时，检查会保守地阻止启动。

这里使用的是 IB Gateway 及其 TWS API，与 Client Portal Gateway 不同。脚本没有下单调用。`ReadOnlyLogin=no` 保留正常登录验证，`ReadOnlyApi=yes` 为默认值。经用户明确授权后，可在私有 INI 中设置 `ReadOnlyApi=no`，允许 Paper API 写入。启动器的 `read_only_api` 报告这一配置选择，不验证服务端设置，也不代表下单授权。真正连接的账户身份和运行时设置，仍需在有人监督的部署测试中确认。

## 环境和限制

需要 Windows、PowerShell 7、Python 3.12，以及稳定安装的本仓库根包。IBC 上游已于 [2026 年 9 月归档](https://github.com/IbcAlpha/IBC)。固定使用 [Windows 3.24.2](https://github.com/IbcAlpha/IBC/releases/tag/3.24.2)，压缩包 SHA256 为 `ba8e95f61f3c7c252620baef41e550c6aab98f6034179156e11a9a1623fdd892`。请在源码目录外保留原始压缩包和未经修改的解压目录。检查会逐一比较脚本、JAR 等文件的字节。辅助脚本不会下载或安装软件。

仅接受 Gateway 主版本 `1050` 的目录结构，并要求配置经过本地审查的可执行文件 SHA256。目录、版本和哈希检查不代表 IBC 兼容性已经验证。真实登录、Paper 账户身份、API 只读行为和历史行情仍需单独测试。应使用包含所需 JAR 和 Java 运行环境的离线 Gateway 安装。本脚本不校验 Gateway 的每一个库。

[上游 Windows 启动脚本](https://github.com/IbcAlpha/IBC/blob/3.24.2/resources/StartGateway.bat) 包含可修改的变量，服务脚本还会重试某些失败并重命名安装文件。`prepare` 从已校验的压缩包生成私有运行副本，移除重启跳转和可执行文件重命名段，指定 Paper、独立设置目录和私有日志。原始压缩包和安装目录保持原样。之后每次检查都会校验生成文件，无法识别的上游结构会被拒绝。生成的 IBC 文件仍属于第三方 GPL 内容，存放在本仓库外。

这套有界启动器禁用自动重启。[IBKR 官方重启说明](https://www.ibkrguides.com/traderworkstation/auto-restart-considerations.htm) 涉及每日会话复用和每周重新验证，需另行部署测试。手机确认和过期登录仍需要人处理。脚本不循环发送验证请求，也不接管其他会话。

## 私有配置

必须显式传入本机 `workspace.toml`。其中定义 `code_root`、`data_root` 和 `config_root`，使用 `tomllib` 读取，不搜索凭据存储。按这些根目录配置：

| 用途 | 位置 |
| --- | --- |
| 启动 JSON、私有 INI、独立设置、生成的启动器和运行副本 | `CONFIG_ROOT/deployments/global-market-research/ibgateway-paper/` |
| 原始 IBC 压缩包和解压目录 | 源码外、由当前用户保护的工具目录 |
| 日志 | `DATA_ROOT/global-market-research/operations/ibgateway-paper/` |

将 [launcher.example.json](../../config/ibgateway-paper/launcher.example.json) 和 [ibc.example.ini](../../config/ibgateway-paper/ibc.example.ini) 复制到私有目录，替换所有绝对路径占位符。保留 `activation_authorized=false`、`retry_limit=0`，超时设为 30–300 秒。源码模板不含登录凭据。如需自动填入，请自行在私有 INI 中添加 `IbLoginId` 和 `IbPassword`，不要写入启动 JSON、命令行、任务 XML 或聊天。未配置凭据时，在 Gateway 界面手动输入。

INI 必须明确指定 Paper、`ReadOnlyApi=yes` 或 `no`、正常登录、关闭 FIX、手动或 secondary 会话策略，以及二次验证超时后不重新登录。配置中的 MFA 退出间隔必须为正数且不大于观察超时。禁用重新登录后，上游可能不使用这个退出间隔；包装脚本只限制观察时长，不保证结束 Gateway。禁止设置自动重启时间、远程命令服务、`IbDir` 和可信 IP 覆盖项。只接受模板中的设置，以及名称完全匹配的 `IbLoginId`、`IbPassword`、`FIXLoginId`、`FIXPassword`。IBC 按 Java Properties 语法解析并记录未知字段，因此拒绝未知字段、转义或不规范的键、续行和重复键。也拒绝相对路径、重解析点和批处理元字符路径。本启动器不支持含圆括号的路径。

保存秘密前，请把部署目录、INI、设置、日志和工具路径的允许访问权限限制为当前 Windows 用户 SID 和可选的 SYSTEM。检查包含继承权限的允许条目和所有者，不在检查过程中自动修复 ACL。对于自己新建的空目录，可先审查下面的 PowerShell 示例：

```powershell
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
icacls $privateDirectory /inheritance:r /grant:r "*${ownerSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F'
icacls $privateDirectory
```

`/grant:r` 只替换指定身份的授权。审查后移除其他允许条目，再次检查。已有文件也需按实际情况限制权限。不要对无关目录或正在使用的共享 Gateway 安装执行这些操作。日志属于私有诊断内容，不能公开发布。

## 不启动进程的检查

源码包装脚本现位于 `scripts/windows`，原路径为 `operations/windows`。准备新的稳定外部部署时，需同时复制这两个文件。源码目录迁移不改变既有外部部署路径。

显式指定稳定安装的根项目环境中的 Python。帮助命令不需要私有配置：

```powershell
& $pythonPath -m competition_tools.gateway_launcher --help
& $pythonPath -m competition_tools.gateway_launcher check --config $launcherJson --workspace $workspaceToml
& $pythonPath -m competition_tools.gateway_launcher dry-run --config $launcherJson --workspace $workspaceToml
& $pythonPath -m competition_tools.gateway_launcher status --config $launcherJson --workspace $workspaceToml
```

后三条命令只验证本地前提，不写文件、不启动 Gateway、不修改设置、不打开网络连接。`preflight_passed` 只表示配置检查通过。缺少文件返回 `REQUIRED_PATH_MISSING`，权限不安全返回 `UNSAFE_ACL`，已有 Gateway 或 Java 进程返回 `EXISTING_GATEWAY_OR_JAVA`。错误只包含稳定代码，不包含输入路径或 INI 值。示例不代表本机已安装或登录成功。

另行准备部署时，`prepare` 会新建配置后的启动器和 `runtime/` 目录，拒绝覆盖已有内容。出错后需手动审查可能留下的部分文件。源码不提供安装、停止、重启或清理命令。

## 单独确认后启用

实际安装 IBC、填写凭据以及替换当前 Gateway，需要用户另行同意。保留手动启动方式。只在审查过的部署中准备文件，并在获得启用授权后设置 `activation_authorized=true`。在已经登录的桌面会话里调用稳定部署的脚本：

```powershell
& $deployedWrapper -Action start -PythonPath $pythonPath -ConfigPath $launcherJson -WorkspacePath $workspaceToml
```

脚本先在私有日志目录独占创建 `launch.lease`，持锁重新检查配置，再启动隐藏的控制台辅助进程，Gateway 自身的界面仍供用户完成验证。子进程输出仅写入受保护的日志，退出码会传递给调用方。观察超时返回代码 3，不结束或重启子进程，也不推断认证成功与否。超时或无法确定启动结果时会保留 `launch.lease`，阻止再次启动。请先人工检查私有桌面和进程状态，再手动删除这一份锁文件。子进程正常退出时会释放锁。请在本地确认 Paper 身份及所选 API 模式，再分别检查历史行情。这里没有下单授权。

`scripts/windows/PaperGateway.psm1` 中的 `Export-PaperGatewayTask` 可生成未注册、默认禁用的任务 XML，供审查使用。需要显式的稳定绝对路径和用户 SID，使用 `InteractiveToken`、`LeastPrivilege`、六分钟任务时限，不设置重试。必须引用稳定部署路径，不能引用 worktree。它不会注册或启用任务，需要已登录的桌面，不支持 Windows 自动登录或保存任务密码。

回退由人执行：只禁用单独批准的计划任务，经用户同意后通过正常界面退出辅助程序，再恢复未改动的手动 Gateway 启动方式。不要自动删除共享工具、凭据或设置。

## 数据任务的可选登录前置步骤

`python -m competition_tools.team data acquire --ensure-gateway` 只对 `source=ibkr` 显式启用，默认仍不启动。`plan`、`inspect`、离线评估和其他来源拒绝这个参数。先用只读客户端检查 Paper API，已连接时不启动工具，也不要求桌面操作。否则需要 Windows、已登录桌面、经过校验且仅所有者可访问的 IBC 部署、已准备运行副本及 `activation_authorized=true`。

```powershell
& $pythonPath -m competition_tools.team data acquire --config $teamConfig --spec $datasetSpec --ensure-gateway --gateway-config $launcherJson --gateway-workspace $workspaceToml --gateway-wrapper $deployedWrapper
```

需在稳定外部部署中同时保留 `Start-PaperGateway.ps1`、`PaperGateway.psm1`，根环境安装可选的 `broker-data` 依赖。计划任务不能指向 worktree。工具只调用一次已有包装器的 `-Action ensure`，按配置观察30–300秒内的API状态，并在开始取数据前独立复查一次。检查失败就阻止取数。API就绪不能认证账户身份或历史行情权限。

数据规格的 `credential_file` 在这里仅引用端点JSON，内容为 `host=127.0.0.1`、`port=4002` 和正整数 `client_id`，不保存登录密码。`IbLoginId`、`IbPassword` 只写私有IBC INI，不放仓库 `.env`、JSON、命令行或任务XML。出现手机验证时仍由人确认。

新增 `ensure` 模式只有在确认API就绪或子进程正常退出后才释放启动锁。超时、探测失败或启动状态不明时保留锁，不结束Gateway、不循环登录、不接管会话。外层330秒观察超时在Windows只结束包装器，Gateway及锁保留供人工检查。原 `start` 和非启动检查的语义不变。独立只读检查命令为 `python -m competition_tools.team.gateway --connection-file <external-json>`，只输出稳定代码，不包含凭据值。SDK缺失或端点配置无效时不会启动。

这里交付的是已批准的代码接入，不安装IBC、不填写凭据、不启用部署、不注册任务，也不代表真实登录已验证成功。

## 验证范围

Linux CI 运行纯 Python 契约测试，专门的 Windows CI 还使用临时假程序测试 PowerShell，覆盖非启动检查、脱敏、桌面会话限制、私有输出和子进程失败。测试不安装 IBC、不认证账户、不下单，这些仍属于部署验证。参见[发布检查](release-checks.md)。

## 只读验收

轻量 API 探测不检查账户、合约或历史数据权限。安装可选的 `ibkr` 依赖后，使用独立验收命令：

```powershell
& $pythonPath -m competition_tools.team gateway verify --connection-file $paperEndpoint --contract-spec $contractSpec --historical --output-root $newExternalOutput
```

命令不需要团队配置。端点文件只接受 `host=127.0.0.1`、`port=4002` 和小于 `2**31` 的正整数 `client_id`。请选择其他连接未使用的客户端 ID。外部合约文件格式如下：

```json
{"schema":"competition.paper_contract_spec.v1","market":"US","contracts":[{"product":"SPY","symbol":"SPY","exchange":"SMART","currency":"USD","role":"benchmark"}]}
```

港股使用 `HK`、`SEHK` 和 `HKD`。每个文件只包含一个市场，产品数量为 1–21，产品标识不得重复，角色为 `stock` 或 `benchmark`。只有确认连接恰好一个 `DU` 前缀账户，才请求合约或历史数据。这只是账户前缀检查，不证明该账户已登记参赛。合约的代码、交易所、币种和股票类型必须匹配，并具有正整数券商合约 ID。SDK 操作超时为八秒。指定 `--historical` 时，为每个已确认合约请求五天的每日 RTH TRADES 数据；未指定则不检查历史数据。成功读取仅说明该次请求可用，不证明完整历史、复权质量或未来所有数据权限。

`competition.paper_read_verification.v1` 报告分别记录 `api`、`account_prefix`、`contract`、`historical`、`intended_read_only` 和 `server_read_only`，附 UTC 检查时间及稳定错误码，不含账户 ID、路径或 SDK 原始错误。可选的 `--ini-file` 检查仅允许所有者访问且不经过重解析路径的 IBC 配置，报告预期只读设置。服务端只读始终为 `not_verified`，命令不会通过下单验证。退出码 0 表示请求的检查未发现阻断问题，不表示所有可选检查或服务端检查都已验证。退出码 2 表示检查受阻或输入无效。指定的输出目录必须位于源码外且尚不存在，报告写入其中的 `verification.json`。命令不会启动、重启 Gateway 或登录账户。

受保护的 SDK 会话串行运行，从连接到断开期间暂时关闭标准 Python 日志，结束后恢复原状态，避免单独配置的 SDK 子日志处理器输出敏感记录。嵌入式调用方应避免在此期间并发记录无关日志。

## Linux 单次启动器

Linux 使用独立的纯标准库启动器，上述 Windows 工具保持不变。在源码外安装离线 Gateway 10.50 和原始 Linux IBC 3.24.2。IBC 已归档，真实兼容性仍需有人监督的 Paper 验证。启动器直接调用 IBC 的 Java 入口，保留官方安装，避开上游 shell 脚本的重命名和重启循环；使用 Gateway 自带 Java，不需要系统 Java 或 xterm。

将 [linux-launcher.example.json](../../config/ibgateway-paper/linux-launcher.example.json) 复制到私人部署目录，填写源码外的绝对路径。沿用私人 INI，保持 `TradingMode=paper`、`ReadOnlyApi=yes`，二次认证和已有会话由人处理。在本地按 Java Properties 语法填写 `IbLoginId`、`IbPassword`，不要把凭据放进 JSON、命令行、Git 或聊天。部署容器、设置目录、日志容器及日志仅所有者可访问（目录 `0700`、私人文件 `0600`）。工具文件须属于当前用户，其他用户或组不可写。符号链接路径和源码内路径会被拒绝。每层上级目录须属于当前用户或 root，且其他用户或组不可写；root 所有且带 sticky bit 的系统临时目录除外。不安全的共享上层目录会阻止部署，不应静默修改其权限。

创建仅所有者可访问的 `tools-manifest.json`：JSON 对象的键为已安装文件的绝对路径，值为经审查的 SHA256。至少覆盖 Gateway JAR、`.install4j/i4jruntime.jar`、`.install4j/i4jparams.conf`、`ibgateway.vmoptions`、`jre/bin/java`、`IBC.jar`；另保留含 Java 库的完整安装文件清单。本地摘要只能检测后续变更，不等于发布方身份验证；需使用可信官方下载并单独审查来源。清单本身是受信任私人配置。原始发布包和许可记录保留在源码外。

```sh
python -m competition_tools.linux_gateway_launcher check --config /absolute/private/deployment/launcher.json
python -m competition_tools.linux_gateway_launcher dry-run --config /absolute/private/deployment/launcher.json
```

两条命令只读取文件和进程名称，不打开 socket、不创建子进程、不写配置、不认证。输出不含 INI 值或 Java 参数。`preflight_passed` 仅说明本地前提通过。已有 Java/Gateway 进程、启动锁或非空设置目录都会阻止检查。初版刻意要求全新的独立设置目录，不是持久重连或每日重启服务。不要自动清空已有设置或结束无关会话来通过检查。

真实登录需要另行明确授权、已登录桌面（`DISPLAY`）以及私人 JSON 中的 `activation_authorized=true`。显式 `start` 获取独占 `launch.lease`，重新检查后仅启动一次，排除继承的 Java 参数注入环境变量，输出只写入私有任务日志。30–300 秒观察超时返回退出码 3，不结束或重试子进程，并保留启动锁；中断或状态不明时同样保留。先检查桌面、进程和私人日志，再人工处理旧锁，不能盲目重试。子进程正常退出后释放锁并报告退出码。进程运行或正常退出不代表认证成功。

不提供自启、计划任务、自动重启、凭据迁移或下单调用。有人监督的登录步骤获准前保留 `activation_authorized=false`。登录后使用独立的[只读验收](#只读验收)，服务端只读设置仍需在界面确认，不通过下单测试。
