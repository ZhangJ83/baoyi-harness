# 78 条 PPT trajectory 逆向分析报告

- 轨迹总数：78
- 非空步骤：70
- 标准事件总数：782
- Skill 数：10

## Skill 证据

### ppt.atomic_edit

证据运行：18；任务：3-002, 3-003, Accounting Equation-004
工具面：ppt_open, ppt_inspect, ppt_edit_text, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → mutate → save → check → finish
验证：ppt_structural；修复上限：1

### ppt.atomic_style

证据运行：12；任务：3-006, 4._Pre-Colonial_Filipino_Culture-001
工具面：ppt_open, ppt_inspect, ppt_style, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → mutate → save → check → finish
验证：ppt_structural；修复上限：1

### ppt.compose_from_slides

证据运行：6；任务：4._Pre-Colonial_Filipino_Culture-005
工具面：ppt_open, ppt_inspect, ppt_compose, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → compose → save → render_check → repair_once → finish
验证：ppt_structural, ppt_render, ppt_visual；修复上限：1

### ppt.content_and_layout

证据运行：6；任务：Aircraft_surface-004
工具面：ppt_open, ppt_inspect, ppt_edit_text, ppt_arrange, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → compose → save → render_check → repair_once → finish
验证：ppt_structural, ppt_render, ppt_visual；修复上限：1

### ppt.diagram_composition

证据运行：6；任务：Accounting Equation-045
工具面：ppt_open, ppt_inspect, ppt_compose, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → compose → save → render_check → repair_once → finish
验证：ppt_structural, ppt_render, ppt_visual；修复上限：1

### ppt.element_creation

证据运行：6；任务：HSC Careers and Expo FINAL COM MOD-008
工具面：ppt_open, ppt_inspect, ppt_compose, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → compose → save → render_check → repair_once → finish
验证：ppt_structural, ppt_render, ppt_visual；修复上限：1

### ppt.layout_reflow

证据运行：6；任务：HSC Careers and Expo FINAL COM MOD-038
工具面：ppt_open, ppt_inspect, ppt_arrange, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → compose → save → render_check → repair_once → finish
验证：ppt_structural, ppt_render, ppt_visual；修复上限：1

### ppt.source_grounded_build

证据运行：6；任务：html-report-quadrant-ppt
工具面：ppt_open, ppt_inspect, ppt_compose, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → compose → save → render_check → repair_once → finish
验证：ppt_structural, ppt_render, ppt_visual；修复上限：1

### ppt.source_sync

证据运行：6；任务：board-material-update-timeline-excel
工具面：ppt_open, ppt_inspect, ppt_edit_text, ppt_style, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → compose → save → render_check → repair_once → finish
验证：ppt_structural, ppt_render, ppt_visual；修复上限：1

### ppt.template_build

证据运行：6；任务：xmind-screenshot-template-ppt
工具面：ppt_open, ppt_inspect, ppt_compose, ppt_save, ppt_check, finish
标准阶段：resolve → inspect → compose → save → render_check → repair_once → finish
验证：ppt_structural, ppt_render, ppt_visual；修复上限：1

## 核心设计结论

1. Task contract 决定 Skill，trajectory 决定执行策略，避免关键词误分类。
2. 输入解析、输出路径、范围和验证合同必须由 Harness 编译并持久化。
3. 模型每轮只看主 Skill 的 5–7 个 canonical 工具；隐藏工具执行时同样拒绝。
4. 原子编辑走 resolve→inspect→mutate→save→check→finish；复杂任务增加 render/visual 和一次有限 repair。
5. 路径错误按 failure family 熔断，不能通过更换猜测文件名绕过。
6. trajectory 是研究旁路；核心任务不依赖记录成功。
