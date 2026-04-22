
import sys
import os
import json
import asyncio
from datetime import datetime

# Add the API directory to path
sys.path.append(os.path.join(os.getcwd(), "saathi-api"))

try:
    from agent_tools import get_tool_definitions, execute_tool
    from storage import storage
    print("Core Modules Imported Successfully")
except ImportError as e:
    print(f"Import Failed: {e}")
    sys.exit(1)

async def run_test_suite():
    results = []
    
    # 1. Test: Tool Definitions
    try:
        tools_container = get_tool_definitions()
        tools = tools_container[0]["function_declarations"]
        if len(tools) > 10:
            results.append({"name": "Tool Discovery", "status": "PASS", "output": f"Found {len(tools)} registered agent tools."})
        else:
            results.append({"name": "Tool Discovery", "status": "FAIL", "output": f"Found only {len(tools)} tools. Some are missing."})
    except Exception as e:
        results.append({"name": "Tool Discovery", "status": "FAIL", "output": str(e)})

    # 2. Test: Memory Storage
    try:
        test_id = "smoke_test_user"
        storage.add_memory(test_id, "Saathi is running a high-fidelity smoke test.")
        mem = storage.list_memory(test_id)
        if any("smoke test" in m['text'] for m in mem):
            results.append({"name": "Memory Engine", "status": "PASS", "output": "Successfully anchored and retrieved neural snippets."})
        else:
            results.append({"name": "Memory Engine", "status": "FAIL", "output": "Snippet retrieval failed."})
    except Exception as e:
        results.append({"name": "Memory Engine", "status": "FAIL", "output": str(e)})

    # 3. Test: Mock Tool Execution (Launch App)
    try:
        # Test with 'launch_app' and 'vs code'
        res = await execute_tool("launch_app", {"app_name": "vs code"}, access_token="mock_token")
        if "Triggering" in res or "error" not in res.lower():
            results.append({"name": "App Launcher (VS Code)", "status": "PASS", "output": str(res)})
        else:
            results.append({"name": "App Launcher (VS Code)", "status": "FAIL", "output": str(res)})
    except Exception as e:
        results.append({"name": "App Launcher (VS Code)", "status": "FAIL", "output": str(e)})

    # 4. Test: Workspace Tool Integrity
    workspace_tools = ["send_email", "list_calendar_events", "create_doc"]
    tool_names = [t["name"] for t in tools]
    missing = [t for t in workspace_tools if t not in tool_names]
    if not missing:
        results.append({"name": "Workspace Tool Mapping", "status": "PASS", "output": "All Google Workspace cognitive endpoints are mapped."})
    else:
        results.append({"name": "Workspace Tool Mapping", "status": "FAIL", "output": f"Missing: {', '.join(missing)}"})

    return results

if __name__ == "__main__":
    print("Starting Saathi Neural Smoke Test (v37.1)...")
    suite_results = asyncio.run(run_test_suite())
    print("\n--- RESULTS ---")
    print(json.dumps(suite_results, indent=2))
    
    with open("smoke_report.json", "w") as f:
        json.dump(suite_results, f)
