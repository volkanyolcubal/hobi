"""
AURA-V — TTS (Metin → Ses) Modülü
gTTS (Google) ve tarayıcı sesi desteği
"""
import os, hashlib

def gtts_olustur(metin: str) -> str | None:
    """gTTS ile Türkçe ses dosyası oluştur, URL path döndür."""
    try:
        from gtts import gTTS
        os.makedirs("static/tts", exist_ok=True)
        dosya_adi = hashlib.md5(metin.encode()).hexdigest()[:12] + ".mp3"
        dosya_yol = f"static/tts/{dosya_adi}"
        if not os.path.exists(dosya_yol):
            tts = gTTS(text=metin[:500], lang="tr", slow=False)
            tts.save(dosya_yol)
        return f"/static/tts/{dosya_adi}"
    except ImportError:
        return None
    except Exception as e:
        print(f"gTTS hatası: {e}")
        return None
