# -*- coding: utf-8 -*-
"""
Kullanım (aura_yerel_motor.py ile aynı klasörde):
    python aura_yama.py ana_aura_dosyan.py

Orijinal dosyaya DOKUNMAZ. Yanına  <ad>_yerel.py  üretir.
Orijinalin ayrıca <ad>_ORIJINAL_YEDEK.py olarak yedeği de alınır.
"""
import re
import sys
import shutil
from pathlib import Path

if len(sys.argv) < 2:
    print("Kullanım: python aura_yama.py ana_aura_dosyan.py")
    sys.exit(1)

kaynak = Path(sys.argv[1])
if not kaynak.exists():
    print("Dosya bulunamadı:", kaynak)
    sys.exit(1)

yedek = kaynak.with_name(kaynak.stem + "_ORIJINAL_YEDEK.py")
hedef = kaynak.with_name(kaynak.stem + "_yerel.py")
shutil.copy2(kaynak, yedek)

kod = kaynak.read_text(encoding="utf-8")

YAMALAR = []


def yama(ad, desen, yerine):
    global kod
    yeni, sayi = re.subn(desen, lambda m: yerine, kod, count=1, flags=re.DOTALL)
    kod = yeni
    YAMALAR.append((ad, sayi))


# 1) Ollama otomatik başlatıcı
yama(
    "Ollama otomatik başlatıcı silindi",
    r'try:\s*\n\s*subprocess\.Popen\(\["ollama", "serve"\].*?'
    r'Ollama başlatılamadı[^\n]*\n',
    'print("🧠 Yerel motor (llama-cpp) kullanılıyor, Ollama gerekmiyor.")\n',
)

# 2) import ollama / dummy Client bloğu
yama(
    "ollama import bloğu yerel motorla değiştirildi",
    r"try:\s*\n\s*import ollama\s*\n\s*from ollama import Client.*?"
    r"return \{'models': \[\]\}\n",
    "from aura_yerel_motor import Client\nOLLAMA_MOD = True\n",
)

# 3) aura_gozcu_bak içindeki ollama.generate
yama(
    "ollama.generate yerel motora bağlandı",
    r"try:\s*\n\s*from ollama import generate as ollama_generate\s*\n"
    r"\s*except ImportError:\s*\n\s*ollama_generate = None\n",
    "ollama_generate = lambda **kw: ollama_client.generate(**kw)\n",
)

# 4) coder_yukle
yama(
    "coder_yukle (ollama pull) değiştirildi",
    r"    def coder_yukle\(self\) -> str:.*?(?=\n    def kod_yaz)",
    "    def coder_yukle(self) -> str:\n"
    "        return (\"ℹ️ Coder GGUF dosyasını MODEL klasörüne indirip \"\n"
    "                \"aura_yerel_motor.py içindeki MODEL_YOLLARI'na yaz.\")\n",
)

hedef.write_text(kod, encoding="utf-8")

print()
for ad, sayi in YAMALAR:
    print(("✅ " if sayi else "❌ BULUNAMADI: ") + ad)

if all(s for _, s in YAMALAR):
    try:
        compile(kod, str(hedef), "exec")
        print("\n✅ Sözdizimi kontrolü geçti.")
    except SyntaxError as e:
        print("\n⚠️ Sözdizimi hatası, satır", e.lineno, "-", e.msg)
    print("Yeni dosya :", hedef)
    print("Yedek      :", yedek)
else:
    print("\n⚠️ Bazı bloklar bulunamadı. Dosya yine de yazıldı ama eksik yama var.")
    print("Hangisinin bulunamadığını bana söyle, elle düzeltiriz.")
