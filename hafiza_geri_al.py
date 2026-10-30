# -*- coding: utf-8 -*-
"""
Yanlışlıkla pasifleştirilen 8 kaydı geri açar.
Aura KAPALIYKEN, aura_hafiza.db'nin olduğu klasörde çalıştır (IDLE'de F5 olur).
Uydurma 4 kayıt (#1759, #1761, #1763, #1765) pasif kalır.
"""
import shutil
import sqlite3
from datetime import datetime

HAFIZA_DB = "aura_hafiza.db"
GERI_ACILACAK = [105, 213, 461, 462, 1026, 1695, 1718, 1721]

yedek = f"{HAFIZA_DB}.geri_alma_yedek_{datetime.now():%Y%m%d_%H%M%S}"
shutil.copy2(HAFIZA_DB, yedek)
print("Yedek alındı:", yedek)

conn = sqlite3.connect(HAFIZA_DB)
yer = ",".join("?" * len(GERI_ACILACAK))
cur = conn.execute(
    f"UPDATE hafiza SET aktif=1 WHERE id IN ({yer}) AND tip='konusma'",
    GERI_ACILACAK,
)
conn.commit()
print(f"{cur.rowcount} kayıt geri açıldı.")

kalan = conn.execute(
    "SELECT id FROM hafiza WHERE id IN (1759,1761,1763,1765) AND aktif=0"
).fetchall()
print("Pasif kalan uydurma kayıtlar:", [k[0] for k in kalan])
conn.close()
