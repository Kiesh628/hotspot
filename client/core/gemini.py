import base64
import requests
import logging

logger = logging.getLogger("GeminiClient")

PREFERRED_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.6-flash"
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

        last_err = ""
        for model in PREFERRED_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                resp = requests.post(
                    url,
                    headers={
                        "x-goog-api-key": key,
                        "Content-Type": "application/json"
                    },
                    json={"contents": [{"parts": [{"text": "ping"}]}]},
                    timeout=6
                )
                
                err_msg = ""
                try:
                    err_msg = resp.json().get("error", {}).get("message", "").strip()
                except Exception:
                    pass

                if resp.status_code == 200:
                    return True, "API key verified successfully!"
                elif resp.status_code == 402:
                    return False, f"Prepayment credits depleted: {err_msg or 'Please check project billing or create a free key in a new project'}"
                elif resp.status_code in (400, 401):
                    return False, f"Invalid key: {err_msg or 'API key not valid'}"
                elif resp.status_code == 403:
                    return False, f"Permission error: {err_msg or 'Access forbidden or API disabled'}"
                elif resp.status_code in (404, 503, 429):
                    # Model not available, temporarily busy (503 high demand), or rate-limited -> fallback to next model!
                    last_err = err_msg or f"Model {model} returned {resp.status_code}"
                    continue
                else:
                    return False, f"Google API Error ({resp.status_code}): {err_msg or resp.text[:100]}"
            except requests.exceptions.Timeout:
                continue
            except Exception as e:
                last_err = str(e)
                continue

        # If all individual models were busy, check GET /models as final verification
        try:
            url_fallback = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
            resp_fb = requests.get(url_fallback, timeout=5)
            if resp_fb.status_code == 200:
                return True, "API key verified successfully!"
            return False, f"Verification failed ({resp_fb.status_code}): {last_err or 'Check API key'}"
        except Exception as e:
            return False, f"Network error: {e}"

    def ask_screen(self, prompt: str, jpeg_bytes: bytes) -> str:
        """
        Sends the screen image and optional user question to Gemini.
        If prompt is empty, sends a default prompt to analyze the boxed region.
        """
        if not self.api_key:
            return "Error: No Gemini API key provided."

        b64_image = base64.b64encode(jpeg_bytes).decode("utf-8")
        models = PREFERRED_MODELS

        clean_prompt = prompt.strip() if prompt else ""
        prompt_instruction = (
            clean_prompt
            if clean_prompt
            else "Describe what you see in this selected screen region and provide concise, helpful context or solutions."
        )

        parts = [
            {
                "text": (
                    "You are an AI pairing and remote assistant viewing the user's friend's screen. "
                    "Provide clear, concise, actionable advice or answers based on what is visible. "
                    f"\n\nUser request: {prompt_instruction}"
                )
            },
            {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": b64_image
                }
            }
        ]

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
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                resp = requests.post(
                    url,
                    headers={
                        "x-goog-api-key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        item_parts = candidates[0]["content"].get("parts", [])
                        text_parts = [p.get("text", "") for p in item_parts if "text" in p]
                        if text_parts:
                            return "\n".join(text_parts).strip()
                    return "No response text received from Gemini."
                elif resp.status_code in (404, 503, 429):
                    logger.warning(f"Model {model} returned {resp.status_code}, attempting fallback model...")
                    continue
                else:
                    return f"Gemini Error ({resp.status_code}): {resp.text}"
            except Exception as e:
                logger.error(f"Error querying Gemini with model {model}: {e}")
                continue

        return "Failed to communicate with Gemini API. Check network or quota."
