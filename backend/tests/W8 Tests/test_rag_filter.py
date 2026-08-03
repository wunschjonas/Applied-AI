from __future__ import annotations

from app.services.rag_service import filter_rag_context


def test_filter_rag_drops_alien_memory_for_football_topic():
    raw = (
        "1. Aliens bauen ein Auto auf dem Mond mit Neonlichtern.\n"
        "2. Fussball-WM Highlights: spannende Tore und Stadionatmosphaere.\n"
        "3. Unser Sponsoring fuer den lokalen Fussballverein."
    )
    filtered = filter_rag_context(
        raw,
        topic="Fussball",
        user_message="Erstelle ein Bild zum Fussball-Post",
    )
    lowered = filtered.casefold()
    assert "fussball" in lowered
    assert "aliens" not in lowered
