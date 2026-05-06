import base64
import io
import requests
from PIL import Image

# Updated after Railway deployment
RAILWAY_URL = "https://methbillingdashboard-production.up.railway.app"

_TIMEOUT = 15  # seconds


def check_server() -> bool:
    try:
        r = requests.get(f"{RAILWAY_URL}/health", timeout=5)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def analyse(image: Image.Image, plan: str, context: str = "main") -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    payload = {"image_b64": image_b64, "plan": plan, "context": context}
    r = requests.post(f"{RAILWAY_URL}/analyse", json=payload, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["token"]
