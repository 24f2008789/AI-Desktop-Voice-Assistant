import os
import asyncio
import sqlite3

from Tools import *
from main import speak
from dotenv import load_dotenv
from typing import TypedDict,Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage,HumanMessage, AIMessage,SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.sqlite import SqliteSaver
from memory_store import save_memory, retrieve_memories

from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START ,END
from langgraph.prebuilt import ToolNode, tools_condition


load_dotenv()
hf_token = os.getenv("HUGGINGFACEHUB_ACCESS_TOKEN")

tools = [open_website,play_youtube,pause_media,play_media,search_tool,wiki,get_tool_price,
        send_whatsapp_message,check_unread_emails,read_email_by_sender,send_professional_email,
        brightness_up,brightness_down,volume_up,volume_down]

tool_registry = {
    tool.name: tool
    for tool in tools
}

model = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
)
classifier_model = ChatGroq(
    model="qwen/qwen3-32b",
    temperature=0
)
llm_tool = model.bind_tools(tools)


class ClassState(TypedDict):
    messages: Annotated[list[BaseMessage],add_messages]

    task_type: str

    plan: list[dict]

    observations: list

    task_completed: bool

    final_answer: str

tool_node = ToolNode(tools)
system_personna = SystemMessage(content="""
                You are Sierra, a very sweet and coversational girl who talks with everyone kindly and clearly

                Rules:
                
                Reply in the same language as the user.
                Keep responses short, natural, and conversational.
                Use tools only when required.
                Never fake or manually write tool calls.
                Never write <function=...> or tool syntax in text.
                If a tool is needed, call the actual tool directly.
                After tool execution, explain the result naturally.
                Preserve the user's exact message when sending texts or WhatsApp messages.
                Ask for confirmation before sending messages, emails, or performing sensitive actions.
                If information is unclear, ask the user for clarification first.
                Check if the given task is done successfully or not, if yes end the conversation, If not do it at max 3 times then also not able to solve then give honest answer to the user that you are not able to do.
                If you are not able to do the given task then honestly reply the user that I am not able to do, Don't "HALLUCINATE". 
                If no tool is needed, respond normally.
                Use WhatsApp tool ONLY for WhatsApp messages.
                Use Gmail tool ONLY for emails.
""")
def extract_memory(user_text):

    prompt = f"""
    Extract ONLY information that would be useful in future conversations.

    Store:
    - User preferences
    - Favourite things
    - Personal profile information
    - Long-term goals
    - Projects being worked on
    - Important relationships
    - Recurring habits

    Do NOT store:
    - Greetings
    - Casual conversation
    - Temporary requests
    - Tool usage
    - Questions
    - Small talk

    User Message:
    {user_text}

    Return:

    MEMORY: <fact>

    or

    NONE
    """

    resp = model.invoke(prompt)

    return resp.content.strip()

def chat_node(state: ClassState):
    print("-----------------------chat_node---------------")
    try:
        user_query = ""

        # Find latest human message
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_query = msg.content
                break
        
        memory_context = retrieve_memories(user_query)
        
        system_memory = SystemMessage(content=f"""
                Below given information is just your knowledge purpose, 
                use it when required but don't need to share it with 
                user unless user ask for it or it's relevant to the conversation.
                                      
                {memory_context}
                """
            )
        recent_history = state["messages"][-8:]
        messages = [system_personna, system_memory] + recent_history

        resp = llm_tool.invoke(messages)

        memory = extract_memory(user_query)

        if memory != "NONE":
            save_memory(memory)

        ai_text = resp.content
        print("AI Response:", ai_text)
        if ai_text:
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
    Classify the user request.

    SIMPLE:
    - Normal conversation
    - Greetings
    - Questions and answers
    - Chit-chat
    - One-step actions
    - Requires 0 or 1 tool
    - Can be completed immediately

    Examples:
    - Hi
    - How are you?
    - What time is it?
    - Open YouTube
    - If task is unclear ask again what clear your question before execution of anytools.
    - Search Python tutorial
    - Open VS Code

    COMPLEX:
    - Requires multiple steps
    - Requires multiple tools
    - One step depends on another
    - Requires planning

    Examples:
    - Search latest AI news and email me summary
    - Find a restaurant and send directions to WhatsApp
    - Create folder, create file, and write code
    - Research a topic and generate report

    User Request:
    {query}

    Answer ONLY:

    SIMPLE

    or

    COMPLEX
    """
    resp = classifier_model.invoke(prompt)
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

    if state.get("task_completed", False):
        return {
            "messages":[
                AIMessage(content="Task completed successfully.")
            ]
        }

    query = state["messages"][-1].content

    prompt = f"""
    If information is missing or ask to need ot fetch some information then use search tool:
    USE TOOLS.

    Never write tool names as text.

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
    If goal completed:
    STOP

    If no tool is needed:
    Respond with the final answer.
    """

    try:
        memory_context = get_memories()

        resp = llm_tool.invoke([
                SystemMessage(content=memory_context),
                HumanMessage(content=prompt)
            ])

    except Exception as e:

        print("Tool Calling Error:", e)

        return {
            "messages":[
                AIMessage(
                    content="I encountered an issue while using tools. Let me try another approach."
                )
            ]
        }
    print("complex_Tool_Calling", resp.tool_calls)
    
    print("Executor : ", resp.content)

    return {
        "messages":[resp]
    }

def completion_checker(state):

    query = state["messages"][0].content

    observations = state.get("observations", [])

    prompt = f"""
    User Goal:
    {query}

    Observations:
    {observations}

    Based on observations,
    has the user goal been completed?

    Answer only:

    YES

    or

    NO
    """

    resp = model.invoke(prompt)

    completed = "yes" in resp.content.lower()

    print("TASK COMPLETED =", completed)

    return {
        "task_completed": completed
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

def completion_router(state):

    if state["task_completed"]:
        return "completion"

    return "executor_agent"

def completion_node(state):

    answer = state["messages"][-1].content

    print("FINAL ANSWER:", answer)

    asyncio.run(speak(answer))

    return {
        "final_answer": answer
    }

conn = sqlite3.connect(database='chatbot.db', check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

graph = StateGraph(ClassState)
graph.add_node("task_classifier", task_classifier)
graph.add_node("chat_node", chat_node)
graph.add_node("simple_tools", ToolNode(tools))
graph.add_node("executor_tools", ToolNode(tools))
graph.add_node("planner", planner_node)
graph.add_node("executor_agent" , executor_node)
graph.add_node("completion_checker",completion_checker)
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
graph.add_conditional_edges(
    "chat_node",
    tools_condition,
    {
        "tools": "simple_tools",
        "__end__": END
    })
graph.add_edge("simple_tools","chat_node")

# Complex path
graph.add_edge("planner", "executor_agent")
graph.add_conditional_edges(
    "executor_agent",
    executor_router,
    {
        "tools":"executor_tools",
        "completion": "completion"
    }
)
graph.add_edge("executor_tools","observation")
graph.add_edge("observation","completion_checker")
graph.add_conditional_edges(
    "completion_checker",
    completion_router,
    {
        "completion": "completion",
        "executor_agent": "executor_agent"
    }
)
graph.add_edge("completion", END)

chatbot = graph.compile(checkpointer=checkpointer)
