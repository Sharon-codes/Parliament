import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow

load_dotenv()
flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
                "project_id": "saathi",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=["openid", "https://www.googleapis.com/auth/userinfo.email"],
)
flow.redirect_uri = f"{os.getenv('PUBLIC_API_URL')}/api/workspace/callback"
url, state = flow.authorization_url(access_type="offline", prompt="consent")
print(url)
