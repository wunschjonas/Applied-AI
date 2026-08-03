from __future__ import annotations

from pathlib import Path

from app.graphs.support import post_fields
from app.graphs.support.messages import BRIEF_FOLLOWUP_PREFIX
from app.services.agent_service import AgentService
from tests.test_phase1_agent_refactor import FakeHF, build_graph, seed_post

POST_A = "aaaa1111-2222-3333-4444-555555555555"
POST_B = "bbbb1111-2222-3333-4444-555555555555"


def stored_post(graph, post_id: str) -> dict:
    return graph.post_repository.get(post_id) or {}


def test_extract_platform_ignores_substrings():
    assert post_fields.extract_platform("Schreibe einen Text") is None
    assert post_fields.extract_platform("Post fuer LinkedIn") == "linkedin"
    assert post_fields.extract_platform("Mach einen Tweet daraus") == "x"
    assert post_fields.extract_platform("Bitte auf Insta posten") == "instagram"


def test_extract_fields_reads_topic_tone_and_platform():
    post = {"topic": None, "platform": None, "tone_of_voice": None, "target_audience": None}
    updates = post_fields.extract_fields(
        "Ein locker geschriebener LinkedIn Post ueber nachhaltiges Bauen.", post
    )

    assert updates["platform"] == "linkedin"
    assert updates["tone_of_voice"] == "locker"
    assert updates["topic"].startswith("nachhaltiges Bauen")


def test_extract_fields_answers_the_awaited_free_text_field():
    post = {"topic": None, "platform": "linkedin", post_fields.AWAITING_FIELD_KEY: "topic"}
    updates = post_fields.extract_fields("Unser neues Recycling-Verfahren", post)

    assert updates == {"topic": "Unser neues Recycling-Verfahren"}


def test_extract_fields_reads_tonality_label_and_free_tone():
    post = {"topic": "KI", "platform": "linkedin", "tone_of_voice": None, "target_audience": None}
    updates = post_fields.extract_fields(
        "Zielgruppe: Meine Freunde. Tonalitaet: Angeberisch", post
    )

    assert updates["target_audience"] == "Meine Freunde"
    assert updates["tone_of_voice"] == "Angeberisch"


def test_extract_fields_answers_awaited_custom_tone():
    post = {
        "topic": "KI",
        "platform": "linkedin",
        "tone_of_voice": None,
        post_fields.AWAITING_FIELD_KEY: "tone_of_voice",
    }
    updates = post_fields.extract_fields("Angeberisch", post)

    assert updates == {"tone_of_voice": "Angeberisch"}


def test_extract_fields_keeps_awaited_field_empty_on_unrelated_answer():
    post = {"topic": None, "platform": None, post_fields.AWAITING_FIELD_KEY: "topic"}
    updates = post_fields.extract_fields("Instagram", post)

    assert updates == {"platform": "instagram"}


def test_manager_asks_for_topic_before_calling_any_specialist(tmp_path: Path):
    graph = build_graph(tmp_path)
    seed_post(graph, POST_A)
    result = graph.run("Hilf mir mal mit dem Post.", POST_A)

    assert result["used_agents"] == []
    assert result["generated_artifacts"] == {}
    assert post_fields.FIELD_QUESTIONS["topic"] in result["assistant_message"]
    assert stored_post(graph, POST_A)[post_fields.AWAITING_FIELD_KEY] == "topic"


def test_manager_stores_answer_and_asks_for_the_next_field(tmp_path: Path):
    graph = build_graph(tmp_path)
    seed_post(graph, POST_A, **{post_fields.AWAITING_FIELD_KEY: "topic"})
    result = graph.run("Nachhaltiges Bauen im Mittelstand", POST_A)

    post = stored_post(graph, POST_A)
    assert post["topic"] == "Nachhaltiges Bauen im Mittelstand"
    assert result["used_agents"] == []
    assert post_fields.FIELD_QUESTIONS["platform"] in result["assistant_message"]
    assert post[post_fields.AWAITING_FIELD_KEY] == "platform"


def test_manager_saves_platform_answer(tmp_path: Path):
    graph = build_graph(tmp_path)
    seed_post(graph, POST_A, topic="Nachhaltiges Bauen", **{post_fields.AWAITING_FIELD_KEY: "platform"})
    graph.run("LinkedIn bitte", POST_A)

    assert stored_post(graph, POST_A)["platform"] == "linkedin"


def test_manager_generates_once_topic_and_platform_are_known(tmp_path: Path):
    graph = build_graph(tmp_path)
    seed_post(graph, POST_A, topic="KI-Agenten im Marketing", platform="linkedin")
    result = graph.run("Schreibe jetzt den Post.", POST_A)

    assert result["used_agents"] == ["TextAgent"]
    preview = stored_post(graph, POST_A)["preview"]
    assert preview["generated_text"] == result["generated_artifacts"]["text"]["generated_text"]
    assert stored_post(graph, POST_A)["status"] == "preview_ready"


