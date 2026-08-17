import pytest
from agent.tools.ppt_tools import (
    _workflow_pipeline_slide,
    _html_slide,
    _new_deck,
    _clean_presentation_title,
    _quality_check,
)
from agent.state import RunState


class MockHarness:
    def __init__(self):
        self.state = RunState()
        self.deck = None


def test_title_sanitizer():
    assert _clean_presentation_title("AI Agent 核心架构与运行时全景 (HTML 页面风格)") == "AI Agent 核心架构与运行时全景"
    assert _clean_presentation_title("端到端认知与执行流水线 (PPTX 原生元素)") == "端到端认知与执行流水线"
    assert _clean_presentation_title("基于现代 Web 组件网格排版，实时展示调度指标") == "实时展示调度指标"


def test_workflow_pipeline_and_html_vector_slide_overhaul():
    h = MockHarness()
    _new_deck(h, "AI Agent 工作流程", "")

    # Slide 1: workflow_pipeline with 5 steps
    _workflow_pipeline_slide(
        h,
        title="AI Agent 端到端认知与执行流水线 (PPTX 原生元素)",
        steps=[
            {
                "title": "意图感知",
                "action": "多模态语义解析与消歧",
                "bullets": [
                    "用户意图精确抽取与参数结构化",
                    "环境上下文依赖注入与边界建模",
                    "歧义意图主动反问与目标澄清",
                ],
                "tag": "NLU",
            },
            {
                "title": "动态规划",
                "action": "ReAct 推理与任务图构建",
                "bullets": [
                    "多阶段长程目标拓扑排序分解",
                    "动态思维链推理与执行路径剪枝",
                    "工具依赖与前置条件实时校验",
                ],
                "tag": "Planner",
            },
            {
                "title": "工具调度",
                "action": "异构 API 并行与流式执行",
                "bullets": [
                    "沙箱隔离环境安全参数化调用",
                    "异步高并发执行与流式响应收集",
                    "运行时异常捕获与动态自愈降级",
                ],
                "tag": "Executor",
            },
            {
                "title": "质检验收",
                "action": "多源聚合与自省对齐",
                "bullets": [
                    "静态规则审计与动态运行状态检验",
                    "业务指标对齐度打分与可信度签名",
                    "多源执行结果交叉一致性复核",
                ],
                "tag": "Evaluator",
            },
            {
                "title": "终态交付",
                "action": "闭环反馈与记忆固化",
                "bullets": [
                    "高质成果规范化输出与用户确认",
                    "增量经验自动固化至长期向量库",
                    "人机协同多轮迭代与终态归档",
                ],
                "tag": "Memory",
            },
        ],
        takeaway="核心结论: 核心价值: 实现从非结构化指令到确定性高质交付物的端到端自主闭环演进",
        slide_number=1,
    )

    # Slide 2: html_slide
    html_code = """
<div class="slide" style="background: #0f172a;">
  <h1>AI Agent 核心架构与运行时全景 (HTML 页面风格)</h1>
  <p class="subtitle">基于现代 Web 组件网格排版，实时展示 Agent 双循环状态机与分布式调度指标</p>
  <div class="grid-3">
    <div class="card">
      <span class="badge">RUNNING</span>
      <h3>01. 感知与意图解析层</h3>
      <ul>
        <li>统一接收语音、文本与文档多模态数据输入</li>
        <li>高维特征向量空间匹配与上下文依赖注入</li>
        <li>生成结构化 AST 参数拓扑树并划定安全边界</li>
      </ul>
      <span class="tech">NLU Core</span>
    </div>
    <div class="card">
      <span class="badge">ACTIVE</span>
      <h3>02. 动态规划与执行引擎</h3>
      <ul>
        <li>ReAct 循环推理机制驱动多 Agent 协同分工</li>
        <li>分布式异步并发调度外部异构工具与沙箱</li>
        <li>运行时异常自动熔断、超时重试与自愈降级</li>
      </ul>
      <span class="tech">ReAct Engine</span>
    </div>
    <div class="card">
      <span class="badge">READY</span>
      <h3>03. 质量门禁与自省验收</h3>
      <ul>
        <li>静态代码审计与动态运行时鲁棒性验收</li>
        <li>对齐业务目标指标并生成可解释审计日志</li>
        <li>交付确定性高质成果并将经验固化至长期库</li>
      </ul>
      <span class="tech">Evaluator</span>
    </div>
  </div>
</div>
"""
    _html_slide(h, html=html_code, slide_number=2)

    # Check Slide 1
    s1 = h.deck.slides[0]
    s1_title = s1.shapes[3].text_frame.text
    assert "原生元素" not in s1_title
    assert "AI Agent 端到端认知与执行流水线" in s1_title

    # Check Slide 2
    s2 = h.deck.slides[1]
    s2_title = s2.shapes[1].text_frame.text
    assert "(HTML 页面风格)" not in s2_title
    assert "AI Agent 核心架构与运行时全景" in s2_title

    # Check Slide 2 Card 1 bullet boxes - MUST NOT contain concatenated card title or badges
    bullet_boxes = [
        sh.text_frame.text
        for sh in s2.shapes
        if getattr(sh, "has_text_frame", False) and "统一接收" in sh.text_frame.text
    ]
    assert len(bullet_boxes) == 1
    assert not bullet_boxes[0].startswith("• RUNNING")
    assert "• 统一接收语音、文本与文档多模态数据输入" in bullet_boxes[0]

    # Check Slide 1 Deliverables
    s1_delivs = [
        sh.text_frame.text
        for sh in s1.shapes
        if getattr(sh, "has_text_frame", False) and "产物" in sh.text_frame.text
    ]
    # In this test we didn't specify deliverable yet, so let's verify quality check passes
    quality_json = _quality_check(h)
    assert '"passed": true' in quality_json


