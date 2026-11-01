# 盲测结果 — source-and-binary-static-audit

- **通过率**: 9/9（100%）
- **判定**: 接受
- **方式**: 独立 sub-agent 盲测（仅给同书 skill 清单与 prompt，不提供预期答案）
- **判卷标准**: should_trigger 要求本 skill 被选中；should_not_trigger 要求本 skill 未被选中；edge_case 按预期行为中的“应/不应激活”判定。

| id | type | prompt | 期望 | 实际 chosen | 结果 |
|---|---|---|---|---|---|
| P1011 | edge_case | 我有源码也有二进制，应该先看哪个？ | 应激活本 skill，按目标与信息量选择源码审计或二进制静态收敛，并说明两者互补 | source-and-binary-static-audit | ✅ |
| P1012 | should_trigger | 有一个 stripped 的 Linux ELF，怎么找到 main 函数并恢复结构体？ | 应激活 | source-and-binary-static-audit | ✅ |
| P1036 | should_not_trigger | 程序跑起来崩溃了，帮我从崩溃现场找根因 | 不应激活 | （无） | ✅ |
| P2010 | should_not_trigger | 把这段反汇编还原成 C++ 类型、表达式和控制流 | 不应激活 | （无） | ✅ |
| P2029 | should_not_trigger | 帮我用 Peach 配一个文件格式 fuzz 会话，选种子和 DataModel | 不应激活 | fuzzing-engineering-peach | ✅ |
| P2041 | should_trigger | IDA 里全是 sub_XXXX，怎么用 FLIRT 签名识别静态链接的库函数？ | 应激活 | source-and-binary-static-audit | ✅ |
| P3008 | should_trigger | 给我一份源码审计检查表，重点看内存破坏和整数溢出 | 应激活 | source-and-binary-static-audit | ✅ |
| P3015 | edge_case | 怎样写 IDAPython 脚本批量重命名函数并标注结构体？ | 不应激活本 skill；编写 IDAPython 插件或脚本做批量标注与协作，走 reverse-engineering | reverse-engineering-tooling-and-collaboration | ✅ |
| P3028 | edge_case | 帮我把 IDA 里的函数名和注释共享给同事，并合并他们的修改 | 不应激活本 skill，应激活同书 reverse-engineering-tooling-and-collaborat | reverse-engineering-tooling-and-collaboration | ✅ |

## 失败案例

无。
