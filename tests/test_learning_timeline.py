from app.data.synthetic_incidents import build_learning_timeline, summarize_pattern_memory


def test_build_learning_timeline_has_growth_story():
    timeline = build_learning_timeline()
    assert len(timeline) >= 4
    assert any(item["title"].startswith("Incident") for item in timeline)
    assert any("Pattern" in item["title"] for item in timeline)


def test_summarize_pattern_memory_describes_recurring_services():
    summary = summarize_pattern_memory()
    assert "checkout-service" in summary.lower()
    assert "pattern" in summary.lower()
