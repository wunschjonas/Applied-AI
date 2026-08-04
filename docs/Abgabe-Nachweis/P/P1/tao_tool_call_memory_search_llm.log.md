# TAO-Log – Tool-Call `call_memory_search` (LLM Function Calling, nicht forced)

Quelle: Docker-Backend-Logs (`TAO_VERBOSE`), Generierungsauftrag zum Fußball-Post mit gespeichertem WM-2014-Fact.

```
[TAO 05] agent=rag_react_node  status=success
  Thought:     Planning retrieval round 1.
  Action:      call_memory_search
  Observation: Retrieved 1 on-topic memory item(s). Summary: Deutschland hat 2014 die WM ('Weltmeisterschaft') im Fußball gewonnen

[TAO 06] agent=rag_react_node  status=skipped
  Thought:     Basierend auf dem gefundenen Eintrag könnte der Text so lauten: "🇩🇪 In 2014 feierte Deutschland die Weltmeisterschaft im Fußball! …"
  Action:      skip_memory_search
  Observation: No tool_calls; RAG skipped.
```

Entscheidender Nachweis: **Thought `Planning retrieval round 1.`** (nicht „Forced…“) + **Action `call_memory_search`** + Observation mit WM-2014-Fact.

TAO 06 = zweite ReAct-Runde ohne weiteren Tool-Call (normal).
