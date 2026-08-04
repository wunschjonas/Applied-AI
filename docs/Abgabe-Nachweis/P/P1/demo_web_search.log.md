# TAO-Demo – 3 – Aktuelles Thema → web_search + check_post_data_completeness

**Eingabe:** `Schreibe einen LinkedIn Post zu aktuellen KI Trends heute.`

Quelle: Graph-Lauf mit FakeHF (situation-abhängige Tool-Wahl), Trace wie bei `TAO_VERBOSE`.

```
[TAO 01] agent=init_state_node  status=success
  Thought:     Neuen Manager-Lauf starten und Trace anlegen.
  Action:      Graph-Zustand initialisieren
  Observation: Chat demo-web::manager_agent, Trace bcc75b61-1f87-4e7f-865e-863af940a3a7, Plattform linkedin.

[TAO 02] agent=collect_post_data_node  status=success
  Thought:     Steckbrief-Felder aus der Nutzernachricht übernehmen.
  Action:      Post-Steckbrief aktualisieren
  Observation: Aktualisiert: platform. Offen: keine. topic=KI Trends; platform=linkedin; target_audience=CMOs; tone_of_voice=professionell

[TAO 03] agent=classify_intent_node  status=success
  Thought:     Detected text generation intent.
  Action:      Intent klassifizieren
  Observation: TextAgent selected.

[TAO 04] agent=create_plan_node  status=success
  Thought:     Ablauf für Intent „nur Text“ festlegen.
  Action:      Ausführungsplan erstellen
  Observation: Agenten: TextAgent. Erwartete Artefakte: text. RAG-Check: ja.

[TAO 05] agent=rag_react_node  status=success
  Thought:     Aktuelle Infos im Web zu „aktueller trend marketing“ suchen.
  Action:      web_search (aktueller trend marketing)
  Observation: web_search results: 1. Top 10 Marketingtrends und Prioritäten 2025/2026: Jan 11, 2026 · Generative KI verändert nicht nur, wie Kunden suchen und kaufen, sondern auch Marketing als Disziplin. In diesem Ratgeber erfährst…

[TAO 06] agent=rag_react_node  status=success
  Thought:     Vor der Generierung Steckbrief-Vollständigkeit prüfen.
  Action:      check_post_data_completeness
  Observation: Steckbrief vollständig — Generierung kann starten.

[TAO 07] agent=rag_react_node  status=skipped
  Thought:     Keine weiteren Tools nötig — mit aktuellem Kontext weiter.
  Action:      Tools überspringen
  Observation: Modell hat keinen weiteren Tool-Aufruf gewählt.

[TAO 08] agent=route_by_intent  status=success
  Thought:     Weiterleitung nach Intent „nur Text“.
  Action:      Nach Intent routen
  Observation: Nächster Schritt: TextAgent.

[TAO 09] agent=TextAgent  status=success
  Thought:     Textauftrag in ein Modell-Prompt übersetzen.
  Action:      Text-Prompt bauen
  Observation: Plattform linkedin, Tonalität professionell.

[TAO 10] agent=TextAgent  status=success
  Thought:     Textmodell für Marketing-Copy aufrufen.
  Action:      Textmodell aufrufen
  Observation: Modell fake-text-model.

[TAO 11] agent=TextAgent  status=success
  Thought:     Modellantwort als Text übernehmen.
  Action:      Textantwort parsen
  Observation: 275 Zeichen empfangen.

[TAO 12] agent=TextAgent  status=success
  Thought:     Fertigen Marketing-Text als Artefakt zurückgeben.
  Action:      Text-Artefakt liefern
  Observation: 275 Zeichen, 4 Hashtags.

[TAO 13] agent=text_agent_node  status=success
  Thought:     Marketing-Text über den TextAgent erzeugen.
  Action:      TextAgent aufrufen
  Observation: Text-Artefakt im Graph-State.; 275 Zeichen; 4 Hashtags.

[TAO 14] agent=validation_node  status=success
  Thought:     Artefakte prüfen (Ergebnis: valid).
  Action:      Ergebnisse validieren
  Observation: Feedback: . Retries Text=0, Bild=0.

[TAO 15] agent=assemble_response_node  status=success
  Thought:     Antwort für Intent „nur Text“ aus den Artefakten bauen.
  Action:      Antwort zusammensetzen
  Observation: Text-Erfolg zusammengestellt.

[TAO 16] agent=persist_post_node  status=success
  Thought:     Erzeugte Inhalte in der Post-Vorschau speichern.
  Action:      Preview persistieren
  Observation: Aktualisiert: generated_text, hashtags, post_structure.

[TAO 17] agent=save_trace_node  status=success
  Thought:     Lauf abschließen und Trace speichern.
  Action:      Chat, Trace und Logs persistieren
  Observation: Chat demo-web::manager_agent, Trace bcc75b61-1f87-4e7f-865e-863af940a3a7, Agenten: TextAgent.

```

**Sichtbare Tool-Actions:** `web_search (aktueller trend marketing)`, `check_post_data_completeness`
