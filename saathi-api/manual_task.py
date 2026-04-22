import system_agent
fp = system_agent.write_code_to_file('factorials.py', 'def factorial(n):\n    if n == 0: return 1\n    return n * factorial(n-1)\n\nprint(f"Factorial of 5 is {factorial(5)}")')
print(system_agent.launch_app_with_file('vs code', fp))
