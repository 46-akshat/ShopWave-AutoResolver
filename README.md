# ShopWave AI: Autonomous Customer Support Agent 🚀

ShopWave AI is a high-performance, autonomous customer support system built with **LangGraph**, **Gemini 2.5 Flash Lite**, and **FastAPI**. It intelligently processes e-commerce support tickets — handling refunds, checking order statuses, and escalating high-risk cases based on real-world business logic.

---

## 🌟 Key Features

- **Autonomous Decision Making** — Uses LLM-driven agents to decide whether to refund, deny, or escalate based on context.
- **Fail-Safe Architecture** — Implements a strict "Logic Hierarchy" to prevent unauthorized high-value refunds (automatically escalates any request over $200).
- **Deep-Unwrap Parsing** — Custom-built robust extractor to handle non-deterministic LLM outputs and JSON hallucinations, ensuring 100% processing uptime.
- **Concurrent Processing** — Orchestrator designed to handle multiple tickets simultaneously using `asyncio` for enterprise-grade scalability.
- **Audit Logging** — Generates detailed `audit_log.json` with step-by-step reasoning for every action taken by the AI.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | LangChain & LangGraph |
| Model | Google Gemini 2.5 Flash Lite |
| Environment | Python 3.11+ |
| Containerization | Docker |

---

# Architecture Diagram/System Architecture:

<img width="1961" height="931" alt="architecture" src="https://github.com/user-attachments/assets/41816653-dc4e-4337-afb9-23437878cebd" />


## 🚀 Getting Started

### 1. Prerequisites

- Python 3.11 or higher
- A valid Google Gemini API Key

### 2. Installation

```bash
# Clone the repository
git clone <repo-url>
cd hackathon2026-agent

# Set up virtual environment
python -m venv venv
source venv/Scripts/activate   # Windows
# or
source venv/bin/activate       # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_api_key_here
```

### 4. Running the Agent (Demo Mode)

```bash
python main.py
```

---

## 🐳 Docker Support (Production Ready)

The system is fully containerized for cloud deployment.

```bash
# Build the image
docker build -t shopwave-agent .

# Run with environment variables and volume mapping for logs
docker run --env-file .env -v "$(pwd):/app" shopwave-agent
```

---

## 📂 Project Structure

```
hackathon2026-agent/
├── main.py              # Concurrent orchestrator and system entry point
├── core/
│   ├── agent.py         # LangGraph logic, state management, and decision-making flow
│   └── tools.py         # Custom business tools (Refund, Status, Escalation)
├── data/                # Mock ticket data and database simulations
├── audit_log.json       # Auto-generated trail of all AI decisions
├── failure_modes.md     # Detailed analysis of system edge cases and engineering fixes
└── Dockerfile           # Production container configuration
```

---

## 🛡️ Security & Fail-Safes

- **Human-in-the-loop** — All warranty claims and refunds over $200 are automatically escalated to human agents.
- **Data Integrity** — The agent cannot modify order data directly; it only triggers pre-validated tool calls based on system records.
