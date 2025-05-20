"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""

from langgraph.graph import StateGraph

from react_agent.configuration import Configuration
from react_agent.state import InputState, State
from react_agent.nodes import (
    call_model,
    email_priorities,
    human_review,
    tools,
    user_profile,
    writing_style,
)
from react_agent.edges import route_model_output

# Define a new graph
builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node("call_model", call_model)
builder.add_node("tools", tools)
builder.add_node("human_review", human_review)
builder.add_node("user_profile", user_profile)
builder.add_node("writing_style", writing_style)
builder.add_node("email_priorities", email_priorities)

# Set the entrypoint as `call_model`
builder.add_edge("__start__", "call_model")

# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
    "call_model",
    route_model_output,
    # [
    #     "tools",
    #     "human_review",
    #     "user_profile",
    #     "writing_style",
    #     "email_priorities",
    #     "__end__",
    # ],
)

builder.add_edge("tools", "call_model")
builder.add_edge("user_profile", "call_model")
builder.add_edge("writing_style", "call_model")
builder.add_edge("email_priorities", "call_model")

# Compile the builder into an executable graph
graph = builder.compile(name="Email Assistant")
