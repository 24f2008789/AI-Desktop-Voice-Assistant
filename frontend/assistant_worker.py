import asyncio
import re

from PySide6.QtCore import QThread
from voice import listen, speak
from PySide6.QtCore import QThread, Signal

from langchain_core.messages import BaseMessage,HumanMessage, AIMessage,SystemMessage
from langgraph.types import Command
from graph import chatbot

def clean_response(text: str) -> str:
    """
    Remove MEMORY: lines and NONE artifacts the LLM leaks into responses.
    """
    if not text:
        return ""

    # Remove standalone NONE (whole word, with optional whitespace)
    text = re.sub(r'(?<!\w)NONE(?!\w)', '', text)

    # Remove MEMORY: <anything> lines
    text = re.sub(r'MEMORY:.*?(\n|$)', '', text, flags=re.IGNORECASE)

    # Clean up extra whitespace/newlines left behind
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text

class AssistantWorker(QThread):
    
    stopped = Signal()
    message_received = Signal(str,str)
    message_chunk = Signal(str)
    message_started = Signal()
    approval_request = Signal(dict)
    avatar_text = Signal(str)
    

    def __init__(self):
        super().__init__()
        self.approval_result = None
        self.running = True
    
    def set_thread(self, thread_id: str):
        """Switch to a different thread."""
        self.thread_id = thread_id

    def run(self):
        asyncio.run(speak("Hello,My name is Sierra, Mai aapki kya help kar sakti hu "))
        print("Assistant Started")
        while self.running:
            config = {"configurable" : {"thread_id" : self.thread_id}}
            user_text = listen()

            if not user_text:
                continue

            if "exit" in user_text.lower():
                print("EXIT DETECTED")
                self.stop()
                break

            self.message_received.emit("user", user_text)
            self.message_started.emit()

            full_response = ""
            for message_chunk, metadata in chatbot.stream(
                {"messages": [HumanMessage(content=user_text)]},
                config=config,
                stream_mode="messages"
            ):
                node = metadata.get("langgraph_node")

                # ← Accept both chat_node (simple) and completion (complex)
                if node not in ("chat_node", "completion"):
                    continue
                if not isinstance(message_chunk, AIMessage):
                    continue
                if not message_chunk.content:
                    continue
                if getattr(message_chunk, "tool_calls", None):
                    continue

                full_response += message_chunk.content
                self.message_chunk.emit(message_chunk.content)

            # After streaming — send full response to avatar
            clean_message = clean_response(full_response)
            if clean_message:
                self.avatar_text.emit(full_response)
            
            snap_shot = chatbot.get_state(config)
            if snap_shot.interrupts:
                interrupt_data = snap_shot.interrupts[0].value
                print("INTERRUPT FOUND")
                print(interrupt_data)
                self.approval_request.emit(interrupt_data)
                while self.approval_result is None:
                    self.msleep(100)

                chatbot.invoke(
                    Command(
                        resume={
                            "approved": self.approval_result
                        }
                    ),
                    config=config
                )

                continue
            asyncio.run(speak(clean_message))


    def stop(self):
        print("STOP CAlled")
        self.running = False
        self.stopped.emit()