def test_incomplete_brief_blocks_generation_without_explicit_order(tmp_path: Path):
    graph = build_graph(tmp_path)
    seed_post(graph, POST_A, topic="KI-Agenten im Marketing", platform="linkedin")
    result = graph.run("Ich brauche bitte eine Caption dazu.", POST_A)

    assert result["used_agents"] == []
    assert "text" not in result["generated_artifacts"]
    assert post_fields.FIELD_QUESTIONS["target_audience"] in result["assistant_message"]
    assert "Soll ich Marketing-Text" not in result["assistant_message"]


def test_generation_appends_followup_question_for_an_open_field(tmp_path: Path):
    graph = build_graph(tmp_path)
    seed_post(graph, POST_A, topic="KI-Agenten im Marketing", platform="linkedin")
    result = graph.run("Schreibe jetzt den Post.", POST_A)

    assert BRIEF_FOLLOWUP_PREFIX in result["assistant_message"]
    assert post_fields.FIELD_QUESTIONS["target_audience"] in result["assistant_message"]
    assert stored_post(graph, POST_A)[post_fields.AWAITING_FIELD_KEY] == "target_audience"


def test_post_status_inquiry_summarizes_current_post(tmp_path: Path):
    graph = build_graph(tmp_path)
    seed_post(
        graph,
        POST_A,
        topic="Nachhaltiges Bauen",
        platform="linkedin",
        target_audience="Bauleiter",
        tone_of_voice="sachlich",
    )
    result = graph.run("Was wissen wir schon zum aktuellen Post?", POST_A)

    assert result["used_agents"] == []
    assert "post_status_answer" in result["generated_artifacts"]
    assert "Nachhaltiges Bauen" in result["assistant_message"]
    assert "linkedin" in result["assistant_message"].lower()
    assert "Bauleiter" in result["assistant_message"]


def test_explicit_order_generates_despite_missing_fields(tmp_path: Path):
    graph = build_graph(tmp_path)
    seed_post(graph, POST_B)
    result = graph.run("Erstelle ein Bild ueber blaue Baeume auf dem Mond. Nur das Bild!", POST_B)

    assert result["used_agents"] == ["ImageAgent"]
    post = stored_post(graph, POST_B)
    assert post["topic"].startswith("blaue Baeume")
    assert post["preview"]["image_url"] == f"/generated-images/{POST_B}.png"
    assert post["preview"]["image_filename"] == f"{POST_B}.png"


def test_preview_merges_text_and_image_across_turns(tmp_path: Path):
    graph = build_graph(tmp_path)
    seed_post(graph, POST_A, topic="KI-Agenten im Marketing", platform="linkedin")
    graph.run("Schreibe jetzt den Post.", POST_A)
    graph.run("Erstelle jetzt noch das Bild dazu. Nur das Bild!", POST_A)

    preview = stored_post(graph, POST_A)["preview"]
    assert preview["generated_text"]
    assert preview["image_url"] == f"/generated-images/{POST_A}.png"


def test_stored_post_fields_reach_the_specialist_brief(tmp_path: Path):
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf)
    seed_post(
        graph,
        POST_A,
        topic="Nachhaltiges Bauen",
        platform="linkedin",
        target_audience="Bauleiter im Mittelstand",
        tone_of_voice="sachlich",
    )
    graph.run("Schreibe jetzt den Post.", POST_A)

    text_brief = next(prompt for prompt in hf.user_prompts if "Erstelle den Marketing-Text" in prompt)
    assert "Nachhaltiges Bauen" in text_brief
    assert "Bauleiter im Mittelstand" in text_brief


def build_agent_service(tmp_path: Path, hf: FakeHF) -> AgentService:
    from app.core import config as config_module

    config_module.settings.chats_file = tmp_path / "chats.json"
    config_module.settings.traces_file = tmp_path / "traces.json"
    config_module.settings.agent_logs_file = tmp_path / "agent_logs.json"
    config_module.settings.posts_file = tmp_path / "posts.json"
    config_module.settings.generated_images_dir = tmp_path / "generated_images"

    service = AgentService()
    service._hf = lambda: hf
    return service


