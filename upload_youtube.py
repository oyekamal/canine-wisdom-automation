"""
YouTube upload module for Canine Wisdom YouTube Shorts Pipeline.

Handles OAuth2 authentication and uploads final video to YouTube as a Short.
"""

import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import load_config, YOUTUBE_API_SCOPES
from utils import log, retry_with_backoff


# ============================================================================
# PART 1: OAuth2 AUTHENTICATION
# ============================================================================

def get_youtube_service():
    """
    Get authenticated YouTube API service.

    Process:
    1. Check for existing token.json
    2. Load credentials from token.json if valid
    3. If no valid token:
       - Check if client_secrets.json exists
       - Use InstalledAppFlow for OAuth login
       - Save credentials to token.json
    4. Return authenticated YouTube service

    Returns:
        googleapiclient.discovery.Resource: Authenticated YouTube API service.

    Raises:
        FileNotFoundError: If client_secrets.json not found.
    """

    # ========================================================================
    # Step 1: Define Paths
    # ========================================================================

    base_dir = Path(__file__).parent
    token_file = base_dir / "token.json"
    client_secrets_file = base_dir / "client_secrets.json"

    # ========================================================================
    # Step 2: Check for Valid Token
    # ========================================================================

    creds = None

    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(token_file),
                YOUTUBE_API_SCOPES
            )
        except Exception as e:
            log(f"⚠️ Token invalid or expired: {str(e)}", level="warning")
            creds = None

    # ========================================================================
    # Step 3: If Token Valid and Not Expired, Return Service
    # ========================================================================

    if creds and creds.valid:
        log("✅ Using existing YouTube credentials")
        return build("youtube", "v3", credentials=creds)

    # ========================================================================
    # Step 4: Refresh Token if Expired
    # ========================================================================

    if creds and creds.expired and creds.refresh_token:
        log("🔄 Refreshing expired YouTube credentials...")
        try:
            creds.refresh(Request())
            # Save refreshed credentials
            with open(token_file, "w") as f:
                f.write(creds.to_json())
            log("✅ Credentials refreshed and saved")
            return build("youtube", "v3", credentials=creds)
        except Exception as e:
            log(f"⚠️ Failed to refresh credentials: {str(e)}", level="warning")
            creds = None

    # ========================================================================
    # Step 5: OAuth Flow if No Valid Token
    # ========================================================================

    if not creds or not creds.valid:
        # Check if client_secrets.json exists
        if not client_secrets_file.exists():
            raise FileNotFoundError(
                f"client_secrets.json not found at {client_secrets_file}.\n"
                "Get your OAuth2 credentials from Google Cloud Console:\n"
                "1. Go to https://console.cloud.google.com\n"
                "2. Create OAuth 2.0 credentials (Desktop Application)\n"
                "3. Download as JSON and save as client_secrets.json in this directory"
            )

        log("🔐 Initiating YouTube OAuth2 login...")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secrets_file),
            YOUTUBE_API_SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open(token_file, "w") as f:
            f.write(creds.to_json())

        log("✅ OAuth2 credentials saved to token.json")

    # ========================================================================
    # Step 6: Return Authenticated Service
    # ========================================================================

    return build("youtube", "v3", credentials=creds)


