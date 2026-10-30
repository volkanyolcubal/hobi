import numpy as np
import requests
from ddgs import DDGS

"""
KUANTUM FİZİK KEŞİF ARACI
=========================
Amaç: Eğlence değil, GERÇEK kuantum mekaniği kavramlarını anlamak.

Bu program:
1) Gerçek kuantum matematiğiyle (state vector simülasyonu) bir devre kurar
2) Devrenin ürettiği durumu (olasılık genlikleri) hesaplar
3) Ölçüm yapar (gerçek kuantum ölçümünün istatistiksel davranışını taklit eder)
4) Sonucu, senin lokal LLM'ine gönderip GERÇEK fizik açıklaması ister
   (mistik yorum değil, ders kitabı seviyesinde doğru açıklama)

SINIRLAMA (dürüst olmak gerekirse):
Bu klasik bir bilgisayarda çalışan bir SİMÜLASYON. ~20-25 qubit'ten sonra
hafıza yetmez çünkü durum uzayı 2^n boyutunda büyür. Gerçek kuantum
bilgisayarların avantajı olan "üstel hızlanma" burada YOK - biz aslında
klasik yöntemle kuantumu taklit ediyoruz, tersini değil.
"""

MODEL = "nchapman/gemma-2-9b-it-abliterated:9b"
OLLAMA_URL = "http://localhost:11434/api/generate"

# ---- Temel kapılar (gate) - gerçek kuantum matematiği ----
H = np.array([[1, 1], [1, -1]]) / np.sqrt(2)          # Hadamard: süperpozisyon yaratır
X = np.array([[0, 1], [1, 0]])                          # Pauli-X: klasik NOT gibi
Z = np.array([[1, 0], [0, -1]])                          # Pauli-Z: faz çevirir
I = np.eye(2)                                             # Kimlik (dokunma)


def kron_liste(matrisler):
    """Birden fazla matrisi tensör çarpımıyla birleştirir (çoklu qubit sistemi kurar)."""
    sonuc = matrisler[0]
    for m in matrisler[1:]:
        sonuc = np.kron(sonuc, m)
    return sonuc


def baslangic_durumu(n):
    """n qubit'lik sistemi |000...0> durumunda başlatır."""
    durum = np.zeros(2**n)
    durum[0] = 1
    return durum


def tek_qubit_kapisi_uygula(durum, n, kapi, hedef_qubit):
    """Belirli bir qubit'e (hedef_qubit) tek-qubit kapısı uygular, diğerlerine dokunmaz."""
    matrisler = [I] * n
    matrisler[hedef_qubit] = kapi
    tam_matris = kron_liste(matrisler)
    return tam_matris @ durum


def cnot_uygula(durum, n, kontrol, hedef):
    """
    CNOT kapısı: kontrol qubit 1 ise hedef qubit'i çevirir (X uygular).
    Bu, dolanıklık (entanglement) yaratan temel kapıdır.
    """
    yeni_durum = np.zeros_like(durum)
    boyut = 2**n
    for i in range(boyut):
        bitler = list(format(i, f'0{n}b'))
        if bitler[kontrol] == '1':
            # hedef biti çevir
            bitler[hedef] = '1' if bitler[hedef] == '0' else '0'
        j = int(''.join(bitler), 2)
        yeni_durum[j] += durum[i]
    return yeni_durum


def olcum_yap(durum, n, tekrar=1):
    """
    Durumu ölçer. Her ölçüm, olasılık genliklerinin karesine (Born kuralı)
    göre bir klasik sonuca "çöker". Bu, kuantum mekaniğinin gerçek
    matematiksel kuralıdır (Max Born, 1926).
    """
    olasiliklar = np.abs(durum) ** 2
    sonuclar = np.random.choice(len(durum), size=tekrar, p=olasiliklar)
    bit_dizileri = [format(s, f'0{n}b') for s in sonuclar]
    return bit_dizileri, olasiliklar


def durumu_yazdir(durum, n):
    """Durumu okunabilir şekilde yazdırır: hangi bit dizisinin hangi genliğe sahip olduğu."""
    print("\nDurum vektörü (sıfırdan büyük genlikler):")
    for i, genlik in enumerate(durum):
        if abs(genlik) > 1e-9:
            bit_dizisi = format(i, f'0{n}b')
            olasilik = abs(genlik) ** 2
            print(f"  |{bit_dizisi}>  genlik = {genlik:+.4f}   olasılık = %{olasilik*100:.2f}")


def web_arama_yap(sorgu, sonuc_sayisi=3):
    """
    İnternette gerçek kaynak arar. Bu sayede model, kendi ezberinden değil,
    GÜNCEL ve GERÇEK kaynaklardan gelen bilgiye dayanarak cevap verebilir.
    (Bu, RAG - Retrieval-Augmented Generation - denen mimarinin basit hali.)
    """
    try:
        sonuclar = DDGS(timeout=15).text(sorgu, max_results=sonuc_sayisi)
        if not sonuclar:
            return None
        kaynak_metni = ""
        for i, r in enumerate(sonuclar, 1):
            kaynak_metni += f"\n[Kaynak {i}: {r['title']}]\n{r['body']}\n(URL: {r['href']})\n"
        return kaynak_metni
    except Exception as e:
        print(f"(Web araması başarısız oldu: {e})")
        return None


