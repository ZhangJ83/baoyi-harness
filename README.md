# 报一（Baoyi）

提供商中立、契约驱动的编码与 PowerPoint 智能体框架。

## 快速开始
```powershell
pip install -e .
$env:OPENAI_API_KEY="..."
baoyi "任务描述"
baoyi-doctor
```

## PPT 工作流
加载/创建 `.pptx` → 检查形状 ID → 替换文本（保留样式）→ 结构检查 → 可选渲染验证。

## 主要命令
```powershell
baoyi-gui --workspace .\workspace   # 桌面 GUI
baoyi --web                         # Web GUI
baoyi-bench --workspace C:\task --json "任务"
baoyi-validate-run C:\path\to\run
pytest -q -m "not swebench and not research_state and not protocol_lock and not gui and not live_provider"
```

## 配置
`BAOYI_RECORD_MODE`：`minimal` | `audit`（默认） | `research`