def get_analytics_service():
    """
    Get authenticated YouTube Analytics API v2 service.
    Reuses the same OAuth credentials as get_youtube_service().
    """
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from config import YOUTUBE_API_SCOPES

    base_dir = Path(__file__).parent
    token_file = base_dir / "token.json"

    if not token_file.exists():
        raise FileNotFoundError("token.json not found. Run get_youtube_service() first to authenticate.")

    creds = Credentials.from_authorized_user_file(str(token_file), YOUTUBE_API_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    return build("youtubeAnalytics", "v2", credentials=creds)


# ============================================================================
# PART 2: VIDEO UPLOAD
# ============================================================================

def upload_youtube() -> str:
    """
    Upload final video to YouTube as a Short.

    Process:
    1. Load metadata from outputs/metadata.json
    2. Verify outputs/final_video.mp4 exists
    3. Get YouTube service with OAuth2
    4. Build video request with metadata
    5. Upload with resumable support and progress tracking
    6. Extract and return video URL

    Returns:
        str: YouTube Shorts URL (https://youtube.com/shorts/{video_id})

    Raises:
        FileNotFoundError: If metadata.json or final_video.mp4 missing.
        Exception: If upload fails after retries.
    """

    # ========================================================================
    # Step 1: Log Start
    # ========================================================================

    log("📤 Step 4: Uploading to YouTube Shorts...")

    # ========================================================================
    # Step 2: Load Configuration
    # ========================================================================

    cfg = load_config()
    outputs_dir = cfg["outputs_dir"]

    # ========================================================================
    # Step 3: Load Metadata from outputs/metadata.json
    # ========================================================================

    metadata_file = outputs_dir / "metadata.json"
    if not metadata_file.exists():
        raise FileNotFoundError(
            f"Metadata file not found at {metadata_file}. "
            "Run generate_script() first."
        )

    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # ========================================================================
    # Step 4: Verify Final Video Exists
    # ========================================================================

    video_file = outputs_dir / "final_video.mp4"
    if not video_file.exists():
        raise FileNotFoundError(
            f"Final video not found at {video_file}. "
            "Run build_video() first."
        )

    # ========================================================================
    # Step 5: Build Video Description
    # ========================================================================

    script = metadata.get("script", "")
    title = metadata.get("title", "Dog Fact")
    hashtags = metadata.get("hashtags", [])
    hashtags_str = " ".join(f"#{tag}" for tag in hashtags)

    # Load YouTube settings (description template, affiliate links, etc.)
    base_dir = Path(__file__).parent
    youtube_settings_file = base_dir / "youtube_settings.json"

    if youtube_settings_file.exists():
        with open(youtube_settings_file, "r") as f:
            yt_settings = json.load(f)
        # Use template from settings
        description_template = yt_settings.get("description_template", "{video_script}")
        description = description_template.format(
            video_title=title,
            video_script=script,
            hashtags=hashtags_str
        )
    else:
        # Fallback to simple description
        description = f"""{script}

{hashtags_str}

#Shorts #YouTubeShorts"""

    # ========================================================================
    # Step 6: Define Nested do_upload() Function
    # ========================================================================

    def do_upload() -> str:
        """
        Execute the YouTube upload.

        Returns:
            str: YouTube Shorts URL

        Raises:
            Exception: If upload fails.
        """

        # Get authenticated service
        youtube = get_youtube_service()

        # ====================================================================
        # Build Request Body
        # ====================================================================

        body = {
            "snippet": {
                "title": metadata.get("title", "Dog Fact"),
                "description": description,
                "tags": metadata.get("hashtags", []),
                "categoryId": "15"  # Pets & Animals
            },
            "status": {
                "privacyStatus": "public",
                "madeForKids": False
            }
        }

        # ====================================================================
        # Create MediaFileUpload
        # ====================================================================

        media = MediaFileUpload(
            str(video_file),
            mimetype="video/mp4",
            chunksize=10 * 1024 * 1024,  # 10MB chunks
            resumable=True
        )

        # ====================================================================
        # Create Insert Request
        # ====================================================================

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        # ====================================================================
        # Execute Upload with Resumable Support
        # ====================================================================

        response = None
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress_percent = int(status.progress() * 100)
                    log(f"⏳ Upload progress: {progress_percent}%")
            except Exception as e:
                log(f"❌ Upload chunk failed: {str(e)}", level="error")
                raise

        # ====================================================================
        # Extract Video ID and Build URL
        # ====================================================================

        if "id" not in response:
            raise Exception(
                f"No video ID in response: {response}"
            )

        video_id = response["id"]
        video_url = f"https://youtube.com/shorts/{video_id}"

        return video_url

    # ========================================================================
    # Step 7: Call do_upload with Retry Logic
    # ========================================================================

    video_url = retry_with_backoff(
        do_upload,
        max_retries=1,
        step_name="YouTube Upload"
    )

    # ========================================================================
    # Step 8: Log Success and Return URL
    # ========================================================================

    log(f"✅ Short uploaded! 🔗 {video_url}")

    return video_url
