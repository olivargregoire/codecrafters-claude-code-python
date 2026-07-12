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

---

## Stage 3 — Detecting and Executing Tool Calls

### Where this sits in Claude Code

Stage 2 taught the model *what tools exist*. Stage 3 is where the model's intent becomes real action. This is the first moment the agent actually touches the filesystem — the bridge between "the model wants to read a file" and "the file gets read."

In the real Claude Code, every response is inspected for tool calls before any text is shown to the user. If tools are requested, they are executed and their results are fed back into the conversation. Stage 3 implements the first half of that: detect and execute.

### What was done

Two conditional branches were added after the API call ([app/main.py:51-69](app/main.py#L51-L69)):

```python
if chat.choices[0].message.tool_calls:
    tool_calls_function_arguments = chat.choices[0].message.tool_calls[0].function.arguments
    path_to_file = json.loads(tool_calls_function_arguments)["file_path"]

    with open(path_to_file, "r") as f:
        file_content = f.read()
        print(file_content)

if not chat.choices[0].message.tool_calls:
    print(chat.choices[0].message.content)
```

The logic is:
1. **Check for tool calls** — inspect `message.tool_calls`; if present, the model wants to act, not just reply.
2. **Extract and parse the arguments** — `function.arguments` is a raw JSON string, so `json.loads()` turns it into a dict to get `file_path`.
3. **Execute the Read** — open the file and print its raw contents to stdout.
4. **Fall through to text** — only print `message.content` when there are no tool calls (the two cases are mutually exclusive in the API).

### Key detail: arguments are a JSON string, not a dict

The API returns `function.arguments` as a serialized JSON string (e.g. `'{"file_path": "/app/main.py"}'`), not a Python dict. The `json.loads()` call is mandatory — skipping it would try to subscript a string and crash.

### What's still missing

The tool result is printed but never sent back to the model. The conversation ends after one tool call. The next stages introduce the **agent loop**: the file contents get added to the message history as a `tool` role message, and the model is called again so it can reason over the result and decide what to do next.
