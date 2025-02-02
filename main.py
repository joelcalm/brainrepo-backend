import os
import uvicorn
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

# Local imports (assuming these files are in the same directory)
from firebase_config import db
from youtube_utils import extract_playlist_id, get_videos_from_playlist, fetch_transcript
from deepseek_utils import summarize_text
from email_utils import send_summary_email
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Or ["*"] if you're just testing
    allow_credentials=True,
    allow_methods=["*"],  # Or ["GET", "POST", "OPTIONS"] specifically
    allow_headers=["*"],  # Or list specific headers
)

class PlaylistData(BaseModel):
    email: str
    playlistUrl: str

@app.get("/")
def root():
    return {"message": "Hello from FastAPI backend!"}

@app.post("/set-playlist")
def set_playlist(data: PlaylistData = Body(...)):
    """
    1. Receive user email + playlist URL in the POST body.
    2. Store/update the playlistUrl in Firestore for this user.
    3. Call process_playlist (the logic is the same as the route below).
    4. Return a response with the summary of how many new videos were processed.
    """

    # 1. Check if user exists, otherwise create one. Alternatively, you can require the user to exist already.
    #    This example "upserts" the user doc (create if not found; update if found).
    users_query = db.collection("users").where("email", "==", data.email).limit(1).get()
    if len(users_query) == 0:
        # Create a new user doc
        new_doc_ref = db.collection("users").document()
        new_doc_ref.set({
            "email": data.email,
            "playlistUrl": data.playlistUrl
        })
        user_id = new_doc_ref.id
    else:
        # Update existing user doc
        user_doc = users_query[0]
        user_id = user_doc.id
        user_doc.reference.update({"playlistUrl": data.playlistUrl})

    # 2. Call the same logic to process the playlist
    result = process_playlist_internal(user_id)
    return {"message": f"Playlist set and processed for {data.email}", **result}

def process_playlist_internal(user_id: str):
    """
    Internal function (not a route) to process the user's playlist.
    """
    user_doc_ref = db.collection("users").document(user_id)
    user_doc = user_doc_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = user_doc.to_dict()
    playlist_url = user_data.get("playlistUrl")
    if not playlist_url:
        raise HTTPException(status_code=400, detail="User has no playlistUrl")

    user_email = user_data.get("email")
    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id:
        raise HTTPException(status_code=400, detail="Invalid playlist URL")

    videos = get_videos_from_playlist(playlist_id)
    new_videos_count = 0

    for vid in videos:
        video_id = vid["video_id"]
        doc_ref = db.collection("videos").document(video_id)

        if not doc_ref.get().exists:
            # Brand-new video
            transcript = fetch_transcript(video_id)
            if not transcript:
                print(f"No transcript available for video {video_id}. Skipping.")
                continue

            summary = summarize_text(transcript)

            # Store in Firestore
            doc_ref.set({
                "playlist_id": playlist_id,
                "title": vid["title"],
                "description": vid["description"],
                "transcript": transcript,
                "summary": summary,
                "user_id": user_id
            })

            # Send email if we have the user's email
            if user_email:
                subject = f"New Video Summary: {vid['title']}"
                send_summary_email(user_email, subject, summary)

            new_videos_count += 1

    return {
        "message": f"Processed playlist for user {user_id}",
        "newVideosFound": new_videos_count
    }

@app.get("/process-playlist/{user_id}")
def process_playlist(user_id: str):
    """
    If you still want a direct GET endpoint for testing or debugging, you can keep this.
    """
    return process_playlist_internal(user_id)

@app.get("/process-all-users")
def process_all_users():
    """
    Process all users in the 'users' collection who have a 'playlistUrl'.
    Ideal for a cron job so new videos get summarized & emailed automatically.
    """
    users_ref = db.collection("users")
    users = users_ref.stream()

    total_new_videos = 0
    processed_users = 0

    for user_doc in users:
        user_data = user_doc.to_dict()
        user_id = user_doc.id
        playlist_url = user_data.get("playlistUrl")
        email = user_data.get("email")

        if playlist_url:
            processed_users += 1
            playlist_id = extract_playlist_id(playlist_url)
            if not playlist_id:
                continue

            videos = get_videos_from_playlist(playlist_id)
            for vid in videos:
                video_id = vid["video_id"]
                doc_ref = db.collection("videos").document(video_id)

                if not doc_ref.get().exists:
                    transcript = fetch_transcript(video_id)
                    if not transcript:
                        print(f"No transcript available for video {video_id}. Skipping.")
                        continue

                    summary = summarize_text(transcript)

                    doc_ref.set({
                        "playlist_id": playlist_id,
                        "title": vid["title"],
                        "description": vid["description"],
                        "transcript": transcript,
                        "summary": summary,
                        "user_id": user_id
                    })

                    # Email user about new video
                    if email:
                        subject = f"New Video Summary: {vid['title']}"
                        send_summary_email(email, subject, summary)

                    total_new_videos += 1

    return {
        "message": "Processed playlists for all users",
        "processedUsers": processed_users,
        "totalNewVideos": total_new_videos
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
