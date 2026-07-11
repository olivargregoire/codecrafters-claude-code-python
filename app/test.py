import argparse
import os
import sys
import json

json2 = {
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "test",
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "Read",
              "arguments": "{\"file_path\": \"/path/to/file.txt\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}

print(json2["choices"][0]["index"])
