# TAO-Demo – 1 – Unvollständiger Brief → check_post_data_completeness → Nachfrage

**Eingabe:** `Schreibe bitte einen LinkedIn Post.`

Quelle: Graph-Lauf mit FakeHF (situation-abhängige Tool-Wahl), Trace wie bei `TAO_VERBOSE`.

```
[TAO 01] agent=init_state_node  status=success
  Thought:     Neuen Manager-Lauf starten und Trace anlegen.
  Action:      Graph-Zustand initialisieren
  Observation: Chat demo-incomplete::manager_agent, Trace 17b5aeeb-ecc5-4be4-b5ed-9a9d7fa4b9bd, Plattform linkedin.

[TAO 02] agent=collect_post_data_node  status=success
  Thought:     Steckbrief-Felder aus der Nutzernachricht übernehmen.
  Action:      Post-Steckbrief aktualisieren
  Observation: Aktualisiert: platform. Offen: target_audience, tone_of_voice. topic=Nur Thema; platform=linkedin; target_audience=offen; tone_of_voice=offen

[TAO 03] agent=classify_intent_node  status=success
  Thought:     Detected text generation intent.
  Action:      Intent klassifizieren
  Observation: TextAgent selected.

[TAO 04] agent=create_plan_node  status=success
  Thought:     Ablauf für Intent „nur Text“ festlegen.
  Action:      Ausführungsplan erstellen
  Observation: Agenten: TextAgent. Erwartete Artefakte: text. RAG-Check: ja.

[TAO 05] agent=rag_react_node  status=warning
  Thought:     Vor der Generierung prüfen, ob der Steckbrief vollständig ist.
  Action:      check_post_data_completeness
  Observation: Unvollständig, fehlend: target_audience, tone_of_voice.

[TAO 06] agent=rag_react_node  status=skipped
  Thought:     Keine weiteren Tools nötig — mit aktuellem Kontext weiter.
  Action:      Tools überspringen
  Observation: Modell hat keinen weiteren Tool-Aufruf gewählt.

[TAO 07] agent=route_by_intent  status=success
  Thought:     Weiterleitung nach Intent „nur Text“.
  Action:      Nach Intent routen
  Observation: Nächster Schritt: TextAgent.

[TAO 08] agent=context_question_node  status=needs_input
  Thought:     Vor der Erzeugung fehlt noch „target_audience“.
  Action:      Steckbrief-Frage stellen
  Observation: Noch offen: target_audience, tone_of_voice. Kein Spezialist gestartet.

[TAO 09] agent=save_trace_node  status=needs_input
  Thought:     Lauf abschließen und Trace speichern.
  Action:      Chat, Trace und Logs persistieren
  Observation: Chat demo-incomplete::manager_agent, Trace 17b5aeeb-ecc5-4be4-b5ed-9a9d7fa4b9bd, Agenten: keine.

```

**Sichtbare Tool-Actions:** `check_post_data_completeness`
