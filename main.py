import os
import uvicorn
from fastapi import FastAPI, HTTPException

# Local imports (assuming these files are in the same directory)
from firebase_config import db
from youtube_utils import extract_playlist_id, get_videos_from_playlist, fetch_transcript
from deepseek_utils import summarize_text
from email_utils import send_summary_email

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from FastAPI backend!"}

@app.get("/process-playlist/{user_id}")
def process_playlist(user_id: str):
    """
    Process a single user's playlist:
    1. Load user's document from 'users' collection.
    2. Extract playlistUrl, parse the playlist ID.
    3. Fetch the playlist's videos from YouTube.
    4. For each NEW video, fetch transcript; if transcript is missing, skip it.
       If transcript is found, summarize it, store in 'videos', and email the user.
    """
    user_doc_ref = db.collection("users").document(user_id)
    user_doc = user_doc_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = user_doc.to_dict()
    playlist_url = user_data.get("playlistUrl")
    if not playlist_url:
        raise HTTPException(status_code=400, detail="User has no playlistUrl")

    user_email = user_data.get("email")  # stored at sign-in time
    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id:
        raise HTTPException(status_code=400, detail="Invalid playlist URL")

    videos = get_videos_from_playlist(playlist_id)
    new_videos_count = 0

    for vid in videos:
        video_id = vid["video_id"]
        doc_ref = db.collection("videos").document(video_id)

        if not doc_ref.get().exists:
            # It's a brand-new video
            transcript = fetch_transcript(video_id)
            if not transcript:
                # Log or print a message if needed, then skip this video.
                print(f"No transcript available for video {video_id}. Skipping.")
                continue

            # Proceed only if transcript is available
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
