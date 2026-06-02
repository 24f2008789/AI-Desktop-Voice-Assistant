import os
import asyncio

from Tools import *
from main import speak
from dotenv import load_dotenv
from typing import TypedDict,Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage,HumanMessage, AIMessage,SystemMessage
from langchain_groq import ChatGroq

from langgraph.types import Command
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START ,END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode, tools_condition


load_dotenv()
hf_token = os.getenv("HUGGINGFACEHUB_ACCESS_TOKEN")

tools = [open_website,play_youtube,pause_play_media,search_tool,wiki,get_tool_price,
        send_whatsapp_message,check_unread_emails,read_email_by_sender,send_professional_email,
        brightness_up,brightness_down,volume_up,volume_down]

tool_registry = {
    tool.name: tool
    for tool in tools
}

model = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.5
)

llm_tool = model.bind_tools(tools)


class ClassState(TypedDict):
    messages: Annotated[list[BaseMessage],add_messages]

    task_type: str

    plan: list[dict]

    observations: list

    final_answer: str

tool_node = ToolNode(tools)

def chat_node(state: ClassState):
    
    try:
        query = state["messages"]

        resp = llm_tool.invoke(query)
        
        print("AI CONTENT:", resp.content)
        print("TOOL CALLS:", resp.tool_calls)
        ai_text = resp.content
        asyncio.run(speak(ai_text))
        return {
            "messages": [resp]
        }
    except Exception as e:
        print("ERROR:", str(e))
        return {
            "ai_reponse" : "Sorry bro tool execution failed. please try again",
            "messages" : [AIMessage(content="Sorry bro tool execution failed.please try again")]
        }

def task_classifier(state: ClassState):
    query = state["messages"][-1].content

    prompt = f"""
    Decide whether this task is:
    SIMPLE or 
    COMPLEX
    For Example : 
    SIMPLE:  (Simple task will need only one tool and not have any need of multitasking)
    - Normal conversation
    - Open YouTube
    - Send WhatsApp
    - Read Gmail
    - Search Google
    - Adjust brightness

    COMPLEX: (complex task needs the multitasking and need more thatn 1 tool to complete the task)
    - Requires multiple tools
    - Requires sequential actions
    - One step depends on previous step output
    - Research then act
    - Search then send
    - Search then play
    - Search then summarize
    - Create folder then create file

    User Request:
    {query}

    Answer only:
    SIMPLE
    or
    COMPLEX
    """
    resp = model.invoke(prompt)
    print("Task_type : " , resp.content.strip().lower())

    return {
            "task_type": resp.content.strip().lower(),
        }

def planner_condition(state: ClassState):
    if state["task_type"] == "complex":
        return "planner"
    
    return "chat_node"

def planner_node(state):

    query = state["messages"][-1].content

    prompt = f"""
    User Request:
    {query}

    Create a short and accurate plan 

    Return plain text.
    """

    resp = model.invoke(prompt)

    print("PLAN:" , resp.content)

    return {
        "plan": resp.content
    }

def executor_node(state):

    query = state["messages"][-1].content

    prompt = f"""
    You are an autonomous execution agent.

    User Goal:
    {query}

    Plan:
    {state.get("plan", "")}

    Previous Observations:
    {state.get("observations", [])}

    Available Tools:
    {list(tool_registry.keys())}

    Instructions:

    1. Analyze the goal.
    2. Decide if another tool is required.
    3. If a tool is required, call the appropriate tool.
    4. If the goal is already completed, DO NOT call any tool.
    5. If the goal is completed, answer normally.

    Important:

    - Never write tool calls as text.
    - Never write XML tags.
    - Never write:
    <function=...>
    - Never manually generate JSON tool calls.
    - Use the actual tool-calling mechanism only.

    If a tool is needed:
    CALL THE TOOL.

    If no tool is needed:
    Respond with the final answer.
    """

    resp = llm_tool.invoke(prompt)
    
    print("Executor : ", resp.content)

    return {
        "messages":[resp]
    }

def executor_router(state: ClassState):
    
    print("executor_roouter reached")
    last_message = state["messages"][-1]

    if getattr(last_message, "tool_calls", None):

        return "tools"

    return "completion"

def observation_node(state):

    last_message = state["messages"][-1]

    observation = str(last_message.content)

    print("OBSERVATION : ", observation)

    old = state.get("observations", [])

    return {
        "observations": old + [observation]
    }


def completion_node(state):

    answer = state["messages"][-1].content

    print("FINAL ANSWER:", answer)

    asyncio.run(speak(answer))

    return {
        "final_answer": answer
    }

checkpointer = InMemorySaver()

graph = StateGraph(ClassState)
graph.add_node("task_classifier", task_classifier)
graph.add_node("chat_node", chat_node)
graph.add_node("tools",tool_node)
graph.add_node("planner", planner_node)
graph.add_node("executor_agent" , executor_node)
graph.add_node("observation",observation_node)
graph.add_node("completion",completion_node)


graph.add_edge(START,"task_classifier")
graph.add_conditional_edges(
    "task_classifier",
    planner_condition,
    {
        "chat_node":"chat_node",
        "planner": "planner"
    }
)
# Simple path
graph.add_conditional_edges("chat_node",tools_condition)
graph.add_edge("tools", "chat_node")
graph.add_edge("chat_node", END)

# Complex path
graph.add_edge("planner", "executor_agent")
graph.add_conditional_edges(
    "executor_agent",
    executor_router,
    {
        "tools":"tools",
        "completion": "completion"
    }
)
graph.add_edge("tools","observation")
graph.add_edge("observation", "executor_agent")
graph.add_edge("completion", END)

chatbot = graph.compile(checkpointer=checkpointer)