def fizigi_acikla(soru, bit_dizileri, olasiliklar, n, devre_aciklamasi, model=MODEL):
    """LLM'e GERÇEK fizik açıklaması sorar - önce internetten kaynak bulur, sonra sorar."""
    ornek_sonuclar = bit_dizileri[:10]

    # ÖNEMLİ: olasiliklar dizisi 2^n boyutunda olabilir (15 qubit = 32768 eleman!)
    # Bunu olduğu gibi modele göndermek prompt'u devasa büyütür ve zaman aşımına
    # sebep olur. Bu yüzden sadece sıfırdan büyük (gerçekten mümkün) olan
    # durumları gönderiyoruz.
    onemli_olasiliklar = {}
    for i, p in enumerate(olasiliklar):
        if p > 1e-9:
            bit_dizisi = format(i, f'0{max(n,1)}b')
            onemli_olasiliklar[bit_dizisi] = round(float(p), 4)

    # 1) Önce internetten ilgili gerçek kaynak ara
    print("(İnternette kaynak aranıyor...)")
    arama_sorgusu = f"quantum physics {soru}"
    kaynaklar = web_arama_yap(arama_sorgusu)

    if kaynaklar:
        kaynak_blogu = f"""
Aşağıda bu soruyla ilgili İNTERNETTEN bulunmuş GÜNCEL kaynaklar var.
Cevabını verirken KENDİ EZBERİNE değil, öncelikle bu kaynaklara dayan.
Eğer kaynaklar bir iddiayı desteklemiyorsa ya da belirsizse, bunu AÇIKÇA belirt
("kaynaklar bunu doğrulamıyor" gibi). Uydurma yapma.

{kaynaklar}
"""
    else:
        kaynak_blogu = "\n(İnternet kaynağı bulunamadı, kendi bilgine dayanarak DİKKATLİ cevap ver, emin olmadığın yerlerde bunu belirt.)\n"

    prompt = f"""Sen bir kuantum mekaniği fizik öğretmenisin. Öğrenci sana bir
kuantum devresi kurdu ve sonuçlar hakkında soru soruyor. Ders kitabı
seviyesinde, DOĞRU ve GERÇEK fizik terimleriyle açıkla. Uydurma, mistik
veya şiirsel yorum YAPMA. Emin olmadığın ya da tartışmalı (yorum meselesi
olan) konularda bunu MUTLAKA belirt - "bu kanıtlanmış değil, tartışmalı
bir yorumdur" gibi. Süperpozisyon, dolanıklık, Born kuralı, olasılık
genliği gibi gerçek kavramları kullan. Türkçe ve anlaşılır anlat.
{kaynak_blogu}
Kurulan devre: {devre_aciklamasi}
Qubit sayısı: {n}
Örnek ölçüm sonuçları: {ornek_sonuclar}
Mümkün olan durumlar ve olasılıkları: {onemli_olasiliklar}

Öğrencinin sorusu: {soru}

Açıklaman (fiziksel olarak doğru, kaynaklara dayalı, 4-6 cümle):"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=300
        )
        response.raise_for_status()
        return response.json()["response"].strip()
    except requests.exceptions.ConnectionError:
        return "HATA: Ollama'ya bağlanılamadı. 'ollama serve' çalışıyor mu kontrol et."
    except Exception as e:
        return f"HATA: {e}"


# ---------------- ÖRNEK DENEYLER ----------------

def deney_1_tek_qubit_superpozisyon():
    """En basit deney: tek bir qubit'i süperpozisyona sokup ölçmek."""
    n = 1
    durum = baslangic_durumu(n)
    durum = tek_qubit_kapisi_uygula(durum, n, H, 0)
    durumu_yazdir(durum, n)
    bit_dizileri, olasiliklar = olcum_yap(durum, n, tekrar=1000)
    return bit_dizileri, olasiliklar, n, "1 qubit'e Hadamard kapısı uygulandı (süperpozisyon)"


def deney_2_bell_dolaniklik():
    """İki qubit'i dolanık hale getirme (Bell durumu)."""
    n = 2
    durum = baslangic_durumu(n)
    durum = tek_qubit_kapisi_uygula(durum, n, H, 0)
    durum = cnot_uygula(durum, n, kontrol=0, hedef=1)
    durumu_yazdir(durum, n)
    bit_dizileri, olasiliklar = olcum_yap(durum, n, tekrar=1000)
    return bit_dizileri, olasiliklar, n, "2 qubit: 1. qubit'e Hadamard, sonra CNOT (Bell durumu / dolanıklık)"


