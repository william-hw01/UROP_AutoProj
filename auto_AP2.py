import requests
import subprocess
import os
import shutil
from pathlib import Path
from pprint import pprint
import re

class GitHubProgramRunner:
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://api.siliconflow.cn/v1/chat/completions"
        self.workspace = Path("workspace")
        self.workspace.mkdir(exist_ok=True)

    def fetch_readme(self, repo_url):
        """Fetch README with detailed error handling"""
        try:
            parts = repo_url.strip("/").split("/")
            owner, repo = parts[-2], parts[-1]
            
            readme_url = f"https://github.com/{owner}/{repo}/main/README.md"
            response = requests.get(readme_url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"⚠️ Failed to fetch README: {str(e)}")
            return None

    def call_ai(self, messages):
        """Call DeepSeek API with error handling"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "Qwen/QwQ-32B",
                "messages": messages,
                "temperature": 0.3,  # Lower for more deterministic technical responses
                "max_tokens": 2048
            }
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=180)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ AI API call failed: {str(e)}")
            return None

    def clone_repo(self, repo_url):
        """Clone repository with real-time output"""
        repo_dir = self.workspace / repo_url.split("/")[-1]
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
            
        print(f"\n🔧 Cloning repository to {repo_dir}...")
        try:
            result = subprocess.run(
                ["git", "clone", repo_url, str(repo_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            print("✅ Clone successful")
            return repo_dir
        except subprocess.CalledProcessError as e:
            print(f"❌ Clone failed:\n{e.stderr}")
            return None
        
    def extract_commands(self, ai_response):
        """Clean AI response into executable commands"""
        commands = []
        for line in ai_response.split('\n'):
            # Remove numbering (e.g., "1. ", "2. ") and whitespace
            cleaned = re.sub(r'^\d+\.\s*', '', line.strip())
            if cleaned and not cleaned.startswith(('#', '//')):  # Skip comments
                commands.append(cleaned)
        return commands

    def execute_commands(self, commands, cwd):
        """Execute commands with real-time monitoring"""
        results = []
        for cmd in commands:
            print(f"\n💻 Executing: {cmd}")           
            try:
                cmd = cmd.replace('\\', '/')
                for shell in ["pwsh", "powershell"]:
                    try:
                        # Try to execute with PowerShell Core first
                        process = subprocess.Popen(
                            [shell, "-Command", cmd],
                            cwd=cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            bufsize=1,
                            universal_newlines=True
                        )
                        break  # If successful, break out of the loop
                    except FileNotFoundError:
                        continue
                # Stream output in real-time
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        print(f"│ {output.strip()}")
                
                # Get remaining output if any
                stdout, stderr = process.communicate()
                returncode = process.returncode
                
                results.append({
                    "command": cmd,
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": returncode
                })
                
                print(f"🔚 Exit code: {returncode}")
                if stderr:
                    print(f"❌ Errors:\n{stderr}")
                
            except Exception as e:
                print(f"⚠️ Execution crashed: {str(e)}")
                results.append({
                    "command": cmd,
                    "error": str(e)
                })
        return results
    
    def find_python_file(self, repo_dir):
        """Find the main Python file in a repo"""
        python_dir = repo_dir / "Python"
        if python_dir.exists():
            for file in python_dir.glob("*.py"):
                if "hello" in file.name.lower() or "main" in file.name.lower():
                    return file
            return next(python_dir.glob("*.py"), None)
        return None
    
    def process_repository(self, repo_url, user_prompt, readme_url=None):
        """Full processing pipeline with visible output"""
        print(f"\n{'='*60}")
        print(f"🚀 Processing repository: {repo_url}")
        print(f"📌 User request: {user_prompt}")
        print(f"{'='*60}")
        
        # Step 1: Get README (with direct URL support)
        print("\n📄 STEP 1: Fetching README...")
        if readme_url:
            print(f"Using direct README URL: {readme_url}")
            try:
                response = requests.get(readme_url, timeout=10)
                response.raise_for_status()
                readme = response.text
                print(f"✅ README fetched directly ({len(readme)} bytes)")
            except Exception as e:
                print(f"⚠️ Failed to fetch direct README: {str(e)}")
                readme = None
        else:
            readme = self.fetch_readme(repo_url)
        
        if not readme:
            return {
                "status": "failed", 
                "error": "README not found",
                "repository": repo_url,
                "readme_url": readme_url or f"{repo_url}/blob/main/README.md"
            }
        
        # Rest of the processing remains the same...
        repo_dir = self.clone_repo(repo_url)
        if not repo_dir:
            return {
                "status": "failed", 
                "error": "Clone failed",
                "repository": repo_url,
                "readme_url": readme_url
            }
        
        # Step 3: Analyze with AI
        print("\n🧠 STEP 3: Analyzing with AI...")
        messages = [
            {
                "role": "system",
                "content": "You are a technical assistant that generates EXACT PowerShell commands to setup and run GitHub repositories. "
                           "Provide commands that can be executed directly without modification. "
                           "Include installation steps if needed."
            },
            {
                "role": "user",
                "content": f"Repository: {repo_url}\n\nREADME Content:\n{readme[:5000]}\n\n"
                           f"User Request: {user_prompt}\n\n"
                           f"Generate a numbered list of PowerShell commands to:\n"
                           f"1. Install dependencies if needed\n"
                           f"2. Run the program\n"
                           f"3. Execute test cases if mentioned\n"
                           f"Output ONLY the commands, one per line, without additional explanations."
            }
        ]
        
        ai_response = self.call_ai(messages)
        if not ai_response:
            return {"status": "failed", "error": "AI analysis failed"}
        
        print("\n🤖 AI RESPONSE:")
        ai_commands = ai_response['choices'][0]['message']['content']
        print(ai_commands)
        
        # Step 4: Execute commands
        print("\n⚡ STEP 4: Executing commands...")
        commands = [cmd.strip() for cmd in ai_commands.split("\n") if cmd.strip()]
        commands = self.extract_commands(ai_commands)
        execution_results = self.execute_commands(commands, repo_dir)
        
        return {
            "status": "completed",
            "repository": repo_url,
            "readme_url": readme_url or f"{repo_url}/blob/main/README.md",
            "commands": commands,
            "execution_results": execution_results,
            "workspace": str(repo_dir)
        }

# Example Usage
if __name__ == "__main__":
    API_KEY = "sk-ldlznymtwuosilumwyqsxkusuwllbzbvcmviebypcbqnxsso"
    runner = GitHubProgramRunner(API_KEY)
    
    # Test with a simple repository
    result = runner.process_repository(
        repo_url="https://github.com/leachim6/hello-world",
        user_prompt="Run the python 3.py in the repo",
        readme_url="https://github.com/leachim6/hello-world/blob/main/readme.md",
    )
    
    print("\n🏁 FINAL RESULTS:")
    pprint(result)