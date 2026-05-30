import os
import asyncio
from dotenv import load_dotenv
from typing import TypedDict,Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage,HumanMessage, AIMessage,SystemMessage
from langchain_groq import ChatGroq
from Tools import *
from main import speak

from langgraph.types import Command
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START ,END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode, tools_condition


load_dotenv()
hf_token = os.getenv("HUGGINGFACEHUB_ACCESS_TOKEN")

tools = [open_website,play_youtube,search_tool,wiki,get_tool_price,send_whatsapp_message,check_unread_emails,read_email_by_sender,send_professional_email]
model = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.5
)
llm_tool = model.bind_tools(tools)

class ClassState(TypedDict):
    messages: Annotated[list[BaseMessage],add_messages]
    user_input: str
    ai_reponse: str


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
            "ai_reponse": ai_text,
            "messages": [resp]
        }
    except Exception as e:
        print("ERROR:", str(e))
        return {
            "ai_reponse" : "Sorry bro tool execution failed. please try again",
            "messages" : [AIMessage(content="Sorry bro tool execution failed.please try again")]
        }

checkpointer = InMemorySaver()

graph = StateGraph(ClassState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools",tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node",tools_condition)
graph.add_edge("tools", "chat_node")

chatbot = graph.compile(checkpointer=checkpointer)