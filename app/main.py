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

    messages = [{"role": "user", "content": args.p}]

    loop = True

    while loop: 

        chat = client.chat.completions.create(
            model="anthropic/claude-haiku-4.5",
            messages=messages,
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
                }, 
                {
                    "type": "function",
                    "function": {
                        "name": "Write",
                        "description": "Write content to a file",
                        "parameters": {
                        "type": "object",
                        "required": ["file_path", "content"],
                        "properties": {
                            "file_path": {
                            "type": "string",
                            "description": "The path of the file to write to"
                            },
                            "content": {
                            "type": "string",
                            "description": "The content to write to the file"
                            }
                        }
                        }
                    }
                }
            ]
        )
        current_response_message = chat.choices[0].message
        #print(f"current response message {current_response_message}")    

        if not chat.choices or len(chat.choices) == 0:
            raise RuntimeError("no choices in response")

        messages.append(current_response_message.model_dump())
        print(current_response_message.tool_calls)
        if current_response_message.tool_calls: 
            for tool_call in current_response_message.tool_calls:

                
                tool_calls_id                = tool_call.id
                tool_calls_type              = tool_call.type
                tool_calls_function_name     = tool_call.function.name
                tool_calls_function_arguments = tool_call.function.arguments
                
                # Read tool execution
                if tool_calls_function_name == "Read":
                    print("----- in the read tool -------")
                    path_to_file = json.loads(tool_calls_function_arguments)["file_path"]

                    with open(path_to_file, "r") as f:
                        file_content = f.read()
                        messages.append({"role": "tool", "tool_call_id": tool_calls_id, "content": file_content})

                # Write tool execution
                if tool_calls_function_name == "Write":
                    print("----- in the write tool -------")
                    path_to_file = json.loads(tool_calls_function_arguments)["file_path"]
                    content = json.loads(tool_calls_function_arguments)["content"]
                    with open(path_to_file, "w", encoding="utf-8") as file:
                        file.write(content)
                        messages.append({"role": "tool", "tool_call_id": tool_calls_id, "content": file_content})


                
        

        # End loop when no more tool is called
        if not chat.choices[0].message.tool_calls: 
            #print("------- in exit loop -----------")
            loop = False
            print(chat.choices[0].message.content)

    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!", file=sys.stderr)

    # TODO: Uncomment the following line to pass the first stage



if __name__ == "__main__":
    main()
