# 小朴：本小时可执行验收协议

## 验收目标

本协议只验证已经存在的能力，不修改 harness 核心实现，也不把历史 smoke 冒充为本轮新生成结果。

一键验收覆盖八项：

1. 通用事务成功并提交；
2. 越权请求在创建 checkpoint 前被拒绝；
3. 执行异常后恢复 checkpoint；
4. 后置验证失败后恢复 checkpoint；
5. 取消信号在安全边界生效并回滚；
6. 一个普通文件任务：两个文本文件经真实 `apply_edits` 工具一次原子更新，同时验证路径逃逸被拦截；
7. XMind + 绿色模板真实 PPT smoke：重开 OOXML、解析全部关系、验证 8 页与关键语义；
8. 治理会批量更新真实 PPT smoke：重开 OOXML、验证 11 页、页 1/9 已更新、历史页 10/11 保持原口径。

## 运行命令

由于 C 盘已无可用空间，必须把临时目录和报告留在 E 盘：

```powershell
$env:TEMP='E:\project\agent\xiaopu\.pytest-tmp\hour-acceptance'
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
python scripts\hour_acceptance.py --report-dir .acceptance\hourly\current
```

底层回归可另外执行：

```powershell
$env:TEMP='E:\project\agent\xiaopu\.pytest-tmp\hour-acceptance'
$env:TMP=$env:TEMP
python -m pytest -q tests\test_action_transaction.py tests\test_ppt.py tests\test_harness.py
```

## 通过门

- 一键验收必须是 `8/8 passed`；
- 五种通用事务结局必须各自留下有序 phase 证据；
- 普通文件任务必须只增加一个 mutation epoch，两个文件同时更新，并拒绝 `../` 路径；
- 两个 PPT 必须能由 `python-pptx` 重开、ZIP 完整性通过、全部 slide relationship 可解析；
- XMind smoke 必须为 8 页，并包含社区主题、30 天承诺、隐私边界和 1-8 页码；
- 治理会 smoke 必须为 11 页，页 1/9 为新口径，页 10/11 保留旧口径。

任一项失败，本小时结论只能写“部分通过”，不能宣称完整闭环。

## 证据边界

- 本协议复用现有 PPT smoke，不重跑模型或竞品；
- 当前没有可信 PNG 渲染，因此不声明视觉质量通过；
- 治理会文件只是批量事务代表性 smoke，不是完整 benchmark 提交；
- `source_unchanged` 和原结构检查来自冻结的 `.smoke/complex_facades/evidence.json`；脚本会另外记录当前输入和输出 SHA256，但不会将“当前哈希”误写成“执行前后相等”的证明。

验收产物固定为：

- `.acceptance/hourly/current/acceptance.json`
- `.acceptance/hourly/current/acceptance.md`
