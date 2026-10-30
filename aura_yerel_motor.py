# -*- coding: utf-8 -*-
"""
aura_yerel_motor.py
Ollama olmadan, llama-cpp-python ile GGUF modelleri çalıştırır.
Ollama'nın Client arayüzünü taklit eder:
    Client(host=...).chat(model=..., messages=..., options=..., stream=...)
    Client().generate(model=..., prompt=..., images=[...])
    Client().list()
Bu dosyayı ana Aura kodunun yanına koy (aynı klasör).
"""

import os
import gc
import base64
import threading
from pathlib import Path

try:
    from llama_cpp import Llama
    LLAMA_VAR = True
except ImportError:
    LLAMA_VAR = False

# ----------------------------------------------------------------------
# AYARLAR
# ----------------------------------------------------------------------
MODEL_KLASORU = Path(r"C:\Users\volka\Desktop\VOLKAN_AI\MODEL")

VARSAYILAN_MODEL = "aura-v.gguf"

# Kodundaki model adı -> gerçek dosya
MODEL_YOLLARI = {
    "aura-v.gguf": MODEL_KLASORU / "aura-v.gguf",
    # Dosya adını indirdiğin GGUF'a göre düzelt:
    "qwen2.5-coder:7b": MODEL_KLASORU / "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
}

# Vision (isteğe bağlı): (metin modeli, mmproj dosyası)
VISION_YOLLARI = {
    "moondream": (
        MODEL_KLASORU / "moondream2-text-model-f16.gguf",
        MODEL_KLASORU / "moondream2-mmproj-f16.gguf",
    ),
}

N_CTX = 8192
N_THREADS = 4
N_BATCH = 128
N_GPU_LAYERS = int(os.environ.get("AURA_GPU_LAYERS", "0"))


class _D(dict):
    """response['message']['content'] ve response.message.content ikisi de çalışır."""
    __getattr__ = dict.get


def _ad_temizle(ad):
    ad = (ad or VARSAYILAN_MODEL).strip()
    if ad.endswith(":latest"):
        ad = ad[:-7]
    return ad


class LocalClient:
    def __init__(self, host=None, **kwargs):
        self._kilit = threading.RLock()   # Llama thread-safe değil
        self._aktif_ad = None
        self._aktif = None
        self._uyari_verildi = set()

    # ------------------------------------------------------------------
    # Model yönetimi
    # ------------------------------------------------------------------
    def _mevcut_mu(self, ad):
        if ad in VISION_YOLLARI:
            m, p = VISION_YOLLARI[ad]
            return m.exists() and p.exists()
        return ad in MODEL_YOLLARI and MODEL_YOLLARI[ad].exists()

    def _yukle(self, ad):
        ad = _ad_temizle(ad)

        if not self._mevcut_mu(ad):
            if ad not in self._uyari_verildi:
                print(f"⚠️ [MOTOR] '{ad}' dosyası bulunamadı, "
                      f"'{VARSAYILAN_MODEL}' kullanılıyor.")
                self._uyari_verildi.add(ad)
            ad = VARSAYILAN_MODEL

        if self._aktif_ad == ad and self._aktif is not None:
            return self._aktif

        if not LLAMA_VAR:
            raise RuntimeError("llama-cpp-python kurulu değil: pip install llama-cpp-python")

        # Aynı anda tek model tut (RAM için)
        self._aktif = None
        self._aktif_ad = None
        gc.collect()

        print(f"🧠 [MOTOR] Model yükleniyor: {ad}")
        if ad in VISION_YOLLARI:
            from llama_cpp.llama_chat_format import MoondreamChatHandler
            metin_yolu, mmproj_yolu = VISION_YOLLARI[ad]
            handler = MoondreamChatHandler(clip_model_path=str(mmproj_yolu))
            llm = Llama(
                model_path=str(metin_yolu),
                chat_handler=handler,
                n_ctx=2048,
                n_threads=N_THREADS,
                n_gpu_layers=N_GPU_LAYERS,
                verbose=False,
            )
        else:
            llm = Llama(
                model_path=str(MODEL_YOLLARI[ad]),
                n_ctx=N_CTX,
                n_threads=N_THREADS,
                n_batch=N_BATCH,
                n_gpu_layers=N_GPU_LAYERS,
                verbose=False,
            )
        self._aktif = llm
        self._aktif_ad = ad
        return llm

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    @staticmethod
    def _parametreler(options):
        o = options or {}
        mt = o.get("num_predict", 512)
        p = {
            "temperature": o.get("temperature", 0.7),
            "top_p": o.get("top_p", 0.9),
            "max_tokens": None if mt in (-1, None) else mt,
        }
        if "top_k" in o:
            p["top_k"] = o["top_k"]
        if "repeat_penalty" in o:
            p["repeat_penalty"] = o["repeat_penalty"]
        stop = o.get("stop")
        if stop:
            p["stop"] = stop
        return p

    @staticmethod
    def _resim_uri(resim):
        if isinstance(resim, (bytes, bytearray)):
            resim = base64.b64encode(resim).decode()
        return "data:image/jpeg;base64," + str(resim)

    def _mesajlari_cevir(self, mesajlar):
        """Ollama'nın 'images' alanını OpenAI tarzı içeriğe çevirir."""
        sonuc = []
        for m in mesajlar:
            resimler = m.get("images")
            if resimler:
                icerik = [{"type": "text", "text": m.get("content", "")}]
                for r in resimler:
                    icerik.append({
                        "type": "image_url",
                        "image_url": {"url": self._resim_uri(r)},
                    })
                sonuc.append({"role": m["role"], "content": icerik})
            else:
                sonuc.append({"role": m["role"], "content": m.get("content", "")})
        return sonuc

    # ------------------------------------------------------------------
    # Ollama uyumlu API
    # ------------------------------------------------------------------
    def chat(self, model=None, messages=None, stream=False, options=None, **kwargs):
        p = self._parametreler(options)
        msgs = self._mesajlari_cevir(messages or [])

        if stream:
            def gen():
                with self._kilit:
                    llm = self._yukle(model)
                    for c in llm.create_chat_completion(messages=msgs, stream=True, **p):
                        delta = c["choices"][0].get("delta", {}).get("content")
                        if delta:
                            yield _D(message=_D(role="assistant", content=delta), done=False)
                    yield _D(message=_D(role="assistant", content=""), done=True)
            return gen()

        with self._kilit:
            llm = self._yukle(model)
            r = llm.create_chat_completion(messages=msgs, **p)
        txt = r["choices"][0]["message"]["content"] or ""
        return _D(message=_D(role="assistant", content=txt), done=True)

    def generate(self, model=None, prompt="", images=None, stream=False,
                 options=None, **kwargs):
        mesaj = {"role": "user", "content": prompt}
        if images:
            mesaj["images"] = images
        r = self.chat(model=model, messages=[mesaj], stream=False, options=options)
        return _D(response=r["message"]["content"], done=True)

    def list(self):
        modeller = []
        for ad in list(MODEL_YOLLARI) + list(VISION_YOLLARI):
            if self._mevcut_mu(ad):
                modeller.append(_D(name=ad, model=ad))
        return _D(models=modeller)


# Büyük koddaki "from ollama import Client" yerine bu isim kullanılır
Client = LocalClient
