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
            subprocess.Popen(f'{cmd} "{file_path}"', shell=True)
            return f"Launched {app_name} with file {file_path}"
        subprocess.Popen(cmd, shell=True)
        return f"Launched {app_name}"
    return f"Could not find shortcut for {app_name}"

def get_active_window_context():
    try:
        window = gw.getActiveWindow()
        if window: return window.title
    except: pass
    return "Unknown Window"

def get_clipboard():
    try: return pyperclip.paste()
    except: return ""

def write_code_to_file(filename: str, code: str):
    workspace = os.path.expanduser("~/Desktop/Saathi_Workspace")
    os.makedirs(workspace, exist_ok=True)
    filepath = os.path.join(workspace, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    return filepath

def execute_python_code(file_path: str):
    """Executes the generated code natively and captures the output."""
    try:
        result = subprocess.run(["python", file_path], capture_output=True, text=True, timeout=10)
        output = result.stdout
        if result.stderr:
            output += f"\n[Errors]:\n{result.stderr}"
        return f"\n\n**Output of Execution:**\n```text\n{output.strip()}\n```"
    except Exception as e:
        return f"\n\n**Execution Error:** {str(e)}"

def agentic_execute(task_command: str, llm_response: str = None, mode: str = "chat"):
    task_lower = task_command.lower()
    results = []
    
    # 1. Parse LLM response for code files
    if llm_response and mode == "agent":
        code_blocks = re.findall(r'```[^\n]*\n(.*?)```', llm_response, re.DOTALL)
        if code_blocks:
            filepath = write_code_to_file("generated_code.py", code_blocks[0].strip())
            
            if "open vs code" in task_lower or "visual studio code" in task_lower or "editor" in task_lower:
                results.append(launch_app_with_file("vs code", filepath))
                
            if "run" in task_lower or "execute" in task_lower or "output" in task_lower:
                exec_output = execute_python_code(filepath)
                results.append(exec_output)
                
            if results: return "\n".join(results)
    
    # 2. Parse User Command directly
    if mode == "agent":
        if "visual studio code" in task_lower or "open vs code" in task_lower or "open vscode" in task_lower:
            results.append(launch_app_with_file("vs code"))
        if "what am i looking at" in task_lower or "what app" in task_lower:
            results.append(f"You are currently looking at: {get_active_window_context()}")
        if "read clipboard" in task_lower:
            results.append(f"Clipboard contains: {get_clipboard()}")
    
        if not results:
            results.append("Task logged for autonomous completion, but no immediate desktop apps were invoked.")
        
    return "\n".join(results)