def test_text_agent_chat_refines_and_stores_the_preview(tmp_path: Path):
    hf = FakeHF()
    service = build_agent_service(tmp_path, hf)
    service.post_repository.save(
        {
            "id": POST_A,
            "title": "Testpost",
            "status": "preview_ready",
            "topic": "KI-Agenten",
            "platform": "linkedin",
            "tone_of_voice": "sachlich",
            "target_audience": "CMOs",
            "additional_context": None,
            "preview": {"generated_text": "Alter Text ueber KI-Agenten.", "hashtags": ["#alt"]},
        }
    )

    result = service.text_agent_chat("Mach den Einstieg kuerzer.", POST_A)

    refine_brief = next(prompt for prompt in hf.user_prompts if "Verfeinerungsauftrag" in prompt)
    assert "Alter Text ueber KI-Agenten." in refine_brief
    assert "Mach den Einstieg kuerzer." in refine_brief

    preview = service.post_repository.get(POST_A)["preview"]
    assert preview["generated_text"] == result["generated_artifacts"]["text"]["generated_text"]
    assert preview["generated_text"] != "Alter Text ueber KI-Agenten."


def test_post_init_writes_welcome_message_with_title(tmp_path: Path):
    from app.core import config as config_module
    from app.schemas.post import PostInit
    from app.services.post_service import PostService

    config_module.settings.chats_file = tmp_path / "chats.json"
    config_module.settings.traces_file = tmp_path / "traces.json"
    config_module.settings.agent_logs_file = tmp_path / "agent_logs.json"
    config_module.settings.posts_file = tmp_path / "posts.json"
    # Force template welcome so the test does not depend on a live HF token.
    config_module.settings.hf_token = None

    service = PostService()
    response = service.init_post(PostInit(title="Nachhaltige Mode"))

    assert response.welcome_message
    assert "Nachhaltige Mode" in response.welcome_message
    assert response.missing_fields == [
        "topic",
        "platform",
        "target_audience",
        "tone_of_voice",
    ]
    post = service.store.get(response.post_id)
    assert post[post_fields.AWAITING_FIELD_KEY] == "topic"
    chat = service.chat_service.get_chat(f"{response.post_id}::manager_agent")
    assert chat["messages"][0]["role"] == "AGENT"
    assert chat["messages"][0]["content"] == response.welcome_message


def test_image_agent_chat_regenerates_the_post_image(tmp_path: Path):
    hf = FakeHF()
    service = build_agent_service(tmp_path, hf)
    service.post_repository.save(
        {
            "id": POST_B,
            "title": "Testpost",
            "status": "preview_ready",
            "topic": "KI-Agenten",
            "platform": "instagram",
            "additional_context": None,
            "preview": {
                "generated_text": "Marketing-Text zum Bild.",
                "image_prompt_optional": "Ein alter Bildprompt mit blauem Hintergrund.",
            },
        }
    )

    result = service.image_agent_chat("Mach den Hintergrund gruen.", POST_B)

    refine_brief = next(prompt for prompt in hf.user_prompts if "Verfeinerungsauftrag" in prompt)
    assert "Ein alter Bildprompt mit blauem Hintergrund." in refine_brief
    assert "Marketing-Text zum Bild." in refine_brief
    assert hf.img2img_calls == []

    preview = service.post_repository.get(POST_B)["preview"]
    assert preview["image_url"] == f"/generated-images/{POST_B}.png"
    assert preview["generated_text"] == "Marketing-Text zum Bild."
    assert (tmp_path / "generated_images" / f"{POST_B}.png").exists()
    assert result["generated_artifacts"]["image"]["image_filename"] == f"{POST_B}.png"


