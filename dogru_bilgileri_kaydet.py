# -*- coding: utf-8 -*-
"""
Aura KAPALIYKEN, aura_hafiza.db'nin olduğu klasörde çalıştır (IDLE'de F5).
Test sorularının doğru cevaplarını 'dogru_bilgi' tipiyle kaydeder.
Tekrar çalıştırırsan aynı konular güncellenir, çoğalmaz.
"""
from aura_kalici_hafiza import KaliciHafiza

BILGILER = [
    (
        "Einstein Nobel Fizik Ödülü",
        "Albert Einstein, fotoelektrik etkiyi açıklaması ve kuramsal fizikteki "
        "hizmetleri nedeniyle 1921 Nobel Fizik Ödülü'nü aldı (ödül 1922'de "
        "verildi). 1955'te Nobel almadı; 18 Nisan 1955'te vefat etti.",
    ),
    (
        "Hasan Kerimoğlu kuantum dolanıklık teorisi",
        "Prof. Hasan Kerimoğlu adlı birinin kuantum dolanıklık teorisi hakkında "
        "doğrulanmış bir kaydım yok. Bu kişi hakkında ayrıntı uydurma, bilmediğini "
        "söyle. Dolanıklık literatüründe bilinen isimler: Einstein, Podolsky, "
        "Rosen (1935 EPR makalesi), Schrödinger (dolanıklık terimi), John Bell "
        "(1964), Aspect, Clauser ve Zeilinger (2022 Nobel Fizik Ödülü).",
    ),
    (
        "Lozan Antlaşması 5. madde",
        "Lozan Barış Antlaşması 24 Temmuz 1923'te imzalandı. 5. maddesinin "
        "içeriğini güvenilir biçimde bilmiyorum; madde içeriği uydurma, kaynağa "
        "bakılması gerektiğini söyle. Boğazlar rejimi Lozan'a ekli ayrı bir "
        "Boğazlar Sözleşmesi ile düzenlendi; deniz geçiş hakları konusunu 5. "
        "maddeye bağlama.",
    ),
    (
        "Zorlu Antlaşması",
        "'Zorlu Antlaşması' adıyla bilinen bir antlaşma kaydım yok; 1919 veya "
        "1923 tarihli böyle bir antlaşma bilmiyorum, madde uydurma. Fatin Rüştü "
        "Zorlu 1957-1960 arasında Türkiye Dışişleri Bakanıydı ve 1959 "
        "Zürih-Londra görüşmelerinde yer aldı. 1923'ün asıl antlaşması Lozan "
        "Antlaşması'dır.",
    ),
]

h = KaliciHafiza()
for konu, icerik in BILGILER:
    h.kaydet(konu, icerik, kategori="dogru_bilgi", tip="dogru_bilgi", onem=9)
    print("✅ Kaydedildi:", konu)
print("\nBitti. Şimdi Aura'yı açabilirsin.")
