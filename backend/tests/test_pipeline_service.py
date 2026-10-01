from module_pipeline.service.pipeline_service import PipelineService


def test_dashboard_summary_contains_pipeline_workflow_counts():
    summary = PipelineService.get_dashboard_summary()

    assert summary["metrics"][0]["label"] == "有效资讯"
    assert summary["metrics"][0]["value"] >= 20
    assert {item["status"] for item in summary["collect_status"]} == {"running", "success", "warning"}
    assert any(topic["name"] == "管道完整性管理" for topic in summary["hot_topics"])


def test_intelligence_list_can_filter_by_category():
    result = PipelineService.list_intelligence(category="paper")

    assert result["total"] == 2
    assert all(item["category"] == "paper" for item in result["rows"])


def test_intelligence_list_can_search_domain_keyword():
    result = PipelineService.list_intelligence(keyword="磁各向异性")

    assert result["total"] == 1
    assert result["rows"][0]["id"] == "paper-001"


def test_intelligence_detail_returns_expected_item():
    detail = PipelineService.get_intelligence_detail("paper-001")

    assert detail["id"] == "paper-001"
    assert "磁各向异性" in detail["title"]
    assert "related_topics" in detail


def test_intelligence_detail_raises_for_unknown_item():
    try:
        PipelineService.get_intelligence_detail("missing")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown intelligence item")


def test_collect_task_can_be_run_manually():
    result = PipelineService.run_collect_task("task-news")

    assert result["id"] == "task-news"
    assert result["status"] == "success"
    assert result["progress"] == 100
    assert "手动运行完成" in result["latest_message"]


def test_report_export_contains_domain_sections():
    content = PipelineService.export_report_markdown("report-route")

    assert "# 磁应力监测技术路线建议" in content
    assert "## 重点主题" in content
    assert "磁各向异性" in content


def test_knowledge_base_returns_documents():
    docs = PipelineService.list_knowledge_documents()

    assert docs["total"] >= 3
    assert any("设计方案" in item["name"] for item in docs["rows"])
