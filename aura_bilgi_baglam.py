# -*- coding: utf-8 -*-
"""
Sorudaki kelimelerle eşleşen 'dogru_bilgi' kayıtlarını bulur ve
modele verilecek bağlam metni olarak döndürür.
"""
import re

_CEVIR = str.maketrans({
    "ı": "i", "İ": "i", "I": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
})

_YOKSAY = {
    "nedir", "anlat", "kimdir", "bilgin", "varmi", "nasil", "neden",
    "hakkinda", "icin", "olarak", "maddesi", "bana", "sence", "misin",
}


def _kelimeler(metin):
    metin = metin.translate(_CEVIR).lower()
    # Einstein'in -> einstein  (kesme işaretinden sonrasını at)
    metin = re.sub(r"'\w*", " ", metin)
    metin = re.sub(r"[^a-z0-9\s]", " ", metin)
    return {k for k in metin.split() if len(k) >= 5 and k not in _YOKSAY}


def bilgi_baglami(hafiza, soru, en_fazla=2):
    """Eşleşen doğrulanmış kayıt yoksa boş string döner."""
    try:
        kayitlar = hafiza.ara(tip="dogru_bilgi", limit=200)
    except Exception:
        return ""

    soru_k = _kelimeler(soru)
    if not soru_k:
        return ""

    puanli = []
    for k in kayitlar:
        puan = len(soru_k & _kelimeler(k.get("konu", "")))
        if puan:
            puanli.append((puan, k))

    if not puanli:
        return ""

    puanli.sort(key=lambda x: x[0], reverse=True)
    parcalar = [
        "[MİMARIN DOĞRULANMIŞ BİLGİLERİ — bunlara aykırı cevap verme]"
    ]
    for _, k in puanli[:en_fazla]:
        parcalar.append("- " + k["icerik"][:450])
    return "\n".join(parcalar)
