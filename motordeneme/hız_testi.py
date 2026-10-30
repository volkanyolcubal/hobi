"""
AURA-V hız testi

Modeli farklı iş parçacığı (thread) sayılarıyla yükleyip iki şeyi ölçer:
  - komut okuma hızı (prompt işleme, token/sn)
  - cevap yazma hızı (üretim, token/sn)

Sonuçlara göre aura_v.py içindeki N_THREADS değerini seçin.
Her deneme modeli yeniden yükler, toplam birkaç dakika sürebilir.
"""

import os
import sys
import time
from pathlib import Path

from llama_cpp import Llama

MODEL = Path(r"C:\Users\volka\Desktop\VOLKAN_AI\MODEL\aura-v.gguf")

if not MODEL.exists():
    print("Model bulunamadı:", MODEL)
    input("Enter...")
    sys.exit()

boyut_gb = MODEL.stat().st_size / (1024 ** 3)
mantiksal = os.cpu_count() or 4

print()
print("Model dosyası  : {:.2f} GB".format(boyut_gb))
print("Mantıksal çekirdek sayısı:", mantiksal)
print()

# En olası iki değer denenir (büyükten küçüğe); fazlası çok uzun sürer.
adaylar = sorted(set([
    mantiksal,
    max(1, (mantiksal * 3) // 4),
    max(1, mantiksal // 2)
]), reverse=True)[:2]

UZUN_METIN = (
    "Bu bir hız testi cümlesidir ve yalnızca komut işleme süresini "
    "ölçmek için tekrar edilmektedir. "
) * 15

sonuclar = []

for n in adaylar:
    print("-" * 50)
    print("N_THREADS =", n, "deneniyor...")

    t = time.time()
    llm = Llama(
        model_path=str(MODEL),
        n_ctx=4096,
        n_threads=n,
        n_gpu_layers=0,
        verbose=False
    )
    print("  model yükleme : {:.1f} sn".format(time.time() - t))

    # 1) komut işleme hızı
    t = time.time()
    r = llm.create_completion(prompt=UZUN_METIN, max_tokens=1)
    sure = time.time() - t
    tok = r["usage"]["prompt_tokens"]
    prompt_hizi = tok / sure
    print("  komut okuma   : {} token, {:.1f} sn  ->  {:.1f} token/sn".format(
        tok, sure, prompt_hizi))

    # 2) cevap yazma hızı
    t = time.time()
    r = llm.create_completion(prompt="Merhaba, bana kendini tanıt.", max_tokens=48)
    sure = time.time() - t
    tok = r["usage"]["completion_tokens"]
    uretim_hizi = tok / sure
    print("  cevap yazma   : {} token, {:.1f} sn  ->  {:.1f} token/sn".format(
        tok, sure, uretim_hizi))

    sonuclar.append((n, prompt_hizi, uretim_hizi))

    del llm

print()
print("=" * 50)
print("ÖZET")
for n, ph, uh in sonuclar:
    print("N_THREADS={:<3} komut okuma {:>6.1f} tok/sn | cevap yazma {:>5.1f} tok/sn".format(n, ph, uh))

en_iyi = max(sonuclar, key=lambda x: x[2])
print()
print("Cevap yazma hızına göre en iyi: N_THREADS =", en_iyi[0])
print()
print("Yorum: cevap yazma 3 tok/sn altındaysa model bu bilgisayar için büyük;")
print("       daha küçük/Q4 bir GGUF modele geçmek en etkili çözümdür.")
print()
input("Enter...")
