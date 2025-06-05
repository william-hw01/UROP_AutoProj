import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime
import subprocess
import re

# Load environment variables from /app (where files are copied during build)
load_dotenv("/app/environment.env")
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
        # Save response to a JSON file in /tmp (ephemeral)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # e.g., 20250605_1620
        filename = f"response_{timestamp}.json"
        json_path = os.path.join("/tmp", filename)
        with open(json_path, "w") as f:
            json.dump(response_data, f, indent=4)
        
        content = response_data["choices"][0]["message"]["content"]
        print("API Response Content:\n", content)  # Debug: Print the full response

        # Extract and execute PowerShell command if present
        powershell_command = extract_powershell_command(content)
        if powershell_command:
            try:
                # Adjust PowerShell command to create directories in /tmp
                original_command = powershell_command
                if "New-Item" in powershell_command or "mkdir" in powershell_command:
                    # Replace TestFolder with /tmp/TestFolder
                    if "New-Item" in powershell_command:
                        powershell_command = powershell_command.replace("TestFolder", "/tmp/TestFolder")
                    elif "mkdir" in powershell_command:
                        powershell_command = powershell_command.replace("TestFolder", "/tmp/TestFolder")
                print(f"Original PowerShell Command: {original_command}")
                print(f"Modified PowerShell Command: {powershell_command}")

                # Execute the command and capture output
                result = subprocess.run(
                    ["pwsh", "-Command", powershell_command],
                    check=True,
                    text=True,
                    capture_output=True
                )
                print("PowerShell command executed successfully!")
                if result.stdout:
                    print(f"PowerShell stdout: {result.stdout}")
                if result.stderr:
                    print(f"PowerShell stderr: {result.stderr}")

                # Verify directory creation
                if os.path.exists("/tmp/TestFolder"):
                    print("TestFolder created successfully at /tmp/TestFolder")
                    print("Contents of TestFolder:", os.listdir("/tmp/TestFolder"))
                else:
                    print("TestFolder was not created at /tmp/TestFolder")
            except subprocess.CalledProcessError as e:
                print(f"Error executing PowerShell command: {e}")
                print(f"PowerShell stdout: {e.stdout}")
                print(f"PowerShell stderr: {e.stderr}")
        else:
            print("No PowerShell command extracted from the response.")
        return content
    except requests.exceptions.HTTPError as e:
        error_msg = e.response.text if e.response.text else "No detailed error message available"
        try:
            error_data = e.response.json()
            error_msg = error_data.get("message", error_msg)
        except ValueError:
            pass
        return f"API Error (HTTP {e.response.status_code}): {error_msg}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

def extract_powershell_command(text):
    # Look for code blocks and extract PowerShell commands
    commands = []
    in_code_block = False
    current_language = None
    lines = text.split('\n')

    for line in lines:
        line = line.strip()
        if line.startswith('```'):
            if in_code_block:
                in_code_block = False
                current_language = None
            else:
                in_code_block = True
                current_language = line[3:].strip()
            continue
        if in_code_block and current_language in ['powershell', '']:
            if line and not line.startswith('#'):  # Ignore comments
                # Check for valid PowerShell syntax
                if (re.match(r'^\$[a-zA-Z]+\..*', line) or  # e.g., $host.UI.RawUI...
                    re.match(r'^Set-\w+\s+-', line) or    # e.g., Set-ItemProperty...
                    re.match(r'^[a-zA-Z]+\s+', line) or   # e.g., New-Item..., mkdir...
                    line.lower().startswith('mkdir')):    # e.g., mkdir TestFolder
                    if 'WallPaper' not in line or 'C:\\Path\\To\\Your\\Image.jpg' in line:
                        commands.append(line)
                elif re.match(r'^color\s+[0-9A-F]{2}', line.lower()):  # CMD color command
                    fg_color = line.split()[1][0].upper()
                    bg_color = line.split()[1][1].upper()
                    powershell_cmd = f"$host.UI.RawUI.BackgroundColor = '{color_map.get(bg_color, 'Gray')}'; Clear-Host"
                    commands.append(powershell_cmd)

    return commands[0] if commands else None

# Color map for CMD to PowerShell color conversion
color_map = {
    '0': 'Black', '1': 'DarkBlue', '2': 'DarkGreen', '3': 'DarkCyan',
    '4': 'DarkRed', '5': 'DarkMagenta', '6': 'DarkYellow', '7': 'Gray',
    '8': 'DarkGray', '9': 'Blue', 'A': 'Green', 'B': 'Cyan',
    'C': 'Red', 'D': 'Magenta', 'E': 'Yellow', 'F': 'White'
}

if __name__ == "__main__":
    print("DeepSeek Chat (type 'q' to exit)")
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == "q":
            break
        result = call_deepseek(user_input)
        print("\nDeepSeek:", result)