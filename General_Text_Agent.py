import json
import requests
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
import os

class AgenticSystem:
    def __init__(self):
        self.api_key = None
        self.site_url = "https://your-site.com"  # Replace with your site for OpenRouter rankings
        self.site_name = "General Agent"  # Replace with your app name
        self.log_file = f"agent_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        self.setup_gui()

    def query_llm(self, messages, model="openai/gpt-4o", temperature=0.7):
        """Query OpenRouter API with a list of messages."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name
        }
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                data=json.dumps(data)
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error querying LLM: {str(e)}"

    def log_to_file(self, content):
        """Append content to the timestamped log file."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:\n{content}\n\n")

    def plan(self, goal, system_prompt):
        """Generate a plan for the goal."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Break down the goal '{goal}' into a list of tasks in JSON format."}
        ]
        plan = self.query_llm(messages, self.model.get(), float(self.temperature.get()))
        self.log_to_file(f"Plan for goal '{goal}':\n{plan}")
        try:
            return json.loads(plan)
        except json.JSONDecodeError:
            error_msg = "Failed to parse plan as JSON"
            self.log_to_file(error_msg)
            return {"tasks": [], "error": error_msg}

    def execute(self, task, context, system_prompt):
        """Execute a single task."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context: {json.dumps(context)}\nPerform task: {task}"}
        ]
        output = self.query_llm(messages, self.model.get(), float(self.temperature.get()))
        self.log_to_file(f"Task: {task}\nOutput: {output}")
        return output

    def reflect(self, task, output, system_prompt):
        """Reflect on the task output and suggest improvements."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task}\nOutput: {output}\nSuggest improvements or confirm correctness."}
        ]
        suggestions = self.query_llm(messages, self.model.get(), float(self.temperature.get()))
        self.log_to_file(f"Reflection on task '{task}':\nSuggestions: {suggestions}")
        return suggestions

    def run_agent(self):
        """Main agentic loop."""
        goal = self.goal_text.get("1.0", tk.END).strip()
        system_prompt = self.prompt_text.get("1.0", tk.END).strip()
        max_iterations = int(self.max_iterations.get())
        self.api_key = self.api_key_entry.get()

        if not self.api_key:
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, "Error: Please enter an OpenRouter API key.")
            return

        context = {"goal": goal, "history": []}
        self.log_to_file(f"Starting agent for goal: {goal}")
        plan = self.plan(goal, system_prompt)
        if "error" in plan:
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, plan["error"])
            return

        for iteration in range(max_iterations):
            self.log_to_file(f"Iteration {iteration + 1}")
            for task in plan.get("tasks", []):
                output = self.execute(task, context, system_prompt)
                suggestions = self.reflect(task, output, system_prompt)
                context["history"].append({
                    "task": task,
                    "output": output,
                    "suggestions": suggestions
                })
                # Check if suggestions indicate the output is correct
                if "correct" in suggestions.lower() or "no improvements needed" in suggestions.lower():
                    continue
                # Refine output if needed
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Refine this output based on suggestions: {suggestions}\nOriginal output: {output}"}
                ]
                refined_output = self.query_llm(messages, self.model.get(), float(self.temperature.get()))
                self.log_to_file(f"Refined output for task '{task}':\n{refined_output}")
                context["history"].append({
                    "task": task,
                    "refined_output": refined_output
                })
            # Stop early if all tasks are deemed correct
            if all("correct" in entry["suggestions"].lower() or "no improvements needed" in entry["suggestions"].lower()
                   for entry in context["history"] if "suggestions" in entry):
                break

        # Display results in GUI
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, json.dumps(context, indent=2))
        self.log_to_file(f"Agent completed. Final context:\n{json.dumps(context, indent=2)}")

    def setup_gui(self):
        """Set up the Tkinter GUI."""
        self.root = tk.Tk()
        self.root.title("General Agentic System")
        self.root.geometry("600x700")

        # API Key
        tk.Label(self.root, text="OpenRouter API Key:").pack(pady=5)
        self.api_key_entry = tk.Entry(self.root, show="*", width=50)
        self.api_key_entry.pack()

        # Model Selection
        tk.Label(self.root, text="Model:").pack(pady=5)
        self.model = tk.StringVar(value="openai/gpt-4o")
        models = ["openai/gpt-4o", "anthropic/claude-3.5-sonnet", "meta-llama/llama-3.1-8b"]
        ttk.Combobox(self.root, textvariable=self.model, values=models).pack()

        # Temperature
        tk.Label(self.root, text="Temperature (0.0-2.0):").pack(pady=5)
        self.temperature = tk.StringVar(value="0.7")
        tk.Entry(self.root, textvariable=self.temperature, width=10).pack()

        # Max Iterations
        tk.Label(self.root, text="Max Iterations:").pack(pady=5)
        self.max_iterations = tk.StringVar(value="5")
        tk.Entry(self.root, textvariable=self.max_iterations, width=10).pack()

        # System Prompt
        tk.Label(self.root, text="System Prompt:").pack(pady=5)
        self.prompt_text = scrolledtext.ScrolledText(self.root, height=5, width=50)
        self.prompt_text.insert(tk.END, "You are a helpful assistant skilled in problem-solving and task planning.")
        self.prompt_text.pack()

        # Goal
        tk.Label(self.root, text="Goal:").pack(pady=5)
        self.goal_text = scrolledtext.ScrolledText(self.root, height=3, width=50)
        self.goal_text.insert(tk.END, "Generate a Python function to calculate Fibonacci numbers")
        self.goal_text.pack()

        # Run Button
        tk.Button(self.root, text="Run Agent", command=self.run_agent).pack(pady=10)

        # Results Display
        tk.Label(self.root, text="Results:").pack(pady=5)
        self.result_text = scrolledtext.ScrolledText(self.root, height=15, width=50)
        self.result_text.pack()

        self.root.mainloop()

# Run the agent
if __name__ == "__main__":
    agent = AgenticSystem()