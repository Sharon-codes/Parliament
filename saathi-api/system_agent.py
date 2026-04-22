import os
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import docx
import httpx
import PyPDF2
import pygetwindow as gw
import pyperclip
import pyttsx3

engine = pyttsx3.init()
engine.setProperty("rate", 150)

APP_MAPPINGS: dict[str, tuple[list[str] | str, str]] = {
    "vs code": (["code"], "Visual Studio Code"),
    "vscode": (["code"], "Visual Studio Code"),
    "visual studio code": (["code"], "Visual Studio Code"),
    "cursor": (["cursor"], "Cursor"),
    "chrome": (["chrome"], "Google Chrome"),
    "google chrome": (["chrome"], "Google Chrome"),
    "edge": (["msedge"], "Microsoft Edge"),
    "firefox": (["firefox"], "Mozilla Firefox"),
    "explorer": (["explorer"], "File Explorer"),
    "file explorer": (["explorer"], "File Explorer"),
    "terminal": (["wt"], "Windows Terminal"),
    "windows terminal": (["wt"], "Windows Terminal"),
    "powershell": (["powershell"], "PowerShell"),
    "command prompt": (["cmd"], "Command Prompt"),
    "cmd": (["cmd"], "Command Prompt"),
    "notepad": (["notepad"], "Notepad"),
    "notepad++": (["notepad++"], "Notepad++"),
    "word": (["winword"], "Microsoft Word"),
    "microsoft word": (["winword"], "Microsoft Word"),
    "excel": (["excel"], "Microsoft Excel"),
    "microsoft excel": (["excel"], "Microsoft Excel"),
    "powerpoint": (["powerpnt"], "Microsoft PowerPoint"),
    "microsoft powerpoint": (["powerpnt"], "Microsoft PowerPoint"),
    "outlook": (["outlook"], "Microsoft Outlook"),
    "teams": (["ms-teams"], "Microsoft Teams"),
    "spotify": (["spotify"], "Spotify"),
    "slack": (["slack"], "Slack"),
    "discord": (["discord"], "Discord"),
    "calculator": (["calc"], "Calculator"),
    "paint": (["mspaint"], "Paint"),
    "pycharm": (["pycharm64"], "PyCharm"),
}


def workspace_root() -> str:
    configured = os.getenv("SAATHI_WORKSPACE", "").strip()
    return os.path.expanduser(configured or "~/Desktop/Saathi_Workspace")


def open_web_url(url: str) -> str:
    try:
        webbrowser.open(url)
        return f"Opened {url} in your default browser."
    except Exception as exc:
        return f"Error opening URL: {exc}"


def open_url(url: str) -> str:
    return open_web_url(url)


def _start_process(command: list[str] | str) -> bool:
    try:
        if isinstance(command, list):
            subprocess.Popen(command)
        else:
            subprocess.Popen(command, shell=True)
        return True
    except Exception:
        return False


def _resolve_known_app(app_name: str) -> tuple[list[str] | str | None, str | None]:
    app_key = (app_name or "").strip().lower()
    return APP_MAPPINGS.get(app_key, (None, None))


def parse_desktop_command(command: str) -> tuple[str, str]:
    cleaned = (command or "").strip()
    cleaned = re.sub(r"^(?:saathi,\s*)?", "", cleaned, flags=re.IGNORECASE)

    for _ in range(2):
        cleaned = re.sub(r"^(?:open|launch|start)\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^(?:my\s+workstation\s*:?\s*)", "", cleaned, flags=re.IGNORECASE)

    normalized = re.sub(r"\s+", " ", cleaned).strip(" :-")
    lower = normalized.lower()

    for alias in sorted(APP_MAPPINGS.keys(), key=len, reverse=True):
        if lower.startswith(alias):
            remainder = normalized[len(alias):].strip(" :-,")
            remainder = re.sub(r"^(?:and|to)\s+", "", remainder, flags=re.IGNORECASE)
            return alias, remainder

    return normalized, ""


def launch_app_with_file(app_name: str, file_path: str | None = None) -> str:
    command, label = _resolve_known_app(app_name)

    if file_path:
        target = str(Path(file_path))
        if command:
            if isinstance(command, list) and _start_process(command + [target]):
                return f"Launched {label or app_name} with {target}."
            if isinstance(command, str) and _start_process(f'{command} "{target}"'):
                return f"Launched {label or app_name} with {target}."
        if os.name == "nt":
            try:
                os.startfile(target)  # type: ignore[attr-defined]
                return f"Opened {target}."
            except Exception:
                pass

    if command:
        if _start_process(command):
            return f"Launched {label or app_name}."

    executable = shutil.which(app_name)
    if executable and _start_process([executable]):
        return f"Launched {app_name}."

    if os.name == "nt":
        powershell_cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f'Start-Process -FilePath "{app_name}"',
        ]
        if _start_process(powershell_cmd):
            return f"Launched {app_name}."

    return f"Could not find an installed app matching '{app_name}'."


