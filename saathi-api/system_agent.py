import subprocess
import os
import psutil
import pyperclip
import pygetwindow as gw
import pyttsx3
import re

engine = pyttsx3.init()
engine.setProperty('rate', 150)

def speak_local(text):
    engine.say(text)
    engine.runAndWait()

def launch_app_with_file(app_name: str, file_path: str = None):
    app_map = {
        "vs code": "code",
        "vscode": "code",
        "visual studio code": "code",
        "notepad": "notepad",
        "browser": "start chrome",
        "chrome": "start chrome",
        "explorer": "explorer"
    }
    cmd = app_map.get(app_name.lower())
    if cmd:
        if file_path:
            # e.g., 'code C:/path/to/file.py'
            subprocess.Popen(f'{cmd} "{file_path}"', shell=True)
            return f"Launched {app_name} with file {file_path}"
        subprocess.Popen(cmd, shell=True)
        return f"Launched {app_name}"
    return f"Could not find shortcut for {app_name}"

def get_active_window_context():
    try:
        window = gw.getActiveWindow()
        if window:
            return window.title
    except Exception:
        pass
    return "Unknown Window"

def get_clipboard():
    try:
        return pyperclip.paste()
    except:
        return ""

def write_code_to_file(filename: str, code: str):
    # Ensure it saves to a safe temp or workspace directory
    # For now, put it in the Desktop/Saathi_Workspace
    workspace = os.path.expanduser("~/Desktop/Saathi_Workspace")
    os.makedirs(workspace, exist_ok=True)
    filepath = os.path.join(workspace, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    return filepath

def extract_code_from_prompt(prompt: str):
    # This just acts as a quick heuristic because generating perfect code inside agent requires LLM call.
    # To fix the "write a python program" without pinging LLM twice, we just pass the info.
    # Realistically, if we want Saathi to physically write code, the LLM should output a specific [WRITE_FILE] tag.
    pass

def agentic_execute(task_command: str, llm_response: str = None):
    """
    Module 11: Multi-step routing. 
    If llm_response is provided, we parse the LLM's output for commands.
    If not, we just parse the user's input directly for immediate actions.
    """
    task_lower = task_command.lower()
    results = []
    
    # 1. Parse LLM response for [ACTION: ...] tags
    if llm_response:
        # If the LLM decided to create a file
        import re
        # This robust regex ignores anything on the original ``` line (like 'markdown', 'python', etc.)
        code_blocks = re.findall(r'```[^\n]*\n(.*?)```', llm_response, re.DOTALL)
        if code_blocks and ("open vs code" in task_lower or "visual studio code" in task_lower):
            filepath = write_code_to_file("generated_code.py", code_blocks[0].strip())
            results.append(launch_app_with_file("vs code", filepath))
            return "\n".join(results)
    
    # 2. Parse User Command directly (fallback)
    if "visual studio code" in task_lower or "open vs code" in task_lower or "open vscode" in task_lower:
        results.append(launch_app_with_file("vs code"))
        
    if "what am i looking at" in task_lower or "what app" in task_lower:
        results.append(f"You are currently looking at: {get_active_window_context()}")
        
    if "read clipboard" in task_lower:
        results.append(f"Clipboard contains: {get_clipboard()}")
        
    if not results:
        results.append("Task logged for autonomous completion, but no immediate desktop tools were invoked.")
        
    return "\n".join(results)
