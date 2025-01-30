# deepseek_utils.py

import os
import openai
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Read your credentials from environment variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# DeepSeek's base URL (OpenAI-compatible)
# Official docs say you can use https://api.deepseek.com (or https://api.deepseek.com/v1)
DEEPSEEK_API_BASE = "https://api.deepseek.com"

# Configure openai for DeepSeek
openai.api_key = DEEPSEEK_API_KEY
openai.api_base = DEEPSEEK_API_BASE

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def summarize_text(transcript: str, temperature: float = 0.8) -> str:
    """
    Calls DeepSeek's chat completion endpoint (OpenAI-compatible)
    to summarize the given transcript.
    """
    if not transcript:
        return ""
    
    # Please install OpenAI SDK first: `pip3 install openai`

    

    try:
        # You can customize roles: system, user, or additional instructions as needed.
        # For a straightforward summarization:

        """
         client = OpenAI(api_key=openai.api_key , base_url="https://api.deepseek.com")

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes the given video transcript into the main takeaways and insights."},
                {"role": "user", "content": transcript},
            ],
            stream=False
        )
        
        """
        
        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "developer", "content": "You are a helpful assistant that summarizes the given video transcript into the main takeaways and insights."},
                {"role": "user", "content": transcript},
            ]
        )

       

        # The summary is typically in: response.choices[0].message.content
        summary = response.choices[0].message.content
        return summary

    except Exception as e:
        print(f"Error calling DeepSeek API: {e}")
        return ""