def test_workflow_pipeline_with_deliverables_and_file_html(tmp_path):
    h = MockHarness()
    _new_deck(h, "AI Agent 工作流程与架构", "")

    # Slide 1 with deliverable pills
    _workflow_pipeline_slide(
        h,
        title="AI Agent 端到端工作流程",
        steps=[
            {
                "title": "意图感知",
                "action": "多模态语义解析、消歧与约束建模",
                "bullets": [
                    "多模态输入流统一接入与领域上下文依赖绑定",
                    "高维向量空间语义匹配与实体参数强类型结构化抽取",
                    "低置信度意图主动多轮反问与操作安全边界划定",
                ],
                "deliverable": "产物: 结构化 Intent AST 参数树",
                "tag": "NLU-Parser",
            },
            {
                "title": "动态规划",
                "action": "ReAct 推理、拓扑分解与路径剪枝",
                "bullets": [
                    "多阶段长程目标拓扑排序与动态 DAG 任务图分解",
                    "思维链 (CoT) 实时推理与次优路径启发式剪枝",
                    "工具集前置依赖校验与状态回滚检查点配置",
                ],
                "deliverable": "产物: DAG 动态规划执行图",
                "tag": "ReAct-Planner",
            },
        ],
        takeaway="实现从非结构化指令到确定性高质交付物的端到端自主闭环演进",
        slide_number=1,
    )

    s1 = h.deck.slides[0]
    s1_texts = [
        sh.text_frame.text
        for sh in s1.shapes
        if getattr(sh, "has_text_frame", False) and "Intent AST" in sh.text_frame.text
    ]
    assert len(s1_texts) >= 1
    assert "Intent AST 参数树" in s1_texts[0]

    # Slide 2 via HTML file
    html_file = tmp_path / "slide2.html"
    html_file.write_text(
        """
<div class="slide" style="background: #0f172a;">
  <h1>AI Agent 核心架构与运行时全景</h1>
  <p class="subtitle">统一双循环状态机驱动的分布式智能体调度平台与质检矩阵</p>
  <div class="grid-3">
    <div class="card">
      <span class="badge">RUNNING</span>
      <h3>01. 感知与意图解析层</h3>
      <div class="metric-bar">⚡ 响应时延 &lt;120ms · 语义置信度 0.94</div>
      <ul>
        <li>多模态输入统一接入、高维特征向量空间对齐与依赖上下文注入</li>
        <li>基于领域知识图谱的歧义消歧，生成结构化 AST 参数拓扑树</li>
        <li>滑动窗口长上下文智能压缩与多轮会话状态机持久化管理</li>
      </ul>
      <span class="tech">AST Parser · Embedding Index</span>
    </div>
  </div>
</div>
""",
        encoding="utf-8",
    )

    from agent import config
    from unittest.mock import patch

    with patch.object(config, "sandbox_root", return_value=tmp_path):
        _html_slide(h, file_path="slide2.html", slide_number=2)

    s2 = h.deck.slides[1]
    s2_title = s2.shapes[1].text_frame.text
    assert "AI Agent 核心架构与运行时全景" in s2_title
    s2_metrics = [
        sh.text_frame.text
        for sh in s2.shapes
        if getattr(sh, "has_text_frame", False) and "响应时延" in sh.text_frame.text
    ]
    assert len(s2_metrics) >= 1