def _tiny_png_bytes(color: tuple[int, int, int] = (20, 40, 60)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_agent_chat_uses_img2img_when_source_image_given(tmp_path: Path):
    hf = FakeHF()
    service = build_agent_service(tmp_path, hf)
    service.post_repository.save(
        {
            "id": POST_B,
            "title": "Testpost",
            "status": "preview_ready",
            "topic": "KI-Agenten",
            "platform": "instagram",
            "additional_context": None,
            "preview": {
                "generated_text": "Marketing-Text zum Bild.",
                "image_prompt_optional": "Ein alter Bildprompt.",
            },
        }
    )
    source = _tiny_png_bytes()

    result = service.image_agent_chat(
        "Behalte die Komposition, aendere die Farbe zu Orange.",
        POST_B,
        source_image=source,
        strength=0.55,
    )

    assert len(hf.img2img_calls) == 1
    assert hf.img2img_calls[0]["image_bytes"] == source
    assert hf.img2img_calls[0]["strength"] == 0.55
    artifact = result["generated_artifacts"]["image"]
    assert artifact["used_image_to_image"] is True
    assert artifact["generation_mode"] == "image_to_image"
    assert artifact["used_reference_image"] is True
    assert artifact["img2img_source"] == "reference"
    assert artifact["image_url"] == f"/generated-images/{POST_B}.png"
    assert (tmp_path / "generated_images" / f"{POST_B}.png").read_bytes() == b"fake-img2img-png-bytes"
    assert "neues Bild" in result["assistant_message"].lower() or "Referenzbild" in result["assistant_message"]


def test_image_agent_chat_combines_current_and_reference_images(tmp_path: Path):
    hf = FakeHF()
    service = build_agent_service(tmp_path, hf)
    service.post_repository.save(
        {
            "id": POST_B,
            "title": "Testpost",
            "status": "preview_ready",
            "topic": "KI-Agenten",
            "platform": "instagram",
            "preview": {
                "image_prompt_optional": "Alter Prompt",
                "image_filename": f"{POST_B}.png",
                "image_url": f"/generated-images/{POST_B}.png",
            },
        }
    )
    current = _tiny_png_bytes(color=(10, 20, 30))
    reference = _tiny_png_bytes(color=(200, 100, 50))
    (tmp_path / "generated_images").mkdir(parents=True, exist_ok=True)
    (tmp_path / "generated_images" / f"{POST_B}.png").write_bytes(current)

    result = service.image_agent_chat(
        "Mische beide Motive zu einem sommerlichen Post.",
        POST_B,
        source_image=reference,
    )

    artifact = result["generated_artifacts"]["image"]
    assert artifact["used_current_image"] is True
    assert artifact["used_reference_image"] is True
    assert artifact["img2img_source"] == "current_plus_reference"
    assert artifact["generation_mode"] == "image_to_image"
    assert len(hf.img2img_calls) == 1
    assert hf.img2img_calls[0]["image_bytes"] != current
    assert hf.img2img_calls[0]["image_bytes"] != reference
    assert "Post-Bild" in result["assistant_message"] and "Referenzbild" in result["assistant_message"]


def test_image_agent_chat_falls_back_to_txt2img_when_img2img_fails(tmp_path: Path):
    class FailingImg2ImgHF(FakeHF):
        def generate_image_from_image(self, prompt, image_bytes, *, negative_prompt=None, strength=0.7):
            self.img2img_calls.append({"prompt": prompt, "image_bytes": image_bytes})
            raise RuntimeError("HuggingFace image-to-image unsupported or unavailable model")

    hf = FailingImg2ImgHF()
    service = build_agent_service(tmp_path, hf)
    service.post_repository.save(
        {
            "id": POST_B,
            "title": "Testpost",
            "status": "preview_ready",
            "topic": "KI-Agenten",
            "platform": "instagram",
            "preview": {"image_prompt_optional": "Alter Prompt"},
        }
    )

    result = service.image_agent_chat(
        "Beziehe das Referenzbild ein und mache es sommerlicher.",
        POST_B,
        source_image=_tiny_png_bytes(),
    )

    artifact = result["generated_artifacts"]["image"]
    assert artifact["generation_mode"] == "text_to_image_fallback"
    assert artifact["used_image_to_image"] is False
    assert artifact["image_url"] == f"/generated-images/{POST_B}.png"
    assert (tmp_path / "generated_images" / f"{POST_B}.png").read_bytes() == b"fake-png-bytes"
    assert "neues Bild" in result["assistant_message"].lower() or "Referenzbild" in result["assistant_message"]


def test_image_agent_chat_multipart_accepts_source_image(tmp_path: Path):
    from fastapi.testclient import TestClient

    from app.core import config as config_module
    from app.main import app
    from app.services.agent_service import AgentService

    previous = {
        "chats_file": config_module.settings.chats_file,
        "traces_file": config_module.settings.traces_file,
        "agent_logs_file": config_module.settings.agent_logs_file,
        "posts_file": config_module.settings.posts_file,
        "generated_images_dir": config_module.settings.generated_images_dir,
    }
    import app.api.routes_image_agent as image_routes

    previous_service = image_routes.agent_service

    try:
        config_module.settings.chats_file = tmp_path / "chats.json"
        config_module.settings.traces_file = tmp_path / "traces.json"
        config_module.settings.agent_logs_file = tmp_path / "agent_logs.json"
        config_module.settings.posts_file = tmp_path / "posts.json"
        config_module.settings.generated_images_dir = tmp_path / "generated_images"

        hf = FakeHF()
        service = AgentService()
        service._hf = lambda: hf  # type: ignore[method-assign]
        service.post_repository.save(
            {
                "id": POST_A,
                "title": "Testpost",
                "status": "preview_ready",
                "topic": "KI",
                "platform": "linkedin",
                "preview": {"image_prompt_optional": "Alter Prompt"},
            }
        )

        image_routes.agent_service = service
        client = TestClient(app)
        response = client.post(
            "/api/agents/image/chat",
            data={"message": "Mach es warmer.", "post_id": POST_A, "strength": "0.6"},
            files={"source_image": ("ref.png", _tiny_png_bytes(), "image/png")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["generated_artifacts"]["image"]["used_image_to_image"] is True
        assert len(hf.img2img_calls) == 1
    finally:
        image_routes.agent_service = previous_service
        for key, value in previous.items():
            setattr(config_module.settings, key, value)
