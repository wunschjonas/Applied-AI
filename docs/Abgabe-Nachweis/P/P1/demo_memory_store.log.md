# TAO-Demo – 4 – Expliziter Speichern-Wunsch → memory_store

**Eingabe:** `Merk dir bitte: Unsere Markenfarbe ist Petrolblau.`

Quelle: Graph-Lauf mit FakeHF (situation-abhängige Tool-Wahl), Trace wie bei `TAO_VERBOSE`.

```
[TAO 01] agent=init_state_node  status=success
  Thought:     Neuen Manager-Lauf starten und Trace anlegen.
  Action:      Graph-Zustand initialisieren
  Observation: Chat demo-store::manager_agent, Trace demo-store-trace, Plattform nicht gesetzt.

[TAO 02] agent=collect_post_data_node  status=skipped
  Thought:     Steckbrief-Felder aus der Nutzernachricht übernehmen.
  Action:      Post-Steckbrief aktualisieren
  Observation: Aktualisiert: nichts. Offen: keine. topic=Brand; platform=LinkedIn; target_audience=CMOs; tone_of_voice=klar

[TAO 03] agent=classify_intent_node  status=needs_input
  Thought:     No clear text or image intent detected.
  Action:      Intent klassifizieren
  Observation: Clarification is required before selecting an agent.

[TAO 04] agent=create_plan_node  status=success
  Thought:     Ablauf für Intent „Klärung nötig“ festlegen.
  Action:      Ausführungsplan erstellen
  Observation: Agenten: keine. Erwartete Artefakte: clarification_message. RAG-Check: ja.

[TAO 05] agent=rag_react_node  status=success
  Thought:     Dauerhafte Notiz in der Wissensbasis speichern.
  Action:      memory_store
  Observation: Stored memory note (27 chars), tags=['test'].

[TAO 06] agent=rag_react_node  status=skipped
  Thought:     Keine weiteren Tools nötig — mit aktuellem Kontext weiter.
  Action:      Tools überspringen
  Observation: Modell hat keinen weiteren Tool-Aufruf gewählt.

[TAO 07] agent=route_by_intent  status=success
  Thought:     Weiterleitung nach Intent „Klärung nötig“.
  Action:      Nach Intent routen
  Observation: Nächster Schritt: Klärungsfrage.

[TAO 08] agent=clarification_node  status=needs_input
  Thought:     Absicht unklar — nach Text, Bild oder beidem fragen.
  Action:      Klärung anfordern
  Observation: Kein Spezialist und kein HuggingFace-Aufruf.

[TAO 09] agent=save_trace_node  status=success
  Thought:     Lauf abschließen und Trace speichern.
  Action:      Chat, Trace und Logs persistieren
  Observation: Chat demo-store::manager_agent, Trace demo-store-trace, Agenten: keine.
```

**Sichtbare Tool-Actions:** `memory_store`
