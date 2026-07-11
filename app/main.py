import argparse
import os
import sys
import json

from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-p", required=True)
    args = p.parse_args()

    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    chat = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        messages=[{"role": "user", "content": args.p}],
        # AQ1 Advertising the tool : Claude code provides several tools that can be used by the model to read and/or modify the user's codebase.
        # Here it is the read tool that can read the content of a file. The model can use this tool to read the content of a file and then use it in its context.
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
    )

    if not chat.choices or len(chat.choices) == 0:
        raise RuntimeError("no choices in response")
    
    if chat.choices[0].message.tool_calls: 
        tool_calls_id                = chat.choices[0].message.tool_calls[0].id
        tool_calls_type              = chat.choices[0].message.tool_calls[0].type
        tool_calls_function_name     = chat.choices[0].message.tool_calls[0].function.name
        tool_calls_function_arguments = chat.choices[0].message.tool_calls[0].function.arguments

        path_to_file = json.loads(tool_calls_function_arguments)["file_path"]

        with open(path_to_file, "r") as f:
            file_content = f.read()
            print(file_content)

    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!", file=sys.stderr)

    # TODO: Uncomment the following line to pass the first stage
    print(chat.choices[0].message.content)


if __name__ == "__main__":
    main()
