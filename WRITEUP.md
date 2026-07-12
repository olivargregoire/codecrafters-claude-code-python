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

---

## Stage 4 — The Agent Loop

### Where this sits in Claude Code

This is the heart of any AI agent. Everything before this stage was a single-shot interaction: one prompt, one response, done. The agent loop is what makes Claude Code *agentic* — the model can now chain multiple tool calls together, reasoning step by step until it has enough information to answer.

In the real Claude Code, this loop runs continuously: the model reads files, runs commands, writes edits, re-reads to verify, and only stops when it decides the task is complete. Stage 4 implements that exact pattern.

### What was done

Three structural changes were made to [app/main.py](app/main.py):

**1. Persistent message history** — `messages` is initialized once before the loop and accumulates every turn:

```python
messages = [{"role": "user", "content": args.p}]
```

**2. The `while` loop** — the API call moves inside a `while loop:` block. Each iteration sends the full conversation history, not just the latest message:

```python
while loop:
    chat = client.chat.completions.create(model=..., messages=messages, tools=[...])
```

**3. Appending every message** — after each API call, the assistant's response is appended to `messages`. When a tool call happens, its result is appended too, as a `"tool"` role message referencing the call's id:

```python
messages.append(current_response_message.model_dump())

# if tool call:
messages.append({
    "role": "tool",
    "tool_call_id": current_response_message.tool_calls[0].id,
    "content": file_content
})
```

The loop exits only when the model returns a response with no `tool_calls`, meaning it has finished reasoning and is ready to give a final answer.

### Why the message history must grow

The LLM is stateless — it has no memory between API calls. The only way it can reason across multiple steps is if every prior message (user prompt, assistant thoughts, tool calls, tool results) is re-sent on each iteration. This is why `messages` is built up and passed in full every time.

### The full conversation shape after two turns

```
[
  { "role": "user",      "content": "Summarize README.md" },
  { "role": "assistant", "tool_calls": [{ "id": "call_1", "function": { "name": "Read", "arguments": "{\"file_path\": \"README.md\"}" } }] },
  { "role": "tool",      "tool_call_id": "call_1", "content": "# My Project\n..." },
  { "role": "assistant", "content": "The README describes..." }   ← loop exits here
]
```

Each role is mandatory: the API will reject a conversation where a `tool` message has no matching `assistant` message with the same `tool_call_id` immediately before it.

---

## Stage 5 — The Write Tool

### Where this sits in Claude Code

Read lets the model observe the filesystem; Write lets it act on it. Together they unlock the core coding workflow: read a file to understand it, then write a modified version back. This is exactly what Claude Code does when you ask it to refactor or fix a bug.

Stage 5 also introduces a pattern that scales to every subsequent tool: the `for tool_call in current_response_message.tool_calls` loop ([app/main.py:97-126](app/main.py#L97-L126)) dispatches by function name, so adding a new tool is just adding an `if` branch.

### What was done

**In the `tools` list** — the Write specification was added alongside Read ([app/main.py:51-68](app/main.py#L51-L68)). It declares two required parameters: `file_path` and `content`.

**In the dispatch loop** — a `Write` branch opens the file in write mode (`"w"`) and writes the model's content verbatim. If the file doesn't exist it is created; if it does it is overwritten:

```python
if tool_calls_function_name == "Write":
    path_to_file = json.loads(tool_calls_function_arguments)["file_path"]
    content      = json.loads(tool_calls_function_arguments)["content"]
    with open(path_to_file, "w", encoding="utf-8") as file:
        file.write(content)
    messages.append({"role": "tool", "tool_call_id": tool_calls_id, "content": "..."})
```

The tool result appended to `messages` just needs to confirm the action completed — the model uses it to decide whether to proceed or retry.

### Bug to fix: `file_content` used in the Write result

The current Write branch appends `file_content` as the tool result ([app/main.py:124](app/main.py#L124)), but `file_content` is a variable set inside the Read branch. If Write is called without a preceding Read in the same iteration, this is either a stale value or a `NameError`. The fix is to use a dedicated confirmation string:

```python
# instead of: "content": file_content
"content": f"Successfully wrote to {path_to_file}"
```
