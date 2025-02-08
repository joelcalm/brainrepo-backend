# main.py
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import stripe

# Local imports
from firebase_config import db
from youtube_utils import extract_playlist_id, get_videos_from_playlist, fetch_transcript
from deepseek_utils import summarize_text
from email_utils import send_summary_email
from stripe_webhook import stripe_webhook_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stripe_webhook_router)

class PlaylistData(BaseModel):
    email: str
    playlistUrl: str
    name: str
    credits: int = 5  # Default credits for new users

@app.get("/")
def root():
    return {"message": "Hello from FastAPI backend!"}

@app.post("/save-playlist")
def save_playlist(data: PlaylistData = Body(...)):
    """
    1. Receive user email, name, and playlist URL.
    2. Store or update in Firestore.
    3. Do NOT process immediately - rely on cron to handle that.
    """
    users_query = (
        db.collection("users")
        .where("email", "==", data.email)
        .limit(1)
        .get()
    )

    if len(users_query) == 0:
        # Create a new document with email, playlistUrl, and name
        new_doc_ref = db.collection("users").document()
        new_doc_ref.set({
            "email": data.email,
            "playlistUrl": data.playlistUrl,
            "name": data.name,  # Save the user's name
            "credits": data.credits  # Save the initial credits
        })
        user_id = new_doc_ref.id
    else:
        # Update the existing document
        user_doc = users_query[0]
        user_id = user_doc.id
        user_doc.reference.update({
            "playlistUrl": data.playlistUrl,
            "name": data.name  # Update the user's name
        })

    return {"message": f"Playlist saved for user {data.email}", "userId": user_id}


@app.get("/run-cron")
def run_cron():
    """
    This endpoint will be hit by a scheduled job (every 30 min, for example).
    It processes all users in Firestore to see if they have new videos.
    """
    result = process_all()
    return result

def process_all():
    """
    Check every user with a playlistUrl for new videos, fetch transcripts,
    generate summaries, and send emails for new items.
    """
    users_ref = db.collection("users")
    all_users = users_ref.stream()

    total_new_videos = 0
    processed_users = 0

    for user_doc in all_users:
        user_data = user_doc.to_dict()
        playlist_url = user_data.get("playlistUrl")
        email = user_data.get("email")

        if playlist_url and email:
            processed_users += 1
            playlist_id = extract_playlist_id(playlist_url)
            if not playlist_id:
                continue

            videos = get_videos_from_playlist(playlist_id)
            for vid in videos:
                video_id = vid["video_id"]
                doc_ref = db.collection("videos").document(video_id)

                if not doc_ref.get().exists:
                    # new video
                    transcript = fetch_transcript(video_id)
                    if not transcript:
                        print(f"No transcript for video {video_id}, skipping.")
                        continue

                    summary = summarize_text(transcript)
                    doc_ref.set({
                        "playlist_id": playlist_id,
                        "title": vid["title"],
                        "description": vid["description"],
                        "transcript": transcript,
                        "summary": summary,
                        "user_id": user_doc.id,
                    })

                    # send email
                    subject = f"New Video Summary: {vid['title']}"
                    send_summary_email(email, subject, summary)

                    if user_data["credits"] > 0:
                        # proceed with summarization
                        new_credits = user_data["credits"] - 1
                        user_doc.reference.update({"credits": new_credits})
                    else:
                        # skip summarization and handle 'no credits' scenario
                        return {"redirect": "https://brainrepo.es/plan"}


                    total_new_videos += 1

    return {
        "message": "Cron job completed",
        "processedUsers": processed_users,
        "totalNewVideos": total_new_videos,
    }

# Set your Stripe secret key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class CheckoutRequest(BaseModel):
    email: str
    planId: str  # e.g., "pro" or "legend"

@app.post("/create-checkout-session")
def create_checkout_session(data: CheckoutRequest):
    """
    1. Receives { email, planId } from the frontend.
    2. Creates a Stripe Checkout Session for the user to pay.
    3. Returns the session URL for redirection.
    """

    # Your plan logic: map planId to the correct line item price or product
    # You said you have 2 product links. Actually, we typically use 'price' IDs from the Stripe Dashboard:
    # e.g., price_12345 for PRO, price_67890 for LEGEND
    # But if you only have 'Buy' links, you can also do it that way. 
    # Let's assume you have price IDs:
    price_map = {
        "pro": "prod_Rjhg6kfBzo1Nnk",   # Replace with your actual price ID from Stripe
        "legend": "prod_RjhhDJDhTzEnHj"
    }

    if data.planId not in price_map:
        raise HTTPException(status_code=400, detail="Invalid planId")

    # Create the session
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_map[data.planId], "quantity": 1}],
            mode="subscription",  # or "payment" if you only want a one-time charge
            success_url="https://your-frontend-domain.com/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://your-frontend-domain.com/plan",
            customer_email=data.email,
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
