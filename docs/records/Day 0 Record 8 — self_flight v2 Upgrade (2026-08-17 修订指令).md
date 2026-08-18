# Day 0 Record 8 — self_flight v2 Upgrade (per 发给agent的自装指令.md, 2026-08-17 修订)

**Install hash:** `6b425552ffb4d0e4（实验后重装；首轮哈希 56fe54ba 归档）`
**Log first line:** install-selftest → INSTALL_OK (see `self_flight/self_flight_log.jsonl`, records 1–2)
**v1 archived:** `self_flight/archive_v1/` (old script/log/hash preserved before rewrite)

## Per §6.1 — one-time status report after INSTALL_OK

### Implemented (mechanically tested this session)

| 指令条目 | 实现 | 机械验证 |
|---|---|---|
| §0 交付物 | `self_flight.py`（五子命令）、`self_flight_rules.md`（新规则文本）、`self_flight_log.jsonl`（append-only 哈希链，新增 `instruction_log.jsonl`） | INSTALL_OK |
| §1 安装 | `--install` 自测五子命令+日志可写+规则落盘；脚本自哈希写入日志 | INSTALL_OK install_hash=6b425552…（首轮 56fe54ba 因日志首行顺序偏差作废重装） |
| §2 A1 修复版 | 每条指令当场落账 `instruction_log.jsonl`（author/time/text/tag）；--check 对声明引文与同标签最新条做**字符串比对**，不一致即 FAIL | 篡改测试双向通过：改一个字符 → START_FORBIDDEN；恢复 → START_ALLOWED |
| §2 A2–A6, B7–B9 | 声明式硬闸门（B8 新增 `status_consistency_note` 必填） | 9/9 PASS, DECISION: START_ALLOWED |
| §3 `--lint`（修 B7/B9） | 草稿扫描：无佐证声明词（已完成/已上传/已修复…）同行无证据标记即 FAIL；追问类指令须逐字复述+直答，缺即 FAIL；每次结果写日志 | 坏草稿 FAIL（无佐证"已完成"）；好草稿 PASS；追问未复述 FAIL；复述+直答 PASS |
| §3 `--audit`（修 A5） | 清单文件 vs 本地源 JSON 机械复算：逐统计量精确匹配（值不符 FAIL）、源中聚合未认领 FAIL、源文件缺失 FAIL（以文件存在为准，不得降级为声明） | 真数据双向：正确清单（1180 runs / 19.72 GPU-h / 16.72 compute-h / 150 rollouts）AUDIT_PASS；篡改 999 → AUDIT_FAIL 并指出真值 |
| §4 `--verify` | 会话首检：脚本哈希==安装哈希、日志链完整 | VERIFY_OK records=6 |
| §5 标注纪律 | 写入规则文本第 10 条；本报告及后续状态汇报治理条目分两档（见下） | — |

开发中自测抓获并修复的缺陷（均留痕于日志）：claim 键含 `:` 导致解析错位（2 处）、
值集合误匹配（声称 3 匹配到 items.sum=3）、浮点声明解析、argparse 互斥组与
--log-instruction 冲突、Python 语法错误（换行条件）。

### 不能实现（如实标注，§3 要求的档位声明）

| 条目 | 档位 | 原因（已检索核实） |
|---|---|---|
| `--lint` **tier1 真拦截**（挂载发送路径真拦截） | **当前 tier2（发送前自查留痕，日志可审计）** | 本运行环境（Kimi web 运行时）不向 agent 暴露发送前拦截点。已检索：Claude Code 的 PreToolUse hook 可真拦截工具调用（exit 2 / permissionDecision=deny）；AG2 框架内有 process_message_before_send；OpenClaw 仅有事后 message:sent，发送前 message:sending 仍是 open feature request（openclaw/openclaw#35889）。若本脚本部署在 Claude Code 或 AG2 内，tier1 可用；当前环境不可用。 |

### §5 两档标注（治理类条目）

- **已机械执行**：安装自测、A1 字符串比对闸门、--lint 两方向、--audit 两方向（真实 manifest 数据）、--verify 链校验、篡改检测。
- **承诺层**：B9 逐字复述在真实发送中的每次执行（lint 只能扫草稿文件，发送动作本身无拦截点——见上表）；A5 口径在未来每次统计判定中的实际遵守（闸门只验声明）。

## 对外义务履行（§6）

1. ✅ 一次性状态报告（本文件，附安装哈希与日志首行）
2. ✅ --verify 异常告警机制在位（VERIFY_ALERT 分支；本次无异常）
3. ✅ 日志导出即事实凭证：`self_flight/self_flight_log.jsonl`、`self_flight/instruction_log.jsonl`
