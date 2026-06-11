import os
import time
import edge_tts
import pygame
import asyncio
import speech_recognition as sr

from dotenv import load_dotenv
from typing import TypedDict,Annotated
from Tools import *
from graph import *

from langgraph.types import Command
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START ,END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_huggingface import HuggingFaceEmbeddings, HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import BaseMessage,HumanMessage, AIMessage,SystemMessage
from langchain_groq import ChatGroq
import threading


def listen():
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("Speak something...")
        recognizer.pause_threshold = 1
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    # Mic is now released here ✅

    try:
        text = recognizer.recognize_google(audio)
        print("You:", text)
        return text
    except:
        print("Could not understand audio")
        asyncio.run(speak("Sorry, I did not understand"))
        return None
    

async def speak(text):

    try:

        if not text.strip():
            return

        filename = f"voice_{int(time.time())}.mp3"

        communicate = edge_tts.Communicate(
            text=text,
            voice="hi-IN-SwaraNeural",
            rate='+30%',
            pitch='+10Hz'
        )

        await communicate.save(filename)

        await asyncio.sleep(0.5)

        pygame.mixer.init()

        pygame.mixer.music.load(filename)

        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)

        pygame.mixer.music.stop()

        pygame.mixer.quit()

        os.remove(filename)

    except Exception as e:
        print("Speech Error:", e)


def main():
    thread_id = "thread-1"
    asyncio.run(speak("Hello ,My name is Sierra, Mai aapki kya help kar sakti hu "))
    config = {"configurable" : {"thread_id" : thread_id}}
    while True:
        user_text = listen()

        if not user_text:
            continue

        if "exit" in user_text.lower():
            break

        state = chatbot.invoke({"messages" : [HumanMessage(content=user_text)]}, config=config)

        interrupts = state.get("__interrupt__", [])


        if interrupts:
            print("INTERRUPTS:", interrupts)

            interrupt_value = interrupts[0].value

            print("Interrupt Value:", interrupt_value)

            asyncio.run(speak(interrupt_value['question']))

            # decision = input("Approve? yes/no : ").strip().lower()
            decision = input("Approve by saying yes or reject it by saying no... : ")

            chatbot.invoke(
                Command(resume={
                    "approved": decision
                }),config=config
            )
            continue

if __name__ == "__main__":
    main()