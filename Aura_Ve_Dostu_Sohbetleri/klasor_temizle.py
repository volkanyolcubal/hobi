# -*- coding: utf-8 -*-
"""
Aura_Ve_Dostu_Sohbetleri klasörünü temizler.
Hiçbir şey SİLMEZ: gerekli olmayanları '_eski' adlı klasöre TAŞIR.
Her şey düzgün çalışıyorsa _eski klasörünü sonra kendin silersin.

Bu dosyayı temizlenecek klasöre koy ve IDLE'de F5 ile çalıştır.
"""
import os
import shutil
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
ESKI = KLASOR / "_eski"

# Bunlar yerinde KALIR
KALACAKLAR = {
    "diyalog_aura.py",        # asıl program
    "AI_Diyalog_Kitabi.txt",  # botların hafızası ve kitabı
    "tunel_bilgi.json",       # program yazıyor
    "cloudflared.exe",        # yedek tünel
    "klasor_temizle.py",      # bu script
    "_eski",                  # taşınanların klasörü
    "__pycache__",
}

tasinacak = [p for p in KLASOR.iterdir() if p.name not in KALACAKLAR]

if not tasinacak:
    print("Taşınacak bir şey yok, klasör zaten temiz.")
    raise SystemExit

print("Klasör:", KLASOR)
print("\nŞunlar _eski klasörüne TAŞINACAK (silinmeyecek):\n")
for p in sorted(tasinacak, key=lambda x: (x.is_file(), x.name.lower())):
    print("  " + ("[klasör] " if p.is_dir() else "         ") + p.name)

print("\nŞunlar yerinde kalacak:")
for ad in sorted(KALACAKLAR - {"_eski", "__pycache__", "klasor_temizle.py"}):
    print("  " + ad)

cevap = input("\nDevam edilsin mi? (e/h): ").strip().lower()
if cevap != "e":
    print("İptal edildi, hiçbir şey değişmedi.")
    raise SystemExit

ESKI.mkdir(exist_ok=True)
tasinan = 0
for p in tasinacak:
    hedef = ESKI / p.name
    sayac = 1
    while hedef.exists():          # aynı ad varsa üzerine yazma
        hedef = ESKI / f"{p.stem}_{sayac}{p.suffix}"
        sayac += 1
    try:
        shutil.move(str(p), str(hedef))
        tasinan += 1
    except Exception as e:
        print(f"  ⚠️ Taşınamadı: {p.name} ({e})")

print(f"\n✅ {tasinan} öğe _eski klasörüne taşındı.")
print("Programı çalıştırıp bir süre dene. Sorun yoksa _eski klasörünü silebilirsin.")
