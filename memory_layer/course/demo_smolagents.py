"""
Demo: smolagents CodeAgent mit lokalem Memory Layer (MCP)

Voraussetzungen:
    1. Docker Container laeuft:
       docker run -d --name memory -p 8765:8765 -v memory_data:/app/data \
         -e MCP_STREAMABLE_HTTP_MODE=1 -e MCP_SSE_HOST=0.0.0.0 \
         -e MCP_SSE_PORT=8765 -e MCP_ALLOW_ANONYMOUS_ACCESS=true \
         -e MCP_MEMORY_STORAGE_BACKEND=sqlite_vec \
         doobidoo/mcp-memory-service:latest

    2. Python-Pakete:
       pip install "smolagents[mcp]"

    3. HuggingFace Token:
       $env:HF_TOKEN = "hf_euer_token"   (PowerShell)
       export HF_TOKEN="hf_euer_token"   (Linux/macOS)
"""

import os
import sys

from smolagents import CodeAgent, MCPClient, InferenceClientModel

MEMORY_URL = "http://localhost:8765/mcp"

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    print("FEHLER: Bitte HF_TOKEN als Umgebungsvariable setzen.")
    print("  PowerShell:  $env:HF_TOKEN = \"hf_euer_token_hier\"")
    print("  Linux/macOS: export HF_TOKEN=\"hf_euer_token_hier\"")
    sys.exit(1)

model = InferenceClientModel(
    model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
    token=HF_TOKEN,
)

server_params = {"url": MEMORY_URL, "transport": "streamable-http"}

print("=" * 60)
print("Verbinde mit Memory Layer auf", MEMORY_URL)
print("=" * 60)

with MCPClient(server_params) as tools:
    tool_names = [t.name for t in tools]
    print(f"\nVerfuegbare MCP-Tools: {tool_names}\n")

    agent = CodeAgent(tools=tools, model=model)

    # --- Test 1: Fakt speichern ---
    print("=" * 60)
    print("Test 1: Fakt im Memory speichern")
    print("=" * 60)
    result1 = agent.run(
        "Speichere folgendes im Memory: "
        "Ich studiere Informatik im Master an der HTWG Konstanz "
        "und interessiere mich besonders fuer AI Agents."
    )
    print(f"\nAntwort: {result1}")

    # --- Test 2: Fakt abrufen ---
    print("\n" + "=" * 60)
    print("Test 2: Gespeicherte Information abrufen")
    print("=" * 60)
    result2 = agent.run(
        "Durchsuche das Memory: Was weisst du ueber mich und mein Studium?"
    )
    print(f"\nAntwort: {result2}")

print("\n" + "=" * 60)
print("Demo abgeschlossen! Euer Memory Layer funktioniert.")
print("=" * 60)
