import subprocess
import os
import time
import psutil
import pyperclip
import pygetwindow as gw
import pyttsx3

# Initialize Local TTS (Module 12)
engine = pyttsx3.init()
rate = engine.getProperty('rate')
engine.setProperty('rate', 150) # Calmer, slightly slower voice

def speak_local(text):
    """Speaks text using local OS TTS engine."""
    engine.say(text)
    engine.runAndWait()

def launch_app(app_name: str):
    """Module 13 & 11: OS App Launching"""
    app_map = {
        "vs code": "code",
        "vscode": "code",
        "notepad": "notepad",
        "browser": "start chrome",
        "chrome": "start chrome",
        "explorer": "explorer"
    }
    cmd = app_map.get(app_name.lower())
    if cmd:
        # Use shell=True for windows built-in like 'start' or PATH mapped like 'code'
        subprocess.Popen(cmd, shell=True)
        return f"Launched {app_name}"
    return f"Could not find shortcut for {app_name}"

def get_active_window_context():
    """Module 13: App context detection"""
    try:
        window = gw.getActiveWindow()
        if window:
            return window.title
    except Exception:
        pass
    return "Unknown Window"

def get_clipboard():
    """Module 13: Clipboard monitoring"""
    try:
        return pyperclip.paste()
    except:
        return ""

def take_screenshot_ocr():
    """Module 13: OCR Screen Awareness (Mock without heavy Tesseract native install)"""
    # In a full production env, we'd do:
    # import pyautogui, pytesseract
    # img = pyautogui.screenshot()
    # text = pytesseract.image_to_string(img)
    return "[OCR Engine Active: Mock extraction applied. System recognizes VS Code with SAC Project open]"

def agentic_execute(task_command: str):
    """Module 11: Multi-step routing"""
    task_command = task_command.lower()
    results = []
    
    if "open vs code" in task_command or "open vscode" in task_command:
        results.append(launch_app("vs code"))
        
    if "what am i looking at" in task_command or "what app" in task_command:
        current_app = get_active_window_context()
        results.append(f"You are currently looking at: {current_app}")
        
    if "read clipboard" in task_command:
        clip = get_clipboard()
        results.append(f"Clipboard contains: {clip}")
        
    if "screenshot" in task_command or "scan screen" in task_command:
        results.append(take_screenshot_ocr())
        
    if not results:
        results.append("Task logged for autonomous completion, but no immediate desktop tools were invoked.")
        
    return "\n".join(results)
