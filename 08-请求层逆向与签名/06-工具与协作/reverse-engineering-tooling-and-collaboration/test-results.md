# 盲测结果 — reverse-engineering-tooling-and-collaboration

- **通过率**: 9/9（100%）
- **判定**: 接受
- **方式**: 独立 sub-agent 盲测（仅给同书 skill 清单与 prompt，不提供预期答案）
- **判卷标准**: should_trigger 要求本 skill 被选中；should_not_trigger 要求本 skill 未被选中；edge_case 按预期行为中的“应/不应激活”判定。

| id | type | prompt | 期望 | 实际 chosen | 结果 |
|---|---|---|---|---|---|
| P1009 | should_trigger | 怎么用 IDAPython 插件批量标注函数和结构体？ | 应激活 | reverse-engineering-tooling-and-collaboration | ✅ |
| P2001 | should_trigger | 分析完样本，怎么把 IOC 沉淀成 YARA 规则并放到沙箱里用？ | 应激活 | reverse-engineering-tooling-and-collaboration | ✅ |
| P2008 | edge_case | 两个人同时改一个 IDB，冲突了怎么办？ | 应激活本 skill，按分段/导出合并/版本化流程解决 | reverse-engineering-tooling-and-collaboration | ✅ |
| P2027 | edge_case | IDA 插件和 Ghidra 脚本应该怎么选？ | 应激活本 skill 的工具化选型部分，但需说明本书以 IDA 为主 | reverse-engineering-tooling-and-collaboration | ✅ |
| P2034 | should_not_trigger | 帮我分析这个 APK 的恶意行为 | 不应激活 | android-malware-triage | ✅ |
| P2047 | should_not_trigger | 帮我从这个 stripped ELF 找 main 并恢复结构体 | 不应激活 | source-and-binary-static-audit | ✅ |
| P3031 | should_trigger | 团队怎么共享 IDA 数据库并合并各自的注释？ | 应激活 | reverse-engineering-tooling-and-collaboration | ✅ |
| P3036 | should_not_trigger | 怎么把这段汇编还原成 C++ 类型 | 不应激活 | （无） | ✅ |
| P3042 | edge_case | 帮我查一下这个函数的地址 | 不应激活本 skill，这是单点查询，不需要工具化与协作流程 | （无） | ✅ |

## 失败案例

无。
