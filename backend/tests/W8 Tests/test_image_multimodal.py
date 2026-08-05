from __future__ import annotations

from pathlib import Path

from helpers import FakeHF, build_agent_service, tiny_png_bytes

POST_ID = "bbbb1111-2222-3333-4444-555555555555"


def test_image_agent_uses_reference_image_for_img2img(tmp_path: Path):
    hf = FakeHF()
    service = build_agent_service(tmp_path, hf)
    service.post_repository.save(
        {
            "id": POST_ID,
            "title": "Testpost",
            "status": "preview_ready",
            "topic": "KI-Agenten",
            "platform": "instagram",
            "tone_of_voice": "professionell",
            "text_context": None,
            "text_length": None,
            "image_context": None,
            "image_style": None,
            "preview": {
                "generated_text": "Marketing-Text zum Bild.",
                "image_prompt_optional": "Ein alter Bildprompt.",
            },
        }
    )
    source = tiny_png_bytes()

    result = service.image_agent_chat(
        "Behalte die Komposition, aendere die Farbe zu Orange.",
        POST_ID,
        source_image=source,
        strength=0.55,
    )

    assert len(hf.img2img_calls) == 1
    assert hf.img2img_calls[0]["image_bytes"] == source
    assert hf.img2img_calls[0]["strength"] == 0.55
    artifact = result["generated_artifacts"]["image"]
    assert artifact["used_image_to_image"] is True
    assert artifact["generation_mode"] == "image_to_image"
    assert artifact["image_url"] == f"/generated-images/{POST_ID}.png"
    assert (tmp_path / "generated_images" / f"{POST_ID}.png").read_bytes() == b"fake-img2img-png-bytes"
