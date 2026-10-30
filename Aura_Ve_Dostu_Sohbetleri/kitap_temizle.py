# -*- coding: utf-8 -*-
"""
AI_Diyalog_Kitabi.txt içindeki hata kayıtlarını temizler.
Önce yedek alır, sonra içinde hata anahtar kelimeleri geçen BÖLÜM'leri çıkarır.
Diyalog programı KAPALIYKEN, kitabın olduğu klasörde çalıştır (IDLE'de F5).
"""
import re
import shutil
from datetime import datetime
from pathlib import Path

KITAP = Path(__file__).resolve().parent / "AI_Diyalog_Kitabi.txt"

ANAHTARLAR = [
    "sistem hatası",
    "httpconnectionpool",
    "max retries exceeded",
    "connection refused",
    "winerror 10061",
    "11434",
]

if not KITAP.exists():
    print("Kitap bulunamadı:", KITAP)
    raise SystemExit

yedek = KITAP.with_name(f"AI_Diyalog_Kitabi_YEDEK_{datetime.now():%Y%m%d_%H%M%S}.txt")
shutil.copy2(KITAP, yedek)
print("Yedek alındı:", yedek.name)

metin = KITAP.read_text(encoding="utf-8")
ayrac = "─" * 80
desen = re.compile(
    r"\n" + ayrac + r"\nBÖLÜM \d+: [^\n]+\n" + ayrac + r"\n(.*?)\n" + ayrac + r"\n",
    re.DOTALL,
)

toplam = 0
silinen = 0


def filtre(m):
    global toplam, silinen
    toplam += 1
    govde = m.group(1).lower()
    if any(a in govde for a in ANAHTARLAR):
        silinen += 1
        return ""
    return m.group(0)


yeni = desen.sub(filtre, metin)
KITAP.write_text(yeni, encoding="utf-8")

print(f"Toplam {toplam} bölüm tarandı, {silinen} hatalı bölüm çıkarıldı, "
      f"{toplam - silinen} bölüm kaldı.")
