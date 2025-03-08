# transcripts_api.py
from fastapi import FastAPI, HTTPException
from youtube_utils import fetch_transcript  # This is your existing function from youtube_utils.py
import uvicorn

app = FastAPI()

@app.get("/transcript/{video_id}")
async def get_transcript(video_id: str):
    transcript = fetch_transcript(video_id)
    if transcript:
        return {"video_id": video_id, "transcript": transcript}
    else:
        raise HTTPException(status_code=404, detail="Transcript not found 2")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
