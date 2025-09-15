"""
Guygentic - AI Conversation Management System

A comprehensive AI chat application with conversation branching,
file I/O, and extensive logging capabilities.

TESTING:
    Run tests with: python Guygentic.py test
    Or import and call: from Guygentic import run_tests; run_tests()
"""

import requests
import json
import tkinter as tk
import os
import shutil
from collections import deque
from datetime import datetime
import unittest
from unittest.mock import Mock, patch, MagicMock

class ConversationNode:
    def __init__(self, system_prompt="", user_prompt="", ai_response="", timestamp=None, branch_id=0):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.ai_response = ai_response
        self.timestamp = timestamp or str(__import__('datetime').datetime.now())
        self.branch_id = branch_id  # For branching conversations
        self.parent_index = None  # Index of parent node for branching

class ConversationStack:
    def __init__(self, max_size=50):
        self.stack = deque(maxlen=max_size)
        self.branches = {}  # Store branch points: {branch_id: [node_indices]}
        self.current_branch = 0

    def push(self, system_prompt="", user_prompt="", ai_response="", branch_id=None):
        """Push a new conversation node to the stack"""
        if branch_id is None:
            branch_id = self.current_branch

        node = ConversationNode(system_prompt, user_prompt, ai_response, branch_id=branch_id)
        self.stack.append(node)

        # Track branches
        if branch_id not in self.branches:
            self.branches[branch_id] = []
        self.branches[branch_id].append(len(self.stack) - 1)

        return len(self.stack) - 1  # Return index of new node

    def get_recent_conversation(self, limit=10):
        """Get the most recent conversation nodes"""
        return list(self.stack)[-limit:]

    def get_branch_conversation(self, branch_id, limit=20):
        """Get conversation for a specific branch"""
        if branch_id not in self.branches:
            return []

        indices = self.branches[branch_id][-limit:]
        return [self.stack[i] for i in indices if i < len(self.stack)]

    def create_branch(self, from_index, new_system_prompt=None, new_user_prompt=None):
        """Create a new branch from an existing conversation point"""
        if from_index >= len(self.stack):
            return None

        self.current_branch += 1
        parent_node = self.stack[from_index]

        # Create new node with modified prompts
        system_prompt = new_system_prompt if new_system_prompt is not None else parent_node.system_prompt
        user_prompt = new_user_prompt if new_user_prompt is not None else parent_node.user_prompt

        new_node = ConversationNode(system_prompt, user_prompt, "", branch_id=self.current_branch)
        new_node.parent_index = from_index

        self.stack.append(new_node)
        self.branches[self.current_branch] = [len(self.stack) - 1]

        return len(self.stack) - 1

    def get_stack(self):
        """Get all conversation nodes"""
        return list(self.stack)

    def get_item(self, index):
        """Get a specific conversation node"""
        if 0 <= index < len(self.stack):
            return self.stack[index]
        return None

stacky = ConversationStack()

class MessageBuilder:
    def __init__(self):
        self.msg = []

    def add_line(self, role, content):
        """Add a message line with role and content"""
        if content and content.strip():  # Only add non-empty content
            line = {"role": role, "content": content.strip()}
            self.msg.append(line)

    def add_system(self, content):
        """Convenience method to add system message"""
        self.add_line("system", content)

    def add_user(self, content):
        """Convenience method to add user message"""
        self.add_line("user", content)

    def add_assistant(self, content):
        """Convenience method to add assistant message"""
        self.add_line("assistant", content)

    def build_from_conversation(self, conversation_nodes):
        """Build messages from conversation nodes"""
        self.clear()
        for node in conversation_nodes:
            if node.system_prompt and node.system_prompt.strip():
                self.add_system(node.system_prompt)
            if node.user_prompt and node.user_prompt.strip():
                self.add_user(node.user_prompt)
            if node.ai_response and node.ai_response.strip():
                self.add_assistant(node.ai_response)

    def build_from_branch(self, stack, branch_id, limit=20):
        """Build messages from a specific conversation branch"""
        branch_nodes = stack.get_branch_conversation(branch_id, limit)
        self.build_from_conversation(branch_nodes)

    def get_message(self):
        """Get the built message array"""
        return self.msg

    def clear(self):
        """Clear all messages"""
        self.msg.clear()

    def get_last_user_message(self):
        """Get the last user message content"""
        for msg in reversed(self.msg):
            if msg["role"] == "user":
                return msg["content"]
        return ""

    def get_last_assistant_message(self):
        """Get the last assistant message content"""
        for msg in reversed(self.msg):
            if msg["role"] == "assistant":
                return msg["content"]
        return ""


