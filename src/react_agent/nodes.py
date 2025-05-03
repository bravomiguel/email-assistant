from typing import Dict, List, cast
from datetime import UTC, datetime
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
from langgraph.types import Command, interrupt

from react_agent.utils import load_chat_model
from react_agent.state import State
from react_agent.configuration import Configuration
from react_agent.tools import TOOLS, gmail_reply_to_thread

tools = ToolNode(TOOLS)

gmail_reply_node = ToolNode(gmail_reply_to_thread)


async def human_review_node(state: State) -> Command:
    """Handle human review of the email reply."""
    last_message = state.messages[-1]

    if not last_message.tool_calls:
        raise ValueError("No tool calls found")

    tool_call = last_message.tool_calls[-1]

    if tool_call.get("name", "") != "GMAIL_REPLY_TO_THREAD":
        return Command(goto="tools")

    human_review = interrupt(
        {
            "question": "Ready to send?",
            "recipient_email": tool_call.get("args", {}).get("recipient_email", ""),
            "message_body": tool_call.get("args", {}).get("message_body", ""),
        }
    )

    action = human_review.get("action")
    edits = human_review.get("edits")
    reject_feedback = human_review.get("reject_feedback")

    if action == "send":
        return Command(goto="tools")

    if action == "edit_send":
        updated_tool_call = {
            "role": "ai",
            "content": last_message.content,
            "tool_calls": [
                {
                    "id": tool_call["id"],
                    "name": tool_call["name"],
                    "args": {**tool_call.get("args", {}), **edits},
                }
            ],
            "id": last_message.id,
        }

        return Command(goto="tools", update={"messages": [updated_tool_call]})

    if action == "reject":
        tool_message = {
            "role": "tool",
            "content": f"Reply rejected by the user. User feedback: {reject_feedback}",
            "name": tool_call["name"],
            "tool_call_id": tool_call["id"],
        }

        return Command(goto="call_model", update={"messages": [tool_message]})


async def call_model(state: State) -> Dict[str, List[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_context()

    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(configuration.model).bind_tools(TOOLS)

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = configuration.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}
