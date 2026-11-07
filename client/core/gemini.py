import base64
import requests
import logging

logger = logging.getLogger("GeminiClient")

PREFERRED_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

class GeminiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip().strip('"').strip("'") if api_key else ""

    @staticmethod
    def verify_key(api_key: str) -> tuple[bool, str]:
        """
        Validates the provided Gemini API key by probing the generateContent endpoint.
        Returns (is_valid, message).
        """
        key = api_key.strip().strip('"').strip("'") if api_key else ""
        if not key:
            return False, "API key is empty."

        for model in PREFERRED_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            try:
                resp = requests.post(
                    url,
                    json={"contents": [{"parts": [{"text": "ping"}]}]},
                    timeout=5
                )
                if resp.status_code == 200:
                    return True, "API key verified successfully!"
                elif resp.status_code == 402:
                    return False, "Prepayment credits depleted on this project. Create a free API key at aistudio.google.com in a new project."
                elif resp.status_code == 400:
                    err_msg = ""
                    try:
                        err_msg = resp.json().get("error", {}).get("message", "")
                    except Exception:
                        pass
                    return False, f"Invalid key: {err_msg or 'API key not valid'}"
                elif resp.status_code == 403:
                    err_msg = ""
                    try:
                        err_msg = resp.json().get("error", {}).get("message", "")
                    except Exception:
                        pass
                    return False, f"Permission error: {err_msg or 'Access forbidden'}"
                elif resp.status_code == 429:
                    return False, "Rate limit reached. Please retry in a moment."
                elif resp.status_code == 404:
                    # Model not found on this endpoint version, try next model
                    continue
                else:
                    return False, f"Verification returned status {resp.status_code}"
            except requests.exceptions.Timeout:
                return False, "Connection timed out. Check your internet connection."
            except Exception as e:
                return False, f"Network error: {e}"

        # If all preferred models returned 404, fallback to checking GET /models
        try:
            url_fallback = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
            resp_fb = requests.get(url_fallback, timeout=5)
            if resp_fb.status_code == 200:
                return True, "API key verified successfully!"
            return False, f"Verification failed with status {resp_fb.status_code}"
        except Exception as e:
            return False, f"Network error: {e}"

    def ask_screen(self, prompt: str, jpeg_bytes: bytes) -> str:
        """
        Sends the screen image and optional user question to Gemini.
        If prompt is empty, sends the image alone.
        """
        if not self.api_key:
            return "Error: No Gemini API key provided."

        b64_image = base64.b64encode(jpeg_bytes).decode("utf-8")
        models = PREFERRED_MODELS

        parts = []
        clean_prompt = prompt.strip() if prompt else ""
        if clean_prompt:
            parts.append({
                "text": (
                    "You are an AI pairing and remote assistant viewing the user's friend's screen. "
                    "Provide clear, concise, actionable advice or answers based on what is visible. "
                    f"\n\nQuestion from user: {clean_prompt}"
                )
            })

        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": b64_image
            }
        })

        payload = {
            "contents": [
                {
                    "parts": parts
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 1024
            }
        }

        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                resp = requests.post(url, json=payload, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        item_parts = candidates[0]["content"].get("parts", [])
                        if item_parts and "text" in item_parts[0]:
                            return item_parts[0]["text"].strip()
                    return "No response text received from Gemini."
                elif resp.status_code == 404:
                    continue
                else:
                    return f"Gemini Error ({resp.status_code}): {resp.text}"
            except Exception as e:
                logger.error(f"Error querying Gemini with model {model}: {e}")
                continue

        return "Failed to communicate with Gemini API. Check network or quota."