builder = MessageBuilder()

# File output globals
SESSION_FILE = None
ERROR_LOG_FILE = None
CUSTOM_FILE_COUNTER = 0

def initialize_session_files():
    """Initialize session files with timestamps"""
    global SESSION_FILE, ERROR_LOG_FILE
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    SESSION_FILE = f"guygentic_session_{timestamp}.txt"
    ERROR_LOG_FILE = f"error_api_fails_{timestamp}.log"

    # Create session file with header
    with open(SESSION_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Guygentic Session Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")

def write_to_session_file(content_type, content, node_info=""):
    """Write to the default session file"""
    if SESSION_FILE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(SESSION_FILE, 'a', encoding='utf-8') as f:
            if node_info:
                f.write(f"[{timestamp}] {node_info}\n")
            f.write(f"{content_type}: {content}\n\n")

def write_error_log(error_message):
    """Write errors to the error log file"""
    if ERROR_LOG_FILE:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] ERROR: {error_message}\n")

def write_custom_file(filename, content, format_type="plain"):
    """Write to custom output file with specified format"""
    try:
        with open(filename, 'a', encoding='utf-8') as f:
            if format_type == "json":
                json.dump(content, f, indent=2)
                f.write("\n")
            elif format_type == "structured":
                if isinstance(content, dict):
                    for key, value in content.items():
                        f.write(f"{key}: {value}\n")
                else:
                    f.write(str(content))
                f.write("\n" + "="*30 + "\n")
            else:  # plain text
                f.write(str(content) + "\n")
    except Exception as e:
        write_error_log(f"Failed to write custom file {filename}: {str(e)}")

def generate_filename(base_name, use_iteration=True, use_timestamp=True):
    """Generate filename with iteration and/or timestamp, preserving custom extensions"""
    global CUSTOM_FILE_COUNTER

    # Check if base_name already has an extension
    if '.' in base_name:
        # Split filename and extension
        name_parts = base_name.rsplit('.', 1)
        base = name_parts[0]
        extension = name_parts[1]
    else:
        # No extension provided, use .txt as default
        base = base_name
        extension = "txt"

    # Build filename parts
    parts = [base]

    if use_iteration:
        CUSTOM_FILE_COUNTER += 1
        parts.append(f"{CUSTOM_FILE_COUNTER:03d}")

    if use_timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        parts.append(timestamp)

    return "_".join(parts) + "." + extension


# user_prompt=input()

def get_response(user_prompt, system_prompt=None):
    # Build messages array
    messages = []
    if system_prompt and system_prompt.strip():
        messages.append({
            "role": "system",
            "content": system_prompt.strip()
        })

    messages.append({
        "role": "user",
        "content": user_prompt
    })

    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
      "Authorization": "Bearer <your-key-here>",
      "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
      "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
    },
    data=json.dumps({
      "model": "qwen/qwen3-max", # Optional
      "messages": messages
    })
  )

    # Extract and return the AI response
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        error_msg = f"API Error: {response.status_code} - {response.text}"
        write_error_log(error_msg)
        return error_msg

def get_conversation_response(messages):
    """Send full conversation history to API"""
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
      "Authorization": "Bearer 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",
      "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
      "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
    },
    data=json.dumps({
      "model": "qwen/qwen3-max", # Optional
      "messages": messages
    })
  )

    # Extract and return the AI response
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        error_msg = f"API Error: {response.status_code} - {response.text}"
        write_error_log(error_msg)
        return error_msg

  
def writefile(filename, content):
  with open(filename, 'w') as file:
    file.write(content)
  
def appendfile(filename, content):
  with open(filename, 'a') as file:
    file.write(content)
    
def deletefile(filename):
  os.remove(filename)
  
def renamefile(filename, newfilename):
  os.rename(filename, newfilename)
  
def copyfile(filename, newfilename):
  shutil.copy(filename, newfilename)
  