def deney_3_ghz_coklu_dolaniklik(n=5):
    """n tane qubit'i tek bir zincirde dolanık hale getirme (GHZ durumu)."""
    durum = baslangic_durumu(n)
    durum = tek_qubit_kapisi_uygula(durum, n, H, 0)
    for i in range(n - 1):
        durum = cnot_uygula(durum, n, kontrol=i, hedef=i + 1)
    durumu_yazdir(durum, n)
    bit_dizileri, olasiliklar = olcum_yap(durum, n, tekrar=1000)
    return bit_dizileri, olasiliklar, n, f"{n} qubit'lik GHZ durumu (hepsi zincirle dolanık)"


def deney_4_serbest_devre():
    """Kullanıcının kendi devresini adım adım kurmasına izin verir."""
    n = int(input("Kaç qubit istiyorsun? (1-15 arası önerilir): ").strip())
    durum = baslangic_durumu(n)
    islemler = []

    print("\nKapı ekleme modundasın. Kullanılabilir kapılar:")
    print("  h <qubit_no>     -> Hadamard (süperpozisyon)")
    print("  x <qubit_no>     -> Pauli-X (bit çevir)")
    print("  z <qubit_no>     -> Pauli-Z (faz çevir)")
    print("  cnot <kontrol> <hedef>  -> CNOT (dolanıklık yaratır)")
    print("  bitir            -> devreyi tamamla ve ölç")
    print("(qubit numaraları 0'dan başlar)\n")

    while True:
        komut = input("Kapı ekle: ").strip().lower().split()
        if not komut:
            continue
        if komut[0] == "bitir":
            break
        try:
            if komut[0] == "h":
                q = int(komut[1])
                durum = tek_qubit_kapisi_uygula(durum, n, H, q)
                islemler.append(f"H(q{q})")
            elif komut[0] == "x":
                q = int(komut[1])
                durum = tek_qubit_kapisi_uygula(durum, n, X, q)
                islemler.append(f"X(q{q})")
            elif komut[0] == "z":
                q = int(komut[1])
                durum = tek_qubit_kapisi_uygula(durum, n, Z, q)
                islemler.append(f"Z(q{q})")
            elif komut[0] == "cnot":
                k, h = int(komut[1]), int(komut[2])
                durum = cnot_uygula(durum, n, k, h)
                islemler.append(f"CNOT(kontrol=q{k},hedef=q{h})")
            else:
                print("Bilinmeyen komut, tekrar dene.")
        except (IndexError, ValueError):
            print("Hatalı format. Örnek: 'h 0' ya da 'cnot 0 1'")

    durumu_yazdir(durum, n)
    bit_dizileri, olasiliklar = olcum_yap(durum, n, tekrar=1000)
    devre_aciklamasi = " -> ".join(islemler) if islemler else "(hiç kapı uygulanmadı)"
    return bit_dizileri, olasiliklar, n, f"Serbest devre: {devre_aciklamasi}"


def sadece_soru_modu():
    """Kuantum devresi kurmadan, direkt genel bir kuantum fizik sorusu sor."""
    return [], np.array([1.0]), 0, "(Devre kurulmadı, genel kuantum fizik sorusu)"


DENEYLER = {
    "1": ("Tek qubit süperpozisyon", deney_1_tek_qubit_superpozisyon),
    "2": ("İki qubit dolanıklık (Bell durumu)", deney_2_bell_dolaniklik),
    "3": ("Çoklu qubit dolanıklık (GHZ durumu)", lambda: deney_3_ghz_coklu_dolaniklik(
        n=int(input("Kaç qubit dolanık olsun? (ör. 5): ").strip() or 5))),
    "4": ("Kendi devreni kur (serbest mod)", deney_4_serbest_devre),
    "5": ("Devre kurmadan direkt soru sor", sadece_soru_modu),
}


if __name__ == "__main__":
    print("=== KUANTUM FİZİK KEŞİF ARACI ===\n")
    print("Hangi deneyi çalıştırmak istersin?")
    for k, (isim, _) in DENEYLER.items():
        print(f"  {k}) {isim}")
    print()

    secim = input("Seçim (1-5): ").strip()
    if secim not in DENEYLER:
        secim = "1"

    isim, fonksiyon = DENEYLER[secim]
    print(f"\n>>> Çalıştırılıyor: {isim}\n")
    bit_dizileri, olasiliklar, n, devre_aciklamasi = fonksiyon()

    print(f"\n1000 ölçümün ilk 20 sonucu: {bit_dizileri[:20]}")

    print("\n--- Şimdi fizik öğretmenine soru sor ---")
    print("(Boş bırakıp Enter'a basarsan çıkarsın)\n")

    while True:
        soru = input("Sorunu yaz: ").strip()
        if not soru:
            break
        print("(Model düşünüyor, ilk seferde model yükleniyor olabilir, biraz sürebilir...)")
        cevap = fizigi_acikla(soru, bit_dizileri, olasiliklar, n, devre_aciklamasi)
        print(f"\n📘 Açıklama:\n{cevap}\n")
        print("-" * 60)
