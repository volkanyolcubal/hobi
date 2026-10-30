# -*- coding: utf-8 -*-
"""
Kullanım (Aura KAPALIYKEN, aura_hafiza.db'nin olduğu klasörde):
    python hafiza_temizle.py Zorlu antlasma

Verilen anahtar kelimelerden HERHANGİ BİRİNİ içeren konuşma kayıtlarını
pasifleştirir (silmez, aktif=0 yapar; geri alınabilir).
Önce otomatik yedek alır.
"""
import sys
import shutil
import sqlite3
from datetime import datetime

from aura_kalici_hafiza import KaliciHafiza, HAFIZA_DB

if len(sys.argv) >= 2:
    anahtarlar = [a.lower() for a in sys.argv[1:]]
else:
    # IDLE gibi argüman veremeyen ortamlarda soru sorar
    ham = input("Temizlenecek ifadeler (virgülle ayır, örn: Zorlu Antlaşması, Zorlu morlu): ").strip()
    anahtarlar = [a.strip().lower() for a in ham.split(",") if a.strip()]
    if not anahtarlar:
        print("Kelime girilmedi, çıkılıyor.")
        sys.exit(1)

yedek = f"{HAFIZA_DB}.temizlik_yedek_{datetime.now():%Y%m%d_%H%M%S}"
shutil.copy2(HAFIZA_DB, yedek)
print("Yedek alındı:", yedek)

h = KaliciHafiza()
conn = sqlite3.connect(HAFIZA_DB)
conn.row_factory = sqlite3.Row

satirlar = conn.execute(
    "SELECT id, konu, icerik, sifreli FROM hafiza "
    "WHERE tip='konusma' AND aktif=1"
).fetchall()

silinecek = []
for s in satirlar:
    metin = s["icerik"]
    if s["sifreli"]:
        metin = h._anahtar.coz(metin)
    if any(a in metin.lower() for a in anahtarlar):
        silinecek.append((s["id"], metin[:80].replace("\n", " | ")))

for kid, onizleme in silinecek:
    print(f"  pasifleştirilecek #{kid}: {onizleme}")

if silinecek:
    cevap = input(f"\n{len(silinecek)} kayıt pasifleştirilsin mi? (e/h): ").strip().lower()
    if cevap == "e":
        conn.executemany(
            "UPDATE hafiza SET aktif=0 WHERE id=?",
            [(k,) for k, _ in silinecek],
        )
        conn.commit()
        print("Tamam.")
    else:
        print("İptal edildi.")
else:
    print("Eşleşen konuşma bulunamadı.")

conn.close()
