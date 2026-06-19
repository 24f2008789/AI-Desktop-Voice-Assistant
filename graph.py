import os
import asyncio
import sqlite3

from Tools import *
from dotenv import load_dotenv
from typing import TypedDict,Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage,HumanMessage, AIMessage,SystemMessage,ToolMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.sqlite import SqliteSaver
from memory_store import save_memory, retrieve_memories,retrieve_pdf_context,list_loaded_pdfs

from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START ,END
from langgraph.prebuilt import ToolNode, tools_condition


load_dotenv()
hf_token = os.getenv("HUGGINGFACEHUB_ACCESS_TOKEN")

tools = [open_website,play_youtube,pause_media,play_media,search_tool,wiki,get_tool_price,
        send_whatsapp_message,check_unread_emails,read_email_by_sender,send_professional_email,
        brightness_up,brightness_down,volume_up,volume_down,find_files_from_file_manager,load_pdf_to_rag_tool,
        retrieve_from_rag_tool]

tool_registry = {
    tool.name: tool
    for tool in tools
}

model = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
)
classifier_model = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0
)
llm_tool = model.bind_tools(tools)


class ClassState(TypedDict):
    messages: Annotated[list[BaseMessage],add_messages]

    task_type: str

    plan: list[dict]

    observations: list

    current_step: int

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
        pdf_context = ""
        if list_loaded_pdfs():
            pdf_context = retrieve_pdf_context(user_query)
        if pdf_context:
            system_pdf = SystemMessage(
            content=f"""
            Use the following PDF information if it helps answer the user's question.

            PDF Context:

            {pdf_context}
            """)
        
        system_memory = SystemMessage(content=f"""
                Below given information is just your knowledge purpose, 
                use it when required but don't need to share it with 
                user unless user ask for it or it's relevant to the conversation.
                                      
                {memory_context}
                """
            )
        recent_history = state["messages"][-8:]
        if pdf_context:
            messages = [system_personna, system_memory, system_pdf] + recent_history
        else:
            messages = [system_personna, system_memory] + recent_history

        resp = llm_tool.invoke(messages)
        print(resp)
        print("TOOL CALLS:", resp.tool_calls)
        memory = extract_memory(user_query)

        if memory != "NONE":
            save_memory(memory)
            
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
    - find the pdf file from local file explorer and upload it to RAG fro further question answer

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
    print("-------------------------planner_node----------------")
    query = ""

    # Find latest human message
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    prompt = f"""
    User Request:
    You are an AI planner.

    You have access to tools.

    Create a numbered step-by-step plan.

    Rules:
    - Assume tools can perform actions.
    - Never say "I am a text based AI".
    - Never say "I cannot do this".
    - Break the task into executable steps.
    - Keep steps short.

    User Request:
    {query}

    Return only the plan.
    """

    resp = model.invoke(prompt)

    print("PLAN:" , resp.content)

    return {
        "plan": resp.content,
        "current_step": 0
    }

MAX_EXECUTOR_ITERATIONS = 3  # hard cap to prevent infinite loops

def executor_node(state):
    print("-------------------------executor_node----------------")

    # Hard cap on iterations
    iterations = state.get("current_step", 0)
    if iterations >= MAX_EXECUTOR_ITERATIONS:
        print(f"[Executor] Hit max iterations ({MAX_EXECUTOR_ITERATIONS}), stopping")
        return {
            "messages": [AIMessage(content="I completed all the steps I could.")],
            "task_completed": True
        }

    query = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    observations = state.get("observations", [])
    plan = state.get("plan", "")

    # Build observations summary for context
    obs_summary = ""
    for i, obs in enumerate(observations):
        result = obs.get("tool_result", "")
        obs_summary += f"\nStep {i+1} result: {result[:300]}\n"

    system_msg = SystemMessage(content=f"""
        You are an execution agent completing a user's task step by step.

        USER GOAL: {query}

        PLAN:
        {plan}

        COMPLETED STEPS ({len(observations)} done so far):
        {obs_summary if obs_summary else "None yet"}

        YOUR JOB NOW:
        - Look at what steps are already done (see observations above)
        - Find the NEXT step that is NOT yet done
        - Execute ONLY that one step using the correct tool
        - If web search results already exist in observations, DO NOT search again — use those results
        - If ALL steps are done, say so in plain text without calling any tool

        TOOLS AVAILABLE: {list(tool_registry.keys())}

        STRICT RULES:
        - Call at most ONE tool per response
        - Never repeat a tool call that already has a result in observations
        - Never write tool names as text — use actual tool calls
        - If search results exist, use them to proceed to the next step (e.g., play YouTube)
        """)

    try:
        resp = llm_tool.invoke([system_msg])
    except Exception as e:
        print("Tool Calling Error:", e)
        return {
            "messages": [AIMessage(content="I had trouble with that step, moving on.")],
        }

    print("complex_Tool_Calling", resp.tool_calls)
    print("Executor response:", resp.content)
    return {"messages": [resp]}

