# Build Your Own Claude Code — Write-up

## Introduction

Welcome to **Build Your Own Claude Code**, a challenge where you recreate the core of a terminal AI coding assistant from scratch.

Claude Code is a tool that autonomously understands your codebase and completes programming tasks — reading files, writing edits, running commands, and iterating until the job is done. By rebuilding it, you learn exactly how tools like GitHub Copilot or Cursor work under the hood.

The challenge walks you through the fundamental building blocks of modern AI agents:

- **LLM APIs** — communicating with a language model over HTTP
- **Tool calling** — defining JSON schemas that let the model trigger real actions
- **Agent loops** — letting the model think, act, observe results, and repeat
- **Context management** — maintaining conversation history across turns

Advanced stages then extend the agent with MCP support, LSP integration, interactive TUI, and web search.

---

## Stage 1 — Connecting to the LLM

This is the foundation: getting the program to talk to a language model at all.

[app/main.py](app/main.py) is the single entry point. It:

1. **Reads configuration from env vars** — an OpenRouter API key and base URL, making the setup provider-agnostic via the OpenAI-compatible REST interface.
2. **Parses a `-p` prompt argument** — the user's instruction passed from the command line.
3. **Sends a chat completion request** to `anthropic/claude-haiku-4.5` via the OpenAI SDK, forwarding the user prompt as a single `user` message.
4. **Prints the model's text reply** from `chat.choices[0].message.content`.

At this point the agent is just a thin wrapper around the API — it can chat, but has no awareness of the filesystem or any tools.

---

## Stage 2 — Advertising the Read Tool

### Where this sits in Claude Code

In the real Claude Code, every request to the LLM includes a `tools` list — a catalogue of capabilities the model is allowed to invoke (Read, Write, Bash, etc.). The model reads these definitions and decides autonomously whether to call one, based on what the user asked. **Advertising a tool is what gives the model agency**: without it, the model can only reply in plain text.

Stage 2 adds the first entry to that catalogue: the `Read` tool.

### What was done

A `tools` array was added to the `chat.completions.create` call ([app/main.py:27-45](app/main.py#L27-L45)):

```python
tools=[
    {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read and return the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read"
                    }
                },
                "required": ["file_path"]
            }
        }
    }
]
```

This JSON Schema is sent verbatim to the API alongside the user's message. The model now knows a `Read` function exists, what it does, and exactly what argument it needs (`file_path`).

### What the model does with it

The model doesn't execute `Read` itself — it can't. Instead, when it decides a file read is needed, it returns a `tool_calls` response instead of plain text. The `finished_reason` on the choice changes from `"stop"` to `"tool_calls"`, and the response body contains the function name and the JSON-encoded arguments the model chose. Stage 3 will handle actually executing that call and feeding the result back.

### Key concept: separation of declaration and execution

| Layer | Responsibility |
|---|---|
| JSON Schema (`tools` array) | Tells the model *what* it can call and *what arguments* to supply |
| Model | Decides *when* and *why* to call a tool, returns a structured `tool_calls` object |
| Python code (next stage) | Receives the call, executes the real action, returns the result |

This three-layer split is the core pattern behind every AI agent framework.
