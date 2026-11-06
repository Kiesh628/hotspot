import base64
import requests
import logging

logger = logging.getLogger("GeminiClient")

class GeminiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip() if api_key else ""

    @staticmethod
    def verify_key(api_key: str) -> tuple[bool, str]:
        """
        Validates the provided Gemini API key by calling the models endpoint.
        Returns (is_valid, message).
        """
        key = api_key.strip()
        if not key:
            return False, "API key is empty."
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
            resp = requests.get(url, timeout=6)
            if resp.status_code == 200:
                return True, "API key verified successfully!"
            elif resp.status_code == 400 or resp.status_code == 403:
                return False, "Invalid API key or insufficient permissions."
            else:
                return False, f"Verification returned status {resp.status_code}"
        except Exception as e:
            return False, f"Network error during verification: {e}"

    def ask_screen(self, prompt: str, jpeg_bytes: bytes) -> str:
        """
        Sends the current screen image and the user's question to Gemini 2.0 Flash.
        """
        if not self.api_key:
            return "Error: No Gemini API key provided."

        b64_image = base64.b64encode(jpeg_bytes).decode("utf-8")
        models = ["gemini-2.0-flash", "gemini-1.5-flash"]

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are an AI pairing and remote assistant viewing the user's friend's screen. "
                                "Provide clear, concise, actionable advice or answers based on what is visible. "
                                f"\n\nQuestion from user: {prompt.strip()}"
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64_image
                            }
                        }
                    ]
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
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                    return "No response text received from Gemini."
                elif resp.status_code == 404:
                    continue # Try next model fallback
                else:
                    return f"Gemini Error ({resp.status_code}): {resp.text}"
            except Exception as e:
                logger.error(f"Error querying Gemini with model {model}: {e}")
                continue

        return "Failed to communicate with Gemini API. Check network or quota."