def executor_router(state: ClassState):
    print("executor_router reached")
    last_message = state["messages"][-1]

    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "completion"


def completion_router(state):
    if state.get("task_completed", False):
        return "completion"
    return "executor_agent"

def observation_node(state):
    last_message = state["messages"][-1]

    if isinstance(last_message, ToolMessage):
        observation = {"tool_result": last_message.content}
    else:
        observation = {"tool_result": str(last_message.content)}

    print("OBSERVATION:", observation["tool_result"][:200])

    old = state.get("observations", [])
    return {
        "observations": old + [observation],
        "current_step": state.get("current_step", 0) + 1
    }


def completion_checker(state):
    """
    Stop if:
    - executor returned no tool calls (it decided it's done)
    - OR we hit the max iteration cap
    """
    last_message = state["messages"][-1]
    iterations = state.get("current_step", 0)

    # If last message has no tool calls → executor decided it's done
    has_tool_calls = bool(getattr(last_message, "tool_calls", None))
    hit_cap = iterations >= MAX_EXECUTOR_ITERATIONS

    # Also stop if last message is a plain text answer (not a tool call)
    is_final_answer = (
        isinstance(last_message, AIMessage)
        and last_message.content
        and not has_tool_calls
    )

    completed = is_final_answer or hit_cap

    print(f"[completion_checker] step={iterations}, tool_calls={has_tool_calls}, "
          f"is_final={is_final_answer}, hit_cap={hit_cap} → completed={completed}")

    return {"task_completed": completed}

def completion_node(state):
    query = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    observations = state.get("observations", [])

    # Build a readable summary of what was done
    obs_text = "\n".join([
        f"Step {i+1}: {o.get('tool_result','')[:400]}"
        for i, o in enumerate(observations)
    ])

    prompt = f"""
        User Goal: {query}

        What was accomplished:
        {obs_text}

        Write a short, natural conversational response telling the user what was done.
        Keep it brief and friendly. Reply in the same language as the user.
        Do NOT write MEMORY: or NONE in your response.
        """
    resp = model.invoke(prompt)
    print("FINAL ANSWER:", resp.content)
    return {
        "messages": [resp],
        "final_answer": resp.content
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
graph.add_node("observation",observation_node)
graph.add_node("completion_checker",completion_checker)
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

def load_thread_messages(thread_id: str):
    """
    Return all messages stored for a given thread_id.
    """

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    state = chatbot.get_state(config)

    if state.values is None:
        return []

    return state.values.get("messages", [])

def delete_thread_from_database(thread_id: str):
    """Delete all checkpoints and writes for a thread."""
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM checkpoints WHERE thread_id=?", (thread_id,)
        )
        # Also delete from checkpoint_writes if it exists
        try:
            cursor.execute(
                "DELETE FROM checkpoint_writes WHERE thread_id=?", (thread_id,)
            )
        except Exception:
            pass  # table may not exist
        conn.commit()
    finally:
        conn.close()

def get_all_thread_ids():
    """Return unique thread IDs ordered by most recent."""
    conn = sqlite3.connect("chatbot.db")
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT thread_id
            FROM checkpoints
            ORDER BY rowid DESC
        """)
        rows = cur.fetchall()
        return [row[0] for row in rows]  # ← return strings not tuples
    finally:
        conn.close()