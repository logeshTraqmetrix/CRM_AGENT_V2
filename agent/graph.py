from typing import TypedDict, List, Annotated, Any
from langgraph.graph import StateGraph, START, END, MessagesState, add_messages
from langgraph.prebuilt import ToolNode
from langchain_groq import ChatGroq
from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    SystemMessage,
    AnyMessage,
    HumanMessage,
    ToolMessage,
)
from typing_extensions import Literal
from .tools import (
    get_fields_tool,
    query_records_tool,
    create_records_tool,
    update_records_tool,
    convert_lead_tool,
    send_mail_tool,
    get_module_api_name_tool,
    get_specific_record_tool,
    create_task_tool
)

from .prompts import get_system_prompt_text
import os
from datetime import datetime, timezone
from langchain.messages import RemoveMessage
from pydantic import BaseModel, Field
groq_api_key = os.getenv("GROQ_DEV_API")
if not groq_api_key:
    raise ValueError("Environment variable GROQ_DEV_API is not set!")
os.environ["GROQ_API_KEY"] = groq_api_key



tools = [
    get_fields_tool,
    query_records_tool,
    create_records_tool,
    update_records_tool,
    convert_lead_tool,
    send_mail_tool,
    get_module_api_name_tool,
    get_specific_record_tool,
    create_task_tool
]

model_name = "qwen/qwen3-32b"

llm = ChatGroq(
    temperature=0,
    model_name=model_name,
    max_retries=2
).bind_tools(tools)

summary_llm = ChatGroq(
    temperature=0,
    model_name=model_name,
    max_retries=2,
    max_tokens=512,
    streaming=False
)



class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    summary: str | None
    summary_count: int


def call_model(state: AgentState):
    system_prompt_text = get_system_prompt_text()
    MessageLengthToAI = 10

    summary = state.get("summary", "")

    if summary:
        system_message = f"{system_prompt_text}\nSummary of conversation earlier: {summary}"
        recent_messages = state["messages"][-(MessageLengthToAI-1):] if len(state["messages"]) > (MessageLengthToAI-1) else state["messages"]
        messages = [SystemMessage(content=system_message)] + recent_messages
    else:
        system_message = f"{system_prompt_text}"
        recent_messages = state["messages"][-MessageLengthToAI:] if len(state["messages"]) > MessageLengthToAI else state["messages"]
        messages = [SystemMessage(content=system_message)] + recent_messages

    response = llm.invoke(messages)
    return {"messages": response}


def summarize_conversation(state: AgentState):
    summary = state.get("summary", "")
    summary_count = state.get("summary_count", 0)
    summary_message = f"""
        You are an expert at summarize conversation while preserving all critical information

        Rules:
        - Preserve all essential facts, decisions, APIs, parameters, and constraints.
        - Remove repetition, verbosity, and conversational text.
        - Use precise, technical language.
        - Keep logical structure intact.
        - Do not drop or invent information.

        The result must be 50–70% shorter than the full conversation while retaining 100% of essential information.

        Return only the updated condensed summary.
        """

    if summary:

        summary_message = summary_message + """
            Existing summary:
            {summary}
            Update this summary using only the new messages above."""


    filtered_messages = [
        msg for msg in state["messages"][-10:]
        if isinstance(msg, (HumanMessage, ToolMessage))
        or (
            isinstance(msg, AIMessage)
            and msg.content
            and msg.content.strip()
        )
    ]

    messages = filtered_messages + [HumanMessage(content=summary_message)]
    response = summary_llm.invoke(messages)
    
    return {"summary": response.content, "summary_count": summary_count + 1 }





def should_summarize(state: AgentState) -> str:
    """
    Determine whether to summarize the conversation based on message count.
    Summarizes every N messages to prevent context overflow.
    
    Returns:
        str: Next node to execute - either "summary_node" or "agent"
    """
    messages = state.get('messages', [])
    message_count = len(messages)
    summary_count = state.get("summary_count", 0)

    threshold = (summary_count + 1) * 10
    
    if message_count > threshold:
        return "summary_node"
    
    return "agent"


def should_continue(state: MessagesState):
    """
    Determine next step based on agent's response.
    - If tool calls exist: route to tools
    - Otherwise: end conversation
    """
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


graph = StateGraph(AgentState)

graph.add_node("agent",call_model)
graph.add_node("tools",ToolNode(tools))
graph.add_node("summary_node",summarize_conversation)

graph.add_conditional_edges(
    START,
    should_summarize,
    {
        "summary_node":"summary_node",
        "agent":"agent"
    }
)

graph.add_edge("summary_node", "agent")
graph.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools":"tools",
        END:END
    }
)
graph.add_edge("tools","agent")


app = graph.compile()