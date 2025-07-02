# Email Assistant

An AI-powered email assistant built with LangGraph that helps manage your Gmail inbox, draft responses, and maintain context about your contacts and communication style.

## What it does

The Email Assistant:

1. Connects to your Gmail account to fetch and manage emails
2. Helps draft and send email responses based on your writing style
3. Maintains a user profile with information about your contacts and preferences
4. Provides a conversational interface for email management tasks

The core functionality is built using a [ReAct agent](https://arxiv.org/abs/2210.03629) implemented with [LangGraph](https://github.com/langchain-ai/langgraph), which allows the assistant to reason about your requests and take appropriate actions.

## Features

- **Gmail Integration**: Connect to your Gmail account to fetch, read, and send emails
- **User Profile Management**: Maintains information about your contacts and preferences
- **Writing Style Analysis**: Learns your writing style to draft appropriate responses
- **Conversational Interface**: Natural language interaction for email management

## Getting Started

### Prerequisites

- Python 3.9+
- A Gmail account
- API keys for the LLM providers you want to use (OpenAI, Anthropic, etc.)

### Installation

1. Clone this repository:
```bash
git clone [https://github.com/bravomiguel/email-assistant.git](https://github.com/bravomiguel/email-assistant.git)
cd email-assistant
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

3. Create a .env file:
```bash
cp .env.example .env
```

4. Add your API keys to the .env file:
```bash
OPENAI_API_KEY=your-api-key
# OR
ANTHROPIC_API_KEY=your-api-key
# AND
TAVILY_API_KEY=your-api-key
```

### Running the Assistant
1. Start LangGraph Studio:
```bash
langgraph dev
```

2. Open the studio in your browser and load the Email Assistant graph.

### Frontend Application

This backend works with a Next.js frontend application that provides a user-friendly interface for interacting with the email assistant. The frontend repository is available at:

https://github.com/bravomiguel/ea-frontend

Follow the instructions in the frontend repository to set up and connect it to this backend.