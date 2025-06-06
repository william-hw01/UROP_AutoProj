import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime
import subprocess
import re

# Load environment variables
load_dotenv("/app/environment.env")
API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-ldlznymtwuosilumwyqsxkusuwllbzbvcmviebypcbqnxsso")

if not API_KEY:
    raise ValueError("API key is not set. Please check your environment configuration.")

API_URL = "https://api.siliconflow.cn/v1/chat/completions"

def call_deepseek(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "Qwen/QwQ-32B",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": 512,
        "temperature": 0.7,
        "top_p": 0.7,
        "response_format": {"type": "text"},
    }

    max_attempts = 3
    powershell_command = None
    response_content = None

    for attempt in range(1, max_attempts + 1):
        print(f"\nAttempt {attempt} of {max_attempts}...")
        try:
            response = requests.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()
            response_content = response_data["choices"][0]["message"]["content"]
            
            # Save response for debugging
            save_response(response_data, attempt)
            
            powershell_command = extract_powershell_command(response_content)
            if powershell_command:
                print("PowerShell command extracted successfully.")
                execute_powershell_command(powershell_command)
                break
                
        except requests.exceptions.HTTPError as e:
            error_msg = get_error_message(e)
            return f"API Error: {error_msg}"
        except Exception as e:
            return f"Error: {str(e)}"

    return response_content if response_content else "No response received."

def save_response(response_data, attempt):
    """Save API response to a JSON file for debugging."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"response_{timestamp}_attempt_{attempt}.json"
    json_path = os.path.join("/app", filename)
    with open(json_path, "w") as f:
        json.dump(response_data, f, indent=4)

def get_error_message(http_error):
    """Extract error message from HTTP error response."""
    error_msg = http_error.response.text if http_error.response.text else "No detailed error message"
    try:
        error_data = http_error.response.json()
        return error_data.get("message", error_msg)
    except ValueError:
        return error_msg

def extract_powershell_command(text):
    """
    Extract PowerShell commands from text with more flexible pattern matching.
    Handles both code blocks and inline commands.
    """
    # Pattern for code blocks
    code_block_pattern = r'```(?:powershell)?\n(.*?)\n```'
    code_blocks = re.findall(code_block_pattern, text, re.DOTALL)
    
    # Pattern for inline commands (between backticks or on their own line)
    inline_pattern = r'(?:`|^)((?:New-Item|mkdir|Set-|Get-|Remove-|Start-|Stop-|Write-|Invoke-|Select-|Where-|\$)[^`\n]+)(?:`|$)'
    inline_commands = re.findall(inline_pattern, text, re.IGNORECASE)
    
    # Combine all potential commands
    all_commands = []
    for block in code_blocks:
        all_commands.extend([cmd.strip() for cmd in block.split('\n') if cmd.strip()])
    
    all_commands.extend(inline_commands)
    
    # Filter out comments and empty commands
    valid_commands = [
        cmd for cmd in all_commands 
        if cmd and not cmd.startswith('#') and not cmd.startswith('//')
    ]
    
    return valid_commands[0] if valid_commands else None

def execute_powershell_command(command):
    """Execute a PowerShell command with safety checks and proper output handling."""
    print(f"\nExecuting PowerShell command: {command}")
    
    try:
        # Basic safety check - don't execute potentially dangerous commands
        if is_potentially_dangerous(command):
            raise ValueError("Command appears potentially dangerous and was blocked")
        
        # Execute the command
        result = subprocess.run(
            ["pwsh", "-Command", command],
            check=True,
            text=True,
            capture_output=True
        )
        
        # Print results
        if result.stdout:
            print(f"Command output:\n{result.stdout}")
        if result.stderr:
            print(f"Command errors:\n{result.stderr}")
            
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")
        print(f"Output: {e.stdout}")
        print(f"Errors: {e.stderr}")
        return False
    except Exception as e:
        print(f"Error executing command: {e}")
        return False

def is_potentially_dangerous(command):
    """Check if a command appears to be potentially dangerous."""
    dangerous_patterns = [
        r'Remove-Item\s+[^-]',  # Remove-Item without -WhatIf or -Confirm
        r'Format-Volume',
        r'Stop-Process\s+-Id\s+\d+',
        r'Restart-Computer',
        r'Invoke-Expression',
        r'Invoke-Command',
        r'Start-Process\s+.*\.exe',
        r'Set-ExecutionPolicy',
        r'net\s+user',
        r'reg\s+(add|delete)',
        r'schtasks\s+',
    ]
    
    lower_command = command.lower()
    return any(re.search(pattern, lower_command, re.IGNORECASE) for pattern in dangerous_patterns)

if __name__ == "__main__":
    print("DeepSeek Chat PowerShell Assistant (type 'quit' or 'exit' to end)")
    while True:
        try:
            user_input = input("\nYour request: ").strip()
            if user_input.lower() in ('q', 'quit', 'exit'):
                break
            if not user_input:
                continue
                
            result = call_deepseek(user_input)
            print("\nAssistant:", result)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")