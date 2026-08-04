from __future__ import annotations

from pathlib import Path

from helpers import build_graph, seed_post


def test_graph_combined_uses_both_agents(tmp_path: Path):
    post_id = "11111111-2222-3333-4444-555555555555"
    graph = build_graph(tmp_path)
    seed_post(
        graph,
        post_id,
        topic="KI Agenten",
        platform="Instagram",
        target_audience="Marketing-Teams",
        tone_of_voice="locker",
    )
    result = graph.run("Erstelle eine Instagram Caption mit Hashtags und Bildidee.", post_id)

    assert result["used_agents"] == ["TextAgent", "ImageAgent"]
    assert "text" in result["generated_artifacts"]
    assert "image" in result["generated_artifacts"]
    assert result["generated_artifacts"]["image"]["image_filename"] == f"{post_id}.png"
