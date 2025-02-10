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

#OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def summarize_text(transcript: str, temperature: float = 0.8) -> str:
    """
    Calls DeepSeek's chat completion endpoint (OpenAI-compatible)
    to summarize the given transcript into HTML.
    The response contains two sections:
      - Main Takeaways & Insights
      - Detailed Summary of the Transcript

    The output is a direct summary (no meta-language about "in this video...").
    """
    if not transcript:
        return ""


    try:
        # Initialize the client (DeepSeek usage)
        client = OpenAI(
            api_key=openai.api_key,
            base_url=openai.api_base
        )

        # Prompt with specific instructions to ensure HTML format & structure
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that summarizes the provided transcript into a clear, standalone summary "
                    "in valid HTML format. Your summary should have two sections: "
                    "1) <h2>Main Takeaways & Insights</h2> with bullet points or short numbered items, "
                    "2) <h2>Detailed Summary</h2> in paragraphs. "
                    "The summary must not contain meta statements like 'In this video...' or 'This transcript says...'. "
                    "Instead, present the information directly as if writing an article. "
                    "Output only the summary HTML, without disclaimers or extraneous commentary."
                )
            },
            {
                "role": "user",
                "content": (
                    f"{transcript}\n\n"
                    "Please provide the final summary in valid HTML with the requested sections."
                )
            }
        ]

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=temperature,
            stream=False
        )

        # Extract the content
        summary_html = response.choices[0].message.content
        return summary_html

    except Exception as e:
        print(f"Error calling DeepSeek API: {e}")
        return ""



"""
    client = OpenAI(api_key=OPENAI_API_KEY)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "developer", "content": "You are a helpful assistant that summarizes the given video transcript into the main takeaways and insights."},
        {"role": "user", "content": transcript},
    ]
)

"""