def play_youtube_video(query: str) -> str:
    normalized = (query or "").strip()
    if not normalized:
        return open_web_url("https://www.youtube.com")
    if "youtube.com/watch" in normalized or "youtu.be/" in normalized:
        return open_web_url(normalized)

    search_url = f"https://www.youtube.com/results?search_query={quote_plus(normalized)}"
    try:
        response = httpx.get(search_url, timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        video_match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', response.text)
        if video_match:
            return open_web_url(f"https://www.youtube.com/watch?v={video_match.group(1)}")
    except Exception:
        pass

    webbrowser.open(search_url)
    return f"Opened YouTube search results for '{normalized}'."


def speak_local(text: str):
    engine.say(text)
    engine.runAndWait()


def get_active_window_context() -> str:
    try:
        window = gw.getActiveWindow()
        if window:
            return window.title
    except Exception:
        pass
    return "Unknown Window"


def get_clipboard() -> str:
    try:
        return pyperclip.paste()
    except Exception:
        return ""


def write_code_to_file(filename: str, code: str) -> str:
    workspace = workspace_root()
    os.makedirs(workspace, exist_ok=True)
    filepath = os.path.join(workspace, filename)
    with open(filepath, "w", encoding="utf-8") as handle:
        handle.write(code)
    return filepath


def extract_text_from_any(file_path: str) -> str:
    ext = file_path.split(".")[-1].lower()
    content = ""
    try:
        if ext == "pdf":
            with open(file_path, "rb") as handle:
                reader = PyPDF2.PdfReader(handle)
                content = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif ext == "docx":
            document = docx.Document(file_path)
            content = "\n".join([paragraph.text for paragraph in document.paragraphs])
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read()
    except Exception as exc:
        return f"Extraction Error: {exc}"
    return content


def execute_python_code(file_path: str) -> str:
    try:
        result = subprocess.run(["python", file_path], capture_output=True, text=True, timeout=20)
        output = result.stdout
        if result.stderr:
            output += f"\n[Errors]\n{result.stderr}"
        return f"\n\nOutput of Execution:\n```text\n{output.strip()}\n```"
    except Exception as exc:
        return f"\n\nExecution Error: {exc}"


def run_background_task(file_path: str) -> dict[str, str | int]:
    log_file = file_path + ".log"
    try:
        with open(log_file, "a", encoding="utf-8") as handle:
            process = subprocess.Popen(
                ["python", "-u", file_path],
                stdout=handle,
                stderr=handle,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        return {"pid": process.pid, "log_file": log_file}
    except Exception as exc:
        return {"error": str(exc)}


def read_task_logs(filename: str) -> str:
    workspace = workspace_root()
    possible_paths = [os.path.join(workspace, filename + ".log"), os.path.join(workspace, filename + ".py.log")]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    lines = handle.readlines()
                return "".join(lines[-25:])
            except Exception:
                pass
    return "Log file not found. Task might not have started yet."


def agentic_execute(task_command: str, llm_response: str | None = None, mode: str = "chat") -> str:
    task_lower = task_command.lower()
    results: list[str] = []

    if llm_response and mode == "agent":
        import re

    if llm_response and mode == "agent":
        import re
        # 🦾 SOVEREIGN PARSER (v123.0): Robust Tag-Based Extraction with Cutoff Recovery
        match = re.search(r"\[SOURCE_START\]([\s\S]+?)\[SOURCE_END\]", llm_response)
        if not match:
            # Cutoff recovery
            match = re.search(r"\[SOURCE_START\]([\s\S]+)$", llm_response)
        if not match:
            # Legacy fallback
            match = re.search(r"```[^\n]*\n(.*?)```", llm_response, re.DOTALL)
            
        if match:
            code = match.group(1).strip()
            # Clean up markdown fences
            code = re.sub(r"^```[\w]*\n|```$", "", code, flags=re.MULTILINE).strip()
            if "[SOURCE_END]" not in llm_response and "[SOURCE_START]" in llm_response:
                 code += "\n\n# [AI NOTICE]: Partial stream recovery."
                 
            filepath = write_code_to_file("generated_code.py", code)
            
            if "open vs code" in task_lower or "visual studio code" in task_lower or "editor" in task_lower:
                results.append(launch_app_with_file("vs code", filepath))
            if "run" in task_lower or "execute" in task_lower or "output" in task_lower:
                results.append(execute_python_code(filepath))
            if results:
                return "\n".join(results)

    if mode == "agent":
        app_names = [
            "vs code",
            "cursor",
            "pycharm",
            "notepad++",
            "chrome",
            "notepad",
            "excel",
            "word",
            "spotify",
            "slack",
        ]
        for name in app_names:
            if f"open {name}" in task_lower or f"launch {name}" in task_lower or f"start {name}" in task_lower:
                results.append(launch_app_with_file(name))
                break

        if not results:
            if "what am i looking at" in task_lower or "what app" in task_lower:
                results.append(f"You are currently looking at: {get_active_window_context()}")
            if "read clipboard" in task_lower:
                results.append(f"Clipboard contains: {get_clipboard()}")

        if not results:
            results.append("Task logged for autonomous completion, but no immediate desktop apps were invoked.")

    return "\n".join(results)