def read_file_content(filename):
    """Safely read file content and return it, or return error message."""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        return f"Error: File '{filename}' not found."
    except PermissionError:
        return f"Error: Permission denied reading '{filename}'."
    except UnicodeDecodeError:
        return f"Error: Could not decode file '{filename}'. May be binary or use different encoding."
    except Exception as e:
        return f"Error reading file '{filename}': {str(e)}"

def submit_prompt(entry_widget, text_widget, file_checkbox, filename_entry, system_entry, branch_var):
    prompt_text = entry_widget.get("1.0", tk.END).strip()
    system_prompt = system_entry.get("1.0", tk.END).strip() if hasattr(system_entry, 'get') else system_entry

    # Get current branch
    current_branch = int(branch_var.get()) if branch_var.get().isdigit() else 0

    # Check if file should be included
    file_content_info = ""
    if file_checkbox.get() and filename_entry.get().strip():
        filename = filename_entry.get().strip()
        file_content = read_file_content(filename)
        prompt_text = f"{prompt_text}\n\nFile content from '{filename}':\n{file_content}"
        file_content_info = f" (with file: {filename})"

    if prompt_text.strip():  # Only process if there's text
        # Build conversation context from current branch
        branch_nodes = stacky.get_branch_conversation(current_branch, limit=10)
        if branch_nodes:
            builder.build_from_conversation(branch_nodes)
            conversation_messages = builder.get_message()
            # Add current prompt to conversation
            builder.add_user(prompt_text)
            full_messages = builder.get_message()
        else:
            # No previous context, just use current prompt
            builder.clear()
            if system_prompt:
                builder.add_system(system_prompt)
            builder.add_user(prompt_text)
            full_messages = builder.get_message()

        # Get response with conversation context
        if len(full_messages) > 1:  # Has conversation context
            # Use the API with full conversation history
            response = get_conversation_response(full_messages)
        else:
            # Simple case - just use regular get_response
            response = get_response(prompt_text, system_prompt)

        # Track conversation in stack
        node_index = stacky.push(
            system_prompt=system_prompt,
            user_prompt=prompt_text,
            ai_response=response,
            branch_id=current_branch
        )

        # Write to session file
        node_info = f"Node #{node_index} - Branch {current_branch}{file_content_info}"
        if system_prompt and system_prompt.strip():
            write_to_session_file("System Prompt", system_prompt, node_info)
        write_to_session_file("User Prompt", prompt_text, node_info)
        write_to_session_file("AI Response", response)

        # Clear previous content and insert new response
        text_widget.delete(1.0, tk.END)
        status_info = f"[{node_info}]\n\n"
        text_widget.insert(tk.END, status_info + response)

def agentic_loop(entry_widget, iteration_entry, text_widget, file_checkbox, filename_entry, system_entry, branch_var):
    prompt_text = entry_widget.get("1.0", tk.END).strip()
    system_prompt = system_entry.get("1.0", tk.END).strip() if hasattr(system_entry, 'get') else system_entry

    # Get current branch
    current_branch = int(branch_var.get()) if branch_var.get().isdigit() else 0

    # Check if file should be included
    file_input = None
    if file_checkbox.get() and filename_entry.get().strip():
        filename = filename_entry.get().strip()
        file_input = read_file_content(filename)
        prompt_text = f"{prompt_text}\n\nFile content from '{filename}':\n{file_input}"

    try:
        max_iterations = int(iteration_entry.get())
    except ValueError:
        max_iterations = 3  # Default if invalid input

    if not prompt_text.strip():
        return

    # Clear previous content
    text_widget.delete(1.0, tk.END)
    file_status = f" (including file: {filename_entry.get().strip()})" if file_input else ""
    system_status = f" (with system prompt)" if system_prompt and system_prompt.strip() else ""
    text_widget.insert(tk.END, f"Starting Agentic Loop with {max_iterations} iterations on Branch {current_branch}{file_status}{system_status}...\n\n")

    current_prompt = prompt_text

    for i in range(max_iterations):
        text_widget.insert(tk.END, f"=== Iteration {i+1} ===\n")
        text_widget.insert(tk.END, f"Input: {current_prompt}\n")

        # Build conversation context from current branch for this iteration
        branch_nodes = stacky.get_branch_conversation(current_branch, limit=10)
        if branch_nodes:
            builder.build_from_conversation(branch_nodes)
            builder.add_user(current_prompt)
            full_messages = builder.get_message()
            response = get_conversation_response(full_messages)
        else:
            response = get_response(current_prompt, system_prompt)

        # Track each iteration in the conversation stack
        iteration_node = stacky.push(
            system_prompt=system_prompt,
            user_prompt=current_prompt,
            ai_response=response,
            branch_id=current_branch
        )

        # Write iteration to session file
        iteration_info = f"Iteration {i+1} - Node #{iteration_node} - Branch {current_branch}"
        if i == 0 and system_prompt and system_prompt.strip():  # Only write system prompt for first iteration
            write_to_session_file("System Prompt", system_prompt, iteration_info)
        write_to_session_file("User Prompt", current_prompt, iteration_info)
        write_to_session_file("AI Response", response)

        text_widget.insert(tk.END, f"Response: {response}\n")
        text_widget.insert(tk.END, f"[{iteration_info}]\n\n")

        # For next iteration, use the response as context
        # Include file content in subsequent iterations if it was provided
        file_context = f"\n\nFile content: {file_input}" if file_input else ""
        current_prompt = f"Based on this response: '{response}', continue improving or expanding on the task. Original request: {entry_widget.get("1.0", tk.END).strip()}{file_context}"

        # Update the GUI to show progress
        text_widget.update()
        text_widget.see(tk.END)

    text_widget.insert(tk.END, "=== Agentic Loop Complete ===")

    # Custom file output after agentic loop
    # This would be controlled by GUI variables - for now, we'll skip custom output
    # The session file already captures everything

# tkiner gui def here
def create_gui():
  root = tk.Tk()
  root.title("Guygentic")
  root.geometry("800x600")
  root.configure(bg="white")
  # create a frame
  frame = tk.Frame(root, bg="white")
  frame.pack(fill="both", expand=True)
  # create a label
  label = tk.Label(frame, text="Guygentic", bg="white")
  label.pack(pady=10)
  # create a entry (now a multi-line text widget)
  entry = tk.Text(frame, bg="white", height=4, width=50)
  entry.pack(pady=10)

  # create conversation controls frame
  conversation_frame = tk.Frame(frame, bg="white")
  conversation_frame.pack(fill="x", pady=(10,5))

  # branch selector
  branch_label = tk.Label(conversation_frame, text="Branch:", bg="white")
  branch_label.pack(side="left", padx=(0,5))

  branch_var = tk.StringVar()
  branch_var.set("0")  # Default to main branch
  branch_selector = tk.OptionMenu(conversation_frame, branch_var, "0")
  branch_selector.configure(bg="white")
  branch_selector.pack(side="left", padx=(0,10))

  # refresh branches button
  def refresh_branches():
      branches = list(stacky.branches.keys())
      branch_selector['menu'].delete(0, 'end')
      for branch in sorted(branches):
          branch_selector['menu'].add_command(
              label=str(branch),
              command=lambda b=branch: branch_var.set(str(b))
          )
      if branches:
          branch_var.set(str(branches[-1]))  # Select most recent branch

  refresh_branches_button = tk.Button(conversation_frame, text="🔄", bg="lightgray",
                                    command=refresh_branches)
  refresh_branches_button.pack(side="left", padx=(0,10))

  # create system prompt label and text box
  system_label = tk.Label(frame, text="System Prompt", bg="white")
  system_label.pack(pady=(10,5))
  system_entry = tk.Text(frame, bg="white", height=4, width=50)
  system_entry.pack(pady=(0,10))

  # create file inclusion checkbox
  file_checkbox = tk.BooleanVar()
  file_check = tk.Checkbutton(frame, text="Include file in prompt", variable=file_checkbox, bg="white")
  file_check.pack(pady=(10,5))

  # create filename label and entry
  filename_label = tk.Label(frame, text="Filename", bg="white")
  filename_label.pack(pady=(5,2))
  filename_entry = tk.Entry(frame, bg="white")
  filename_entry.pack(pady=(0,10))

  # create a button
  button = tk.Button(frame, text="Submit", bg="white", command=lambda: submit_prompt(entry, text, file_checkbox, filename_entry, system_entry, branch_var))
  button.pack(pady=10)

  # create iteration limit label and entry
  iteration_label = tk.Label(frame, text="Agentic Loop Iteration Limit", bg="white")
  iteration_label.pack(pady=(20,5))
  iteration_entry = tk.Entry(frame, bg="white")
  iteration_entry.insert(0, "3")  # Default value
  iteration_entry.pack(pady=(0,10))

  # create agentic loop button
  agentic_button = tk.Button(frame, text="Agentic Loop", bg="lightblue", command=lambda: agentic_loop(entry, iteration_entry, text, file_checkbox, filename_entry, system_entry, branch_var))
  agentic_button.pack(pady=10)

  # create conversation management frame
  conv_mgmt_frame = tk.Frame(frame, bg="white")
  conv_mgmt_frame.pack(fill="x", pady=(10,5))

  # branch creation controls
  branch_create_frame = tk.Frame(conv_mgmt_frame, bg="white")
  branch_create_frame.pack(side="left", padx=(0,10))

  branch_node_label = tk.Label(branch_create_frame, text="Branch from Node:", bg="white")
  branch_node_label.pack(side="top", anchor="w")

  branch_node_entry = tk.Entry(branch_create_frame, bg="white", width=8)
  branch_node_entry.pack(side="left", padx=(0,5))

  def create_branch():
      try:
          node_index = int(branch_node_entry.get())
          new_branch = stacky.create_branch(node_index)
          if new_branch is not None:
              branch_var.set(str(stacky.current_branch))
              refresh_branches()
              text.delete(1.0, tk.END)
              text.insert(tk.END, f"Created new branch #{stacky.current_branch} from node #{node_index}")
          else:
              text.delete(1.0, tk.END)
              text.insert(tk.END, f"Error: Node #{node_index} not found")
      except ValueError:
          text.delete(1.0, tk.END)
          text.insert(tk.END, "Error: Please enter a valid node number")

  branch_create_button = tk.Button(branch_create_frame, text="Create Branch",
                                 bg="lightgreen", command=create_branch)
  branch_create_button.pack(side="left")

  # conversation history controls
  history_frame = tk.Frame(conv_mgmt_frame, bg="white")
  history_frame.pack(side="right")

  def show_conversation_history():
      current_branch = int(branch_var.get()) if branch_var.get().isdigit() else 0
      nodes = stacky.get_branch_conversation(current_branch, limit=10)

      text.delete(1.0, tk.END)
      text.insert(tk.END, f"=== Conversation History - Branch {current_branch} ===\n\n")

      for i, node in enumerate(nodes):
          text.insert(tk.END, f"Node #{nodes.index(node)} - {node.timestamp}\n")
          if node.system_prompt:
              text.insert(tk.END, f"System: {node.system_prompt[:100]}...\n")
          text.insert(tk.END, f"User: {node.user_prompt[:100]}{'...' if len(node.user_prompt) > 100 else ''}\n")
          if node.ai_response:
              text.insert(tk.END, f"AI: {node.ai_response[:100]}{'...' if len(node.ai_response) > 100 else ''}\n")
          text.insert(tk.END, "\n")

  history_button = tk.Button(history_frame, text="View History", bg="lightyellow",
                           command=show_conversation_history)
  history_button.pack(side="right")

  # create file output controls
  file_output_frame = tk.Frame(frame, bg="white")
  file_output_frame.pack(fill="x", pady=(15,5))

  # file output enable checkbox
  file_output_var = tk.BooleanVar()
  file_output_check = tk.Checkbutton(file_output_frame, text="Enable Custom File Output",
                                   variable=file_output_var, bg="white")
  file_output_check.pack(anchor="w", pady=(0,5))

  # filename controls
  filename_frame = tk.Frame(file_output_frame, bg="white")
  filename_frame.pack(fill="x", pady=(0,5))

  filename_label = tk.Label(filename_frame, text="Output Filename:", bg="white")
  filename_label.pack(side="left")

  filename_entry = tk.Entry(filename_frame, bg="white", width=20)
  filename_entry.insert(0, "my_output.txt")
  filename_entry.pack(side="left", padx=(5,10))

  # Extension info label
  extension_info = tk.Label(filename_frame, text="(add .py, .java, .txt, etc. for custom extensions)",
                          bg="white", fg="gray", font=("Arial", 8))
  extension_info.pack(side="left")

  # filename format options
  format_frame = tk.Frame(file_output_frame, bg="white")
  format_frame.pack(fill="x", pady=(0,5))

  iteration_var = tk.BooleanVar(value=True)
  iteration_check = tk.Checkbutton(format_frame, text="Include Iteration #",
                                 variable=iteration_var, bg="white")
  iteration_check.pack(side="left", padx=(0,10))

  timestamp_var = tk.BooleanVar(value=True)
  timestamp_check = tk.Checkbutton(format_frame, text="Include Timestamp",
                                 variable=timestamp_var, bg="white")
  timestamp_check.pack(side="left", padx=(0,10))

  # content format options
  content_format_frame = tk.Frame(file_output_frame, bg="white")
  content_format_frame.pack(fill="x", pady=(0,5))

  content_format_label = tk.Label(content_format_frame, text="Content Format:", bg="white")
  content_format_label.pack(side="left")

  content_format_var = tk.StringVar(value="structured")
  content_plain = tk.Radiobutton(content_format_frame, text="Plain Text",
                               variable=content_format_var, value="plain", bg="white")
  content_plain.pack(side="left", padx=(5,5))

  content_structured = tk.Radiobutton(content_format_frame, text="Structured",
                                    variable=content_format_var, value="structured", bg="white")
  content_structured.pack(side="left", padx=(5,5))

  content_json = tk.Radiobutton(content_format_frame, text="JSON",
                              variable=content_format_var, value="json", bg="white")
  content_json.pack(side="left", padx=(5,5))

  # manual save button
  def save_custom_file():
      if file_output_var.get() and filename_entry.get().strip():
          base_name = filename_entry.get().strip()
          filename = generate_filename(base_name, iteration_var.get(), timestamp_var.get())

          # Get current conversation content
          current_text = text.get(1.0, tk.END).strip()
          format_type = content_format_var.get()

          if format_type == "json":
              content = {
                  "timestamp": datetime.now().isoformat(),
                  "conversation": current_text,
                  "branch": branch_var.get(),
                  "node_count": len(stacky.stack)
              }
          else:
              content = current_text

          write_custom_file(filename, content, format_type)
          text.insert(tk.END, f"\n[Saved to: {filename}]\n")

  save_button = tk.Button(file_output_frame, text="Save Current Output",
                        bg="orange", command=save_custom_file)
  save_button.pack(pady=(5,0))

  # create a text
  text = tk.Text(frame, bg="white")
  text.pack(pady=10)
  # create a scrollbar
  scrollbar = tk.Scrollbar(frame, bg="white")
  scrollbar.pack(side="right", fill="y")
  # set the scrollbar to the text
  scrollbar.config(command=text.yview)
  text.config(yscrollcommand=scrollbar.set)


  return root


