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
        "max_tokens": 1024,  # Increased to allow for multiple commands
        "temperature": 0.7,
        "top_p": 0.7,
        "response_format": {"type": "text"},
    }

    max_attempts = 3
    powershell_commands = []
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
            
            powershell_commands = extract_powershell_commands(response_content)
            if powershell_commands:
                print(f"Found {len(powershell_commands)} PowerShell command(s).")
                execute_powershell_commands(powershell_commands)
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

def extract_powershell_commands(text):
    """
    Extract multiple PowerShell commands from text.
    Returns a list of commands in the order they should be executed.
    """
    commands = []
    
    # First try to extract complete code blocks
    code_block_pattern = r'```(?:powershell)?\n(.*?)\n```'
    code_blocks = re.findall(code_block_pattern, text, re.DOTALL)
    
    for block in code_blocks:
        # Split block into individual commands, handling line continuations
        block_commands = []
        current_command = []
        
        for line in block.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # Skip empty lines and comments
            
            # Handle line continuations (lines ending with backtick)
            if line.endswith('`'):
                current_command.append(line[:-1].strip())
            else:
                current_command.append(line)
                complete_command = ' '.join(current_command).strip()
                if complete_command:
                    block_commands.append(complete_command)
                current_command = []
        
        # Add any remaining command parts
        if current_command:
            complete_command = ' '.join(current_command).strip()
            if complete_command:
                block_commands.append(complete_command)
        
        commands.extend(block_commands)
    
    # Then look for inline commands (between single backticks or on their own line)
    inline_pattern = r'(?:`|^|\n)((?:[A-Za-z]+-[A-Za-z]+\b|mkdir|cd|cp|mv|rm|ls|cat|echo|foreach|if|while|switch|try|catch|finally|function|\$[A-Za-z0-9_]+\s*=?).*?)(?:`|$|\n)'
    inline_commands = re.findall(inline_pattern, text, re.IGNORECASE)
    
    # Filter and add inline commands
    for cmd in inline_commands:
        cmd = cmd.strip()
        if cmd and not cmd.startswith('#') and not cmd.startswith('//'):
            # Check if this is part of a multi-line command already captured
            if not any(cmd in existing for existing in commands):
                commands.append(cmd)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_commands = []
    for cmd in commands:
        normalized_cmd = ' '.join(cmd.split())  # Normalize whitespace
        if normalized_cmd not in seen:
            seen.add(normalized_cmd)
            unique_commands.append(cmd)
    
    return unique_commands

def execute_powershell_commands(commands):
    """Execute a list of PowerShell commands with safety checks and proper output handling."""
    if not commands:
        print("No valid commands to execute.")
        return False
    
    overall_success = True
    
    for i, command in enumerate(commands, 1):
        print(f"\nCommand {i}/{len(commands)}: {command}")
        
        try:
            # Basic safety check
            if is_potentially_dangerous(command):
                print(f"⚠️ Warning: Command {i} appears potentially dangerous and was skipped")
                overall_success = False
                continue
            
            # Execute the command
            result = subprocess.run(
                ["pwsh", "-Command", command],
                check=True,
                text=True,
                capture_output=True
            )
            
            # Print results
            if result.stdout:
                print(f"Output:\n{result.stdout}")
            if result.stderr:
                print(f"Errors:\n{result.stderr}")
            
            print(f"✅ Command {i} executed successfully")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Command {i} failed with error: {e}")
            print(f"Output: {e.stdout}")
            print(f"Errors: {e.stderr}")
            overall_success = False
            # Continue with next command even if one fails
        except Exception as e:
            print(f"❌ Unexpected error executing command {i}: {e}")
            overall_success = False
    
    return overall_success

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
        r'rm\s+-r',
        r'del\s+/s',
        r'Format-',
        r'Clear-',
    ]
    
    lower_command = command.lower()
    return any(re.search(pattern, lower_command, re.IGNORECASE) for pattern in dangerous_patterns)

if __name__ == "__main__":
    print("DeepSeek Chat PowerShell Assistant (type 'quit' or 'exit' to end)")
    print("Note: Multiple PowerShell commands will be executed in order.")
    
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