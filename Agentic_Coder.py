import json
import requests
import subprocess
import time

class AgenticCoder:
    def __init__(self, openrouter_api_key, site_url="your-site-url", site_name="your-site-name", max_iterations=5):
        self.openrouter_api_key = openrouter_api_key
        self.site_url = site_url  # For OpenRouter rankings
        self.site_name = site_name  # For OpenRouter rankings
        self.max_iterations = max_iterations
        self.tools = {
            "run_code": self.run_code,
            "run_tests": self.run_tests
        }

    def query_llm(self, messages, model="openai/gpt-4o"):
        """Query OpenRouter API with a list of messages."""
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name
        }
        data = {
            "model": model,  # You can swap models here (e.g., anthropic/claude-3.5-sonnet)
            "messages": messages
        }
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                data=json.dumps(data)
            )
            response.raise_for_status()  # Raise exception for bad status codes
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error querying LLM: {str(e)}"


    def query_llm_rate_limited(self, messages, model="openai/gpt-4o", retries=3):
        for attempt in range(retries):
            try:
                response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                data=json.dumps(data)
            )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
             except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise
         return "Error: Max retries reached"



    def run_code(self, code):
        """Execute Python code and capture output."""
        try:
            with open("temp.py", "w") as f:
                f.write(code)
            result = subprocess.run(["python", "temp.py"], capture_output=True, text=True, timeout=10)
            return result.stdout, result.stderr
        except Exception as e:
            return "", f"Error running code: {str(e)}"

    def run_tests(self, code, test_code):
        """Run unit tests on the code using pytest."""
        try:
            with open("test_temp.py", "w") as f:
                f.write(test_code)
            result = subprocess.run(["pytest", "test_temp.py"], capture_output=True, text=True, timeout=10)
            return result.stdout, result.stderr
        except Exception as e:
            return "", f"Error running tests: {str(e)}"

    def plan(self, goal):
        """Generate a plan for the goal using OpenRouter."""
        messages = [
            {"role": "system", "content": "You are a skilled software engineer. Break down coding goals into tasks."},
            {"role": "user", "content": f"Break down the goal '{goal}' into a list of coding tasks in JSON format."}
        ]
        plan = self.query_llm(messages)
        try:
            return json.loads(plan)
        except json.JSONDecodeError:
            return {"tasks": [], "error": "Failed to parse plan as JSON"}

    def execute(self, task, context):
        """Execute a single task using OpenRouter and tools."""
        messages = [
            {"role": "system", "content": "You are a coding assistant. Write clean, functional Python code."},
            {"role": "user", "content": f"Context: {json.dumps(context)}\nWrite Python code for: {task}"}
        ]
        code = self.query_llm(messages)
        stdout, stderr = self.tools["run_code"](code)
        return code, stdout, stderr

    def reflect(self, code, stdout, stderr, task):
        """Reflect on the output and suggest improvements."""
        messages = [
            {"role": "system", "content": "You are a code reviewer. Suggest improvements for code based on output and errors."},
            {"role": "user", "content": f"Code: {code}\nOutput: {stdout}\nErrors: {stderr}\nTask: {task}\nSuggest improvements."}
        ]
        suggestions = self.query_llm(messages)
        return suggestions

    def run(self, goal):
        """Main agentic loop."""
        context = {"goal": goal, "history": []}
        plan = self.plan(goal)
        if "error" in plan:
            return {"error": plan["error"], "context": context}

        for iteration in range(self.max_iterations):
            for task in plan.get("tasks", []):
                code, stdout, stderr = self.execute(task, context)
                suggestions = self.reflect(code, stdout, stderr, task)
                context["history"].append({
                    "task": task,
                    "code": code,
                    "output": stdout,
                    "errors": stderr,
                    "suggestions": suggestions
                })
                if stderr:  # Errors detected, refine code
                    messages = [
                        {"role": "system", "content": "You are a coding assistant. Refine code based on suggestions."},
                        {"role": "user", "content": f"Refine this code based on suggestions: {suggestions}\nOriginal code: {code}"}
                    ]
                    refined_code = self.query_llm(messages)
                    stdout, stderr = self.tools["run_code"](refined_code)
                    context["history"].append({
                        "task": task,
                        "refined_code": refined_code,
                        "output": stdout,
                        "errors": stderr
                    })
                if not stderr:  # No errors, move to next task
                    continue
            # Check if all tasks are error-free
            if all(not entry.get("errors") for entry in context["history"] if "errors" in entry):
                break
        return context

# Example usage
agent = AgenticCoder(
    openrouter_api_key="your-openrouter-api-key",
    site_url="https://your-site.com",
    site_name="Your Agentic Coder"
)
result = agent.run("Create a Python function to calculate Fibonacci numbers")
print(json.dumps(result, indent=2))