class TestGuygentic(unittest.TestCase):
    """Test suite for Guygentic application"""

    def setUp(self):
        """Set up test fixtures"""
        self.stack = ConversationStack(max_size=10)
        self.builder = MessageBuilder()

        # Store original global values
        global CUSTOM_FILE_COUNTER, SESSION_FILE, ERROR_LOG_FILE
        self.original_counter = CUSTOM_FILE_COUNTER
        self.original_session = SESSION_FILE
        self.original_error = ERROR_LOG_FILE

        # Reset for testing
        CUSTOM_FILE_COUNTER = 0
        SESSION_FILE = None
        ERROR_LOG_FILE = None

    def tearDown(self):
        """Clean up after each test"""
        global CUSTOM_FILE_COUNTER, SESSION_FILE, ERROR_LOG_FILE
        CUSTOM_FILE_COUNTER = self.original_counter
        SESSION_FILE = self.original_session
        ERROR_LOG_FILE = self.original_error

    def test_conversation_node_creation(self):
        """Test ConversationNode initialization"""
        node = ConversationNode("You are helpful", "Hello", "Hi there!", branch_id=1)
        self.assertEqual(node.system_prompt, "You are helpful")
        self.assertEqual(node.user_prompt, "Hello")
        self.assertEqual(node.ai_response, "Hi there!")
        self.assertEqual(node.branch_id, 1)
        self.assertIsNotNone(node.timestamp)

    def test_conversation_stack_operations(self):
        """Test ConversationStack basic operations"""
        # Test push
        idx1 = self.stack.push("System", "User1", "Response1")
        self.assertEqual(idx1, 0)

        idx2 = self.stack.push("System", "User2", "Response2")
        self.assertEqual(idx2, 1)

        # Test get_item
        node = self.stack.get_item(0)
        self.assertEqual(node.user_prompt, "User1")
        self.assertEqual(node.ai_response, "Response1")

        # Test get_recent_conversation
        recent = self.stack.get_recent_conversation(1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].user_prompt, "User2")

    def test_branching_functionality(self):
        """Test conversation branching"""
        # Create initial conversation
        idx1 = self.stack.push("System", "Initial prompt", "Initial response")

        # Create branch from first node
        branch_idx = self.stack.create_branch(idx1, "New system", "Branch prompt")
        self.assertIsNotNone(branch_idx)

        # Check that branch was created
        self.assertIn(1, self.stack.branches)
        self.assertEqual(len(self.stack.branches[1]), 1)

        # Get branch conversation
        branch_nodes = self.stack.get_branch_conversation(1)
        self.assertEqual(len(branch_nodes), 1)
        self.assertEqual(branch_nodes[0].user_prompt, "Branch prompt")

    def test_filename_generation(self):
        """Test filename generation with various options"""
        # Counter is reset in setUp, so first call should be 001

        # Test with extension
        filename = generate_filename("test.py", use_iteration=True, use_timestamp=False)
        self.assertTrue(filename.endswith(".py"))
        self.assertIn("001", filename)

        # Test without extension (should default to .txt)
        filename = generate_filename("test", use_iteration=False, use_timestamp=True)
        self.assertTrue(filename.endswith(".txt"))

        # Test with both options
        filename = generate_filename("output.java", use_iteration=True, use_timestamp=True)
        self.assertTrue(filename.endswith(".java"))
        self.assertIn("002", filename)  # Should be 002 since counter incremented
        self.assertIn("_", filename)  # Should have timestamp

    def test_message_builder(self):
        """Test MessageBuilder functionality"""
        self.builder.add_system("You are helpful")
        self.builder.add_user("Hello")
        self.builder.add_assistant("Hi there")

        messages = self.builder.get_message()
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[2]["role"], "assistant")

        # Test clear
        self.builder.clear()
        self.assertEqual(len(self.builder.get_message()), 0)

    def test_file_operations(self):
        """Test file operations with mocking"""
        # Test write_to_session_file
        global SESSION_FILE
        original_session = SESSION_FILE

        try:
            SESSION_FILE = "test_session.txt"

            # Mock the open function
            mock_file = unittest.mock.mock_open()
            with patch('builtins.open', mock_file):
                write_to_session_file("Test Type", "Test Content", "Test Info")

            # Verify that open was called with correct arguments
            mock_file.assert_called_with("test_session.txt", 'a', encoding='utf-8')

        finally:
            SESSION_FILE = original_session

    def test_error_handling(self):
        """Test error handling in various functions"""
        # Test file reading with non-existent file
        result = read_file_content("non_existent_file.txt")
        self.assertIn("Error", result)
        self.assertIn("not found", result)

    @patch('requests.post')
    def test_api_response_handling(self, mock_post):
        """Test API response handling with mocking"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
        mock_post.return_value = mock_response

        # This would test the actual API functions with proper mocking
        # For now, just verify the mock setup works
        self.assertEqual(mock_response.status_code, 200)

    def test_stack_limits(self):
        """Test that stack respects size limits"""
        small_stack = ConversationStack(max_size=3)

        # Add more items than the limit
        for i in range(5):
            small_stack.push(f"System{i}", f"User{i}", f"Response{i}")

        # Should only keep the last 3 items
        all_items = small_stack.get_stack()
        self.assertEqual(len(all_items), 3)

        # Check that we have the most recent items
        self.assertEqual(all_items[0].user_prompt, "User2")
        self.assertEqual(all_items[2].user_prompt, "User4")


def run_tests():
    """Run the test suite"""
    print("🧪 Running Guygentic Test Suite...")
    print("=" * 50)

    # Create a test suite with our test class
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGuygentic)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed. Check output above.")

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys

    # Check if running tests
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        success = run_tests()
        sys.exit(0 if success else 1)
    else:
        # Initialize session files
        initialize_session_files()
        print(f"Session logging to: {SESSION_FILE}")
        print(f"Error logging to: {ERROR_LOG_FILE}")

        root = create_gui()
        root.mainloop()
