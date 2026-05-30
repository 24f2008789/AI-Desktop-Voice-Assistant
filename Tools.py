import webbrowser
import requests
import pywhatkit
import urllib.parse
from langchain_core.tools import tool
from langgraph.types import interrupt
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from playwright.sync_api import sync_playwright
from pywinauto.application import Application
import pyautogui
import time
from pywinauto.keyboard import send_keys
from gmail import gmail_auth
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64


@tool
def open_website(url:str) -> str:
    """Open any website or URL in the default web browser"""

    webbrowser.open(url)

    return "f{url} opened successfully"

@tool
def play_youtube(video_name:str):
    """
    Search YouTube and play top matching video.
    Use this when user asks to play songs, music, videos, or YouTube content.
    """

    pywhatkit.playonyt(video_name)

    return f"Playing {video_name} on YouTube"

@tool
def get_tool_price(symbol:str) -> dict:
    """
    Fetch latest stock price for a given symbol(ex : 'AAPL','TSLA')
    using this alphavantage url given below    
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=NAHN06HJFDMEH5AW"
    r = requests.get(url)
    return r.json()



@tool
def send_whatsapp_message(contact: str, message: str) -> str:
    """
    Send WhatsApp message using WhatsApp Desktop app.

    Use when user asks:
    - send whatsapp message
    - text someone
    - message someone
    """

    decision = interrupt({
        "question": f'Should the message "{message}" be sent to "{contact}"?'
    })
    
    if decision["approved"]:
        if decision["approved"] == "yes":
            try:

                # CONNECT TO WHATSAPP
                app = Application(backend="uia").connect(
                    title="WhatsApp"
                )

                # GET WINDOW
                window = app.window(title="WhatsApp")

                window.wait("visible", timeout=20)

                window.set_focus()

                print("WhatsApp connected")

                # SEARCH BOX
                search_box = window.child_window(
                    control_type="Edit",
                    found_index=0
                )

                search_box.click_input()

                # CLEAR OLD TEXT
                search_box.type_keys("^a{BACKSPACE}")

                # TYPE CONTACT
                search_box.type_keys(contact, with_spaces=True)

                time.sleep(1)

                # OPEN CHAT
                send_keys("{ENTER}")

                print(f"{contact} chat opened")

                time.sleep(1)

                # MESSAGE BOX
                pyautogui.write(message, interval=0.03)
                time.sleep(1)

                pyautogui.press("enter")

                return {
                    "status": "success",
                    "message": f"Message sent to {contact}",
                    "contact": contact,
                    "message_text": message
                }

            except Exception as e:

                print("ERROR:", e)

                return {
                    "status": "failed",
                    "message": str(e)
                }

        else:
            return {
                "status": "cancelled",
                "message": f"Message was not sent to {contact}"
            }
    else:
        return {
                "status": "cancelled",
                "message": f"The voice was not clear please say again"
            }
    
################################ GMAIL TOOLS #####################################

@tool
def check_unread_emails():

    """
    Check unread Gmail emails.
    """

    creds = gmail_auth()

    service = build(
        'gmail',
        'v1',
        credentials=creds
    )

    # Fetch unread emails
    results = service.users().messages().list(
        userId='me',
        q='is:unread',
        maxResults=10
    ).execute()

    messages = results.get('messages', [])

    if not messages:

        return {
            "status": "success",
            "message": "No unread emails found."
        }

    email_list = []

    for msg in messages:

        txt = service.users().messages().get(
            userId='me',
            id=msg['id']
        ).execute()

        headers = txt['payload']['headers']

        subject = ""
        sender = ""

        for header in headers:

            if header['name'] == 'Subject':
                subject = header['value']

            if header['name'] == 'From':
                sender = header['value']

        email_list.append({
            "sender": sender,
            "subject": subject
        })

    return {
        "status": "success",
        "total_unread": len(email_list),
        "emails": email_list
    }


@tool
def read_email_by_sender(sender_name: str):

    """
    Read latest email from a specific sender.
    """

    creds = gmail_auth()

    service = build(
        'gmail',
        'v1',
        credentials=creds
    )

    results = service.users().messages().list(
        userId='me',
        q=f'from:{sender_name}',
        maxResults=1
    ).execute()

    messages = results.get('messages', [])

    if not messages:

        return {
            "status": "failed",
            "message": f"No email found from {sender_name}"
        }

    msg = messages[0]

    txt = service.users().messages().get(
        userId='me',
        id=msg['id']
    ).execute()

    headers = txt['payload']['headers']

    subject = ""
    sender = ""

    for header in headers:

        if header['name'] == 'Subject':
            subject = header['value']

        if header['name'] == 'From':
            sender = header['value']

    return {
        "status": "success",
        "sender": sender,
        "subject": subject,
        "snippet": txt.get("snippet", "")
    }


@tool
def send_professional_email(receiver_name: str,sender_name:str,receiver_email: str,subject: str,message: str) -> dict:
    """
    Send a professional email using Gmail.

    Use when user asks:
    - send email
    - write professional email
    - mail someone
    - send internship/job/project email
    """

    # -----------------------------
    # HUMAN CONFIRMATION
    # -----------------------------
    decision = interrupt({
        "question": (
            f"Do you want to send this email?\n\n"
            f"Receiver Name: {receiver_name}\n"
            f"Receiver Email: {receiver_email}\n"
            f"Subject: {subject}\n"
            f"Message: {message}\n"
        )
    })

    # -----------------------------
    # CHECK APPROVAL
    # -----------------------------
    if decision["approved"]:
        if decision["approved"] == "yes":
            try:

                # -----------------------------
                # AUTHENTICATION
                # -----------------------------
                creds = gmail_auth()

                service = build(
                    "gmail",
                    "v1",
                    credentials=creds
                )

                # -----------------------------
                # CREATE PROFESSIONAL EMAIL
                # -----------------------------
                email_text = f"""
                    Dear {receiver_name},

                    {message}

                    Best Regards,
                    {sender_name}
                    """

                # -----------------------------
                # MIME MESSAGE
                # -----------------------------
                mime_message = MIMEText(email_text)

                mime_message["to"] = receiver_email
                mime_message["subject"] = subject

                # Encode email
                raw_message = base64.urlsafe_b64encode(
                    mime_message.as_bytes()
                ).decode()

                # -----------------------------
                # SEND EMAIL
                # -----------------------------
                send_message = service.users().messages().send(
                    userId="me",
                    body={
                        "raw": raw_message
                    }
                ).execute()

                return {
                    "status": "success",
                    "message": f"Email sent successfully to {receiver_name}",
                    "email": receiver_email,
                    "subject": subject,
                    "gmail_id": send_message["id"]
                }

            except Exception as e:

                return {
                    "status": "failed",
                    "error": str(e)
                }
        else:
            return {
                "status": "cancelled",
                "message": "Email sending cancelled by user."
            }
    else:
        return {
                "status": "cancelled",
                "message": "Email sending cancel due to some technical issue."
            }
    
search_tool = DuckDuckGoSearchRun(region='us-en')

wiki = WikipediaQueryRun(
    api_wrapper=WikipediaAPIWrapper()
)
