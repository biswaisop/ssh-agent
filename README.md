# SSH AI System Assistant

A powerful, AI-driven Linux system assistant that allows you to manage remote servers using natural language. Built with LangChain, Paramiko, and Groq (Llama 3.3).

## 🚀 Features

- **Natural Language Interface**: Execute complex shell tasks (e.g., "do an update", "kill process X", "check disk space") without memorizing flags.
- **Robust SSH Connector**:
    - Automatic detection of RSA, Ed25519, and ECDSA keys.
    - Supports both OpenSSH and PEM key formats.
    - Integrated password fallback.
- **Safety First**:
    - **Command Timeouts**: Prevents the agent from hanging on interactive prompts.
    - **Non-Interactive Defaults**: Automatically uses `-y` flags for package managers.
    - **Indentation Cleaning**: Cleaned tool outputs for better AI parsing.
- **Modern Tech Stack**: Powered by Llama 3.3 (70B) via Groq for lightning-fast reasoning.

## 🛠️ Setup

### 1. Prerequisites
- Python 3.12+
- UV (recommended) or pip

### 2. Environment Configuration
Create a `.env` file in the root directory:

```env
GROQ = your_groq_api_key
SSH_HOST = localhost
SSH_PORT = 2222
SSH_USERNAME = ubuntu
KEY_PATH = path/to/your/id_rsa
# PASSWORD = optional_password_fallback
```

*Note: The project uses `SSH_USERNAME` prefix to avoid conflicts with Windows system environment variables.*

### 3. Installation
```bash
# Using UV
uv sync

# Or using pip
python -m venv .venv
.\.venv\Scripts\activate
pip install -r pyproject.toml
```

### 4. Running the Assistant
```bash
python main.py
```

## 🐳 Docker Support (Optional)
The project includes a `Dockerfile` to spin up a local Ubuntu SSH server for testing.

```bash
docker build -t ssh-server .
docker run -d -p 2222:22 --name ssh-container ssh-server
```

## 📂 Project Structure

- `agents/`: LangChain agent logic and prompts.
- `connectors/`: Raw SSH connectivity using Paramiko.
- `tools/`: LangChain tools (ShellTool).
- `brain/`: LLM configuration.
- `utils/`: Output formatting and helpers.
- `config.py`: Pydantic settings management.

## ⚠️ Known Gotchas
- **Windows Environment**: If you are on Windows, ensure your `KEY_PATH` uses forward slashes (e.g., `C:/Users/.../.ssh/id_rsa`).
- **Permissions**: Ensure your SSH private key has correct permissions if running on Linux/macOS.
