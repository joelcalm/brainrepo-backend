# backend/youtube_utils.py
import os
from googleapiclient.discovery import build
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
import urllib.parse as urlparse

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")

def extract_playlist_id(playlist_url: str) -> str:
    """Get the 'list' param from the YouTube playlist URL."""
    parsed_url = urlparse.urlparse(playlist_url)
    query = urlparse.parse_qs(parsed_url.query)
    return query.get("list", [None])[0]

def get_videos_from_playlist(playlist_id: str):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    videos = []
    next_page_token = None

    while True:
        response = youtube.playlistItems().list(
            part="contentDetails,snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in response["items"]:
            video_id = item["contentDetails"]["videoId"]
            title = item["snippet"]["title"]
            description = item["snippet"]["description"]
            videos.append({
                "video_id": video_id,
                "title": title,
                "description": description
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos

def fetch_transcript(video_id: str):
    """Attempt to fetch the English transcript."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'es']) #first tries to get english transcript, if not available, gets spanish
        return " ".join([entry['text'] for entry in transcript_list])
    except Exception:
        return None
