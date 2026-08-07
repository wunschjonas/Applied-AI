from __future__ import annotations

from pathlib import Path

from helpers import FakeHF, build_agent_service, tiny_png_bytes

POST_ID = "bbbb1111-2222-3333-4444-555555555555"


def _seed_post(service) -> None:
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


def test_image_agent_refines_post_image_via_img2img(tmp_path: Path):
    hf = FakeHF()
    service = build_agent_service(tmp_path, hf)
    _seed_post(service)
    current = tiny_png_bytes(color=(30, 30, 90))
    (tmp_path / "generated_images").mkdir(parents=True, exist_ok=True)
    (tmp_path / "generated_images" / f"{POST_ID}.png").write_bytes(current)

    result = service.image_agent_chat("Mach das Bild etwas waermer.", POST_ID)

    assert len(hf.img2img_calls) == 1
    assert hf.img2img_calls[0]["image_bytes"] == current
    artifact = result["generated_artifacts"]["image"]
    assert artifact["generation_mode"] == "image_to_image"
    assert artifact["img2img_source"] == "current_post"
    assert artifact["used_current_image"] is True
    assert artifact["image_url"] == f"/generated-images/{POST_ID}.png"
