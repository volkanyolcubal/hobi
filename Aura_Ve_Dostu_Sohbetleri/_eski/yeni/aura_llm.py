"""
AURA-V — LLM Modülü
Ollama (lokal), Gemini, Groq, Danışma Kurulu
"""
import requests, threading

OLLAMA_URL = "http://localhost:11434/api/generate"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"

DANISMA_TETIKLEYICI = [
    "araştır","emin misin","doğrula","karşılaştır",
    "kanıtla","gerçek mi","doğru mu","farklı görüş",
    "research","verify","confirm","compare","son gelişme","güncel haber"
]

def danisma_gerekli_mi(komut: str) -> bool:
    """Danışma kurulu tetikleyici var mı?"""
    k = komut.lower()
    if k.startswith("/danış") or k.startswith("/danis"):
        return True
    return any(t in k for t in DANISMA_TETIKLEYICI)

def llm_local(prompt: str, model: str, options: dict = None) -> str:
    """Yerel Ollama modeli."""
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": model, "prompt": prompt, "stream": False,
            "options": options or {"temperature": 0.8, "num_predict": 500}
        }, timeout=None)
        return r.json().get("response","...").strip()
    except Exception as e:
        return f"Ollama hatası: {e}"

def llm_gemini(prompt: str, sistem: str, api_key: str) -> str:
    """Google Gemini 1.5 Flash API."""
    try:
        payload = {
            "system_instruction": {"parts": [{"text": sistem}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.8, "maxOutputTokens": 1000}
        }
        r = requests.post(
            GEMINI_URL + f"?key={api_key}",
            json=payload, timeout=30,
            headers={"Content-Type": "application/json"}
        )
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"Gemini hatası: {e}"

def llm_groq(mesajlar: list, sistem: str, api_key: str, model: str) -> str:
    """Groq — Llama 3.3 70B."""
    try:
        payload = {
            "model": model,
            "messages": [{"role":"system","content":sistem}] + mesajlar,
            "temperature": 0.8, "max_tokens": 1000
        }
        r = requests.post(GROQ_URL, json=payload, timeout=30,
                          headers={"Authorization": f"Bearer {api_key}",
                                   "Content-Type": "application/json"})
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Groq hatası: {e}"

def aura_danisma_kurulu(komut: str, aura_cevap: str,
                        sistem: str, internet_ctx: str,
                        gemini_key: str, groq_key: str, groq_model: str) -> str:
    """AURA + Gemini + Groq görüşlerini sentezle."""
    sonuclar = {"gemini": None, "groq": None}
    danisma_sorusu = (f"Soru: {komut}\n\n"
                      f"Bağlam: {internet_ctx[:800] if internet_ctx else 'Yok'}\n\n"
                      f"Kısa, öz Türkçe cevap ver.")

    def _gemini():
        try:
            sonuclar["gemini"] = llm_gemini(danisma_sorusu,
                "Bilgili YZ asistanısın. Kısa Türkçe cevap ver.", gemini_key)
        except Exception as e:
            sonuclar["gemini"] = f"(Gemini yanıt veremedi: {e})"

    def _groq():
        try:
            sonuclar["groq"] = llm_groq(
                [{"role":"user","content":danisma_sorusu}],
                "Bilgili YZ asistanısın. Kısa Türkçe cevap ver.", groq_key, groq_model)
        except Exception as e:
            sonuclar["groq"] = f"(Groq yanıt veremedi: {e})"

    t1 = threading.Thread(target=_gemini, daemon=True)
    t2 = threading.Thread(target=_groq,   daemon=True)
    t1.start(); t2.start()
    t1.join(timeout=30); t2.join(timeout=30)

    sentez_prompt = f"""Sen AURA-V\'sın. Üç yapay zekanın cevabını sentezle. Türkçe yaz.

SORU: {komut}

📌 AURA\'NIN CEVABI:
{aura_cevap}

🌟 GEMİNİ:
{sonuclar["gemini"] or "(yanıt alınamadı)"}

⚡ GROQ/LLAMA:
{sonuclar["groq"] or "(yanıt alınamadı)"}

Sentezi \"🧠 DANIŞMA KURULU SENTEZİ:\" başlığıyla yaz."""

    try:
        return llm_groq([{"role":"user","content":sentez_prompt}],
                        "Sen AURA-V\'sın. Türkçe sentez yap.",
                        groq_key, groq_model)
    except Exception:
        return llm_local(sentez_prompt, "")  # fallback
