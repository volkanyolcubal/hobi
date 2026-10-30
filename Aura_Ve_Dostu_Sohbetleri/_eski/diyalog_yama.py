# -*- coding: utf-8 -*-
"""
Kullanım (aura_yerel_motor.py ile aynı klasörde):
    python diyalog_yama.py diyalog_dosyan.py
IDLE'de çalıştırırsan dosya adını sorar.

Orijinale DOKUNMAZ. <ad>_yerel.py üretir, ayrıca <ad>_ORIJINAL_YEDEK.py kaydeder.
"""
import re
import sys
import shutil
from pathlib import Path

if len(sys.argv) >= 2:
    ad = sys.argv[1]
else:
    ad = input("Diyalog dosyasının adı (örn: diyalog.py): ").strip().strip('"')

kaynak = Path(ad)
if not kaynak.exists():
    print("Dosya bulunamadı:", kaynak)
    sys.exit(1)

yedek = kaynak.with_name(kaynak.stem + "_ORIJINAL_YEDEK.py")
hedef = kaynak.with_name(kaynak.stem + "_yerel.py")
shutil.copy2(kaynak, yedek)

kod = kaynak.read_text(encoding="utf-8")
sonuclar = []


def yama(isim, desen, yerine):
    global kod
    kod, sayi = re.subn(desen, lambda m: yerine, kod, count=1, flags=re.DOTALL)
    sonuclar.append((isim, sayi))


# 1) Ollama adresi + Path'li MODEL satırı
yama(
    "OLLAMA_URL ve MODEL satırları yerel motorla değiştirildi",
    r'OLLAMA_URL\s*=\s*"[^"]*"\s*\n(?:#.*\n)*MODEL\s*=\s*Path\([^\n]*\)\n',
    'from aura_yerel_motor import LocalClient\n'
    'yerel_motor = LocalClient()\n'
    'MODEL = "aura-v.gguf"\n',
)

# 2) generate_response (HTTP isteği yerine yerel motor)
yama(
    "generate_response yerel motora bağlandı",
    r'def generate_response\(prompt\):.*?(?=\n\s*#\s*─)',
    'def generate_response(prompt):\n'
    '    try:\n'
    '        r = yerel_motor.generate(\n'
    '            model=MODEL,\n'
    '            prompt=prompt,\n'
    '            options={"temperature": 0.9, "num_predict": 200},\n'
    '        )\n'
    '        return (r["response"] or "").strip() or "..."\n'
    '    except Exception as e:\n'
    '        return f"Sistem hatası: {str(e)}"\n'
    '\n',
)

hedef.write_text(kod, encoding="utf-8")

print()
for isim, sayi in sonuclar:
    print(("✅ " if sayi else "❌ BULUNAMADI: ") + isim)

if all(s for _, s in sonuclar):
    try:
        compile(kod, str(hedef), "exec")
        print("\n✅ Sözdizimi kontrolü geçti.")
    except SyntaxError as e:
        print("\n⚠️ Sözdizimi hatası, satır", e.lineno, "-", e.msg)
    print("Yeni dosya:", hedef)
    print("Yedek     :", yedek)
else:
    print("\n⚠️ Bazı bloklar bulunamadı. Hangisi olduğunu bana yaz.")
