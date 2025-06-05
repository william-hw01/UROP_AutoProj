import requests
import os
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()
API_KEY = "sk-ldlznymtwuosilumwyqsxkusuwllbzbvcmviebypcbqnxsso"

# Check if API key is loaded
if not API_KEY:
    raise ValueError("DEEPSEEK_API_KEY is not set in the environment. Please check environment.env.")

API_URL = "https://api.siliconflow.cn/v1/chat/completions"

def call_deepseek(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "Qwen/QwQ-32B",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "max_tokens": 512,
        "thinking_budget": 4096,
        "min_p": 0.05,
        "stop": None,
        "temperature": 0.7,
        "top_p": 0.7,
        "top_k": 50,
        "frequency_penalty": 0.5,
        "n": 1,
        "response_format": {"type": "text"},
        "tools": [
            {
                "type": "function",
                "function": {
                    "description": "<string>",
                    "name": "<string>",
                    "parameters": {},
                    "strict": False
                }
            }
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        # Save response to a JSON file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"response_{timestamp}.json"
        with open(os.path.join("/workspace", filename), "w") as f:
            json.dump(response_data, f, indent=4)
        return response_data["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        error_msg = e.response.text if e.response.text else "No detailed error message available"
        try:
            error_data = e.response.json()
            error_msg = error_data.get("message", error_msg)
        except ValueError:
            pass  # Use the raw text if JSON parsing fails
        return f"API Error (HTTP {e.response.status_code}): {error_msg}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

if __name__ == "__main__":
    print("DeepSeek Chat (type 'q' to exit)")
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == "q":
            break
        result = call_deepseek(user_input)
        print("\nDeepSeek:", result)