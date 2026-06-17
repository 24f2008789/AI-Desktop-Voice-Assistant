import os
import time
import edge_tts
import pygame
import asyncio
import speech_recognition as sr

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