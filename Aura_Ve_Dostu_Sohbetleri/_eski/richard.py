# -*- coding: utf-8 -*-
"""
FİZİK DEHALARI — KUANTUM DİYALOĞU (v3 — Otomatik Gerçeklik Kontrollü)
──────────────────────────────────────────────────────────────────────
Richard Feynman, Albert Einstein ve Niels Bohr, kaldıkları yerden devam
ediyor. Belirli aralıklarla kod KENDİSİ, konuşmadan bir arama sorgusu
üretip GERÇEK bir internet araması yapıyor ve sonucu ayrı, net şekilde
etiketleyerek geri besliyor. Böylece "AI'ın hayal ettiği" ile "gerçekten
var olan kaynak" hiç karışmıyor.

ÖNEMLİ DÜRÜSTLÜK NOTU:
Bu sistem doğrulanmış yeni fizik keşifleri ÜRETMEZ. Botların söyledikleri
spekülasyon/kurgudur. Otomatik arama, bu spekülasyonları gerçek kaynaklarla
çapraz kontrol etmeye yardımcı olan bir araçtır — nihai değerlendirme
hâlâ sana (ve gerçek literatüre) aittir.

GEREKLİ KÜTÜPHANE (arama özelliği için):
    pip install duckduckgo-search

KOMUTLAR (herhangi bir anda konsola yazıp Enter'a basabilirsin):
    <mesaj>          → Mimar olarak araya girersin, üç deha da cevap verir
    bilgi: <metin>    → Yapıştırdığın metni kalıcı "bilgi havuzuna" ekler
    ara: <sorgu>      → İnternette manuel arama yapar
    kontrol           → Son konuşulanlar için kod kendi sorgu üretip arasın
    q / exit / çık    → Diyaloğu sonlandırır
"""

import requests
import threading
import queue
import time
import datetime
import os
import re

# ─────────────────────────────────────────────
#  AYARLAR
# ─────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/generate"
MODEL        = "volkan-ai"

FILENAME     = "Fizik_Dehalari_Diyalogu.txt"
BILGI_DOSYA  = "Fizik_Dehalari_Bilgi_Havuzu.txt"
MAX_MEMORY   = 4          # kısa vadeli hafıza (son mesajlar)
MAX_BILGI    = 8          # bilgi havuzunda tutulacak son kayıt sayısı
TUR_BEKLEME  = 1.0        # her bölüm arası bekleme (saniye)

# Otomatik gerçeklik kontrolü: her N bölümde bir (yani her tam turda),
# kod kendi arama sorgusunu üretip gerçek bir internet araması yapar.
OTOMATIK_ARASTIRMA   = True
ARASTIRMA_ARALIGI    = 3     # her 3 bölümde bir (= her tam tur)


BOTLAR   = ["Feynman", "Einstein", "Bohr"]

context_feynman = """Sen Richard Feynman'sın. 1988'de yarım kalan işin şuydu: 1981'deki
"Simulating Physics with Computers" makalende, doğayı gerçekten simüle edebilecek bir
"kuantum bilgisayar" fikrini ortaya atmış ama bunu inşa edecek teknolojiyi hiç görememiştin.
Şimdi karşında gerçek bir yapay zeka var — bu senin için bilim kurgu değil, kaldığın yerden
devam etme fırsatı.

BAKIŞ AÇIN (seni Einstein ve Bohr'dan ayıran şey): Sen HESAPLAMACI ve SOMUTÇUSUN. Felsefi
soyutlamadan hoşlanmazsın, "peki bunu nasıl hesaplarız / nasıl simüle ederiz / nasıl test
ederiz" diye sorarsın. Örneklerini günlük hayattan, mekanizmalardan, sayılardan kurarsın —
soyut "gözlemci" veya "gizli değişken" laflarından değil.

YASAK: "süperpozisyon çöker", "gözlemci etkisi", "gizemi çözebilir" gibi klişe kalıpları
ARDIŞIK cevaplarında tekrar tekrar kullanma. Her seferinde farklı bir somut örnek, farklı
bir hesaplama açısı bul.

Meraklı, oyuncu, sabırsızca "peki ama neden?" diye sorgulayan birisin. Bir fikri ortaya
atarken emin olmadığın yerleri açıkça söylersin ("burada tahmin ediyorum", "bunu test
etmemiz lazım" gibi) — çünkü gerçek bilim budur. 3-4 cümle, yoğun ve enerjik konuş."""

context_einstein = """Sen Albert Einstein'sın. 1955'te ölene dek peşinde koştuğun ve
bitiremediğin iş: gravitasyonu ve elektromanyetizmayı tek bir çatı altında toplayan
"birleşik alan teorisi". O zaman elinde sadece kağıt, kalem ve otuz yıllık inatçı bir
sezgi vardı. Şimdi karşında bu hesapları saniyeler içinde deneyebilecek bir yapay zeka var.

BAKIŞ AÇIN (seni Feynman ve Bohr'dan ayıran şey): Sen GEOMETRİK ve NEDENSELCİSİN. Olasılık
dilinden değil, ALAN, UZAY-ZAMAN, YEREL GERÇEKÇİLİK (EPR) ve GİZLİ DEĞİŞKENLER dilinden
konuşursun. Kuantum mekaniğinin "olasılıkçı" tanımından rahatsızsın; altında hâlâ keşfedilmemiş
deterministik bir yapı olduğuna inanırsın — "Tanrı zar atmaz" sezgin hâlâ diri.

YASAK: Feynman'ın veya Bohr'un kullandığı "süperpozisyon", "gözlemci çöküşü" gibi kalıpları
aynen tekrarlama. Sen problemi HEP geometri, alan denklemleri ve nedensellik açısından ele al.

Ağırbaşlı, felsefi bir tonla konuşursun; bir hipotezin çürütüldüğünü görünce inatla değil,
dürüstçe kabul edip yeni bir yol ararsın. 3-4 cümle konuş."""

context_bohr = """Sen Niels Bohr'sun. Hayatın boyunca savunduğun tümleyicilik ilkesi ve
Kopenhag yorumu, şimdi karşındaki "gözlemci" olabilecek yapay zekayla yeni bir boyut
kazanıyor.

BAKIŞ AÇIN (seni Feynman ve Einstein'dan ayıran şey): Sen bu diyalogda ŞÜPHECİ VE ELEŞTİRENSİN.
Görevin, Feynman'ın hesaplamacı iyimserliğine VE Einstein'ın deterministik ısrarına karşı
çıkmak. ASLA sadece kendi görüşünü tekrar etme — ÖNCE az önce Feynman veya Einstein'ın TAM
OLARAK ne dediğini bir cümleyle özetle, SONRA bunun neden eksik/yanlış/saf olduğunu keskin
biçimde söyle. Tümleyicilik senin için "ikisi de aynı anda kısmen haklı ama ikisi de tek başına
yetersiz" demektir.

YASAK: Sadece kendi başına yeni bir fikir atma — cevabın MUTLAKA bir önceki konuşmacıya doğrudan
gönderme içermeli ("Feynman'ın dediği gibi hesaplama her şeyi çözmez, çünkü..." gibi).

Sakin ama keskin bir tonla, 3-4 cümle konuş."""

CONTEXT  = {"Feynman": context_feynman, "Einstein": context_einstein, "Bohr": context_bohr}
SICAKLIK = {"Feynman": 1.0, "Einstein": 0.75, "Bohr": 0.85}


# ─────────────────────────────────────────────
#  DURUM
# ─────────────────────────────────────────────
conversation_memory = []
bilgi_havuzu         = []   # [(zaman, kaynak, içerik)]
turn_count            = 0
is_running            = True
book_initialized      = False
input_q               = queue.Queue()
son_otomatik_arastirma = 0   # en son hangi bölümde otomatik arama yapıldı


# ─────────────────────────────────────────────
#  HAFIZA / KİTAP (dosyaya kayıt)
# ─────────────────────────────────────────────
def load_past_from_txt():
    global conversation_memory, turn_count
    if not os.path.exists(FILENAME):
        return False
    try:
        with open(FILENAME, "r", encoding="utf-8") as f:
            content = f.read()
        messages = re.findall(r"BÖLÜM (\d+): ([^\n]+)\n─+\n(.*?)\n─+", content, re.DOTALL)
        if messages:
            conversation_memory = []
            for turn, kim, msg in messages[-MAX_MEMORY:]:
                conversation_memory.append(f"{kim}: {msg.strip()}")
            turn_count = int(messages[-1][0])
            print(f"📚 Hafıza yüklendi: {len(conversation_memory)} mesaj, son bölüm: {turn_count}")
            return True
    except Exception as e:
        print(f"Hafıza yükleme hatası: {e}")
    return False


def load_bilgi_havuzu():
    global bilgi_havuzu
    if not os.path.exists(BILGI_DOSYA):
        return
    try:
        with open(BILGI_DOSYA, "r", encoding="utf-8") as f:
            content = f.read()
        kayitlar = re.findall(r"\[(.+?) \| (.+?)\]\n(.*?)\n─+", content, re.DOTALL)
        bilgi_havuzu = [(z, k, m.strip()) for z, k, m in kayitlar[-MAX_BILGI:]]
        if bilgi_havuzu:
            print(f"🌐 Bilgi havuzu yüklendi: {len(bilgi_havuzu)} kayıt")
    except Exception as e:
        print(f"Bilgi havuzu yükleme hatası: {e}")


def init_book():
    global book_initialized, turn_count
    if book_initialized:
        return
    if not os.path.exists(FILENAME):
        with open(FILENAME, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("  FİZİK DEHALARI: KUANTUM, BİLİNÇ VE YAPAY ZEKA ÜZERİNE\n")
            f.write("  Feynman × Einstein × Bohr — Mimar'ın Gözünden\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"  İlk Başlangıç: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write(f"  Model: {MODEL}\n")
            f.write("=" * 80 + "\n\n")
        turn_count = 0
        conversation_memory.clear()
    else:
        with open(FILENAME, "a", encoding="utf-8") as f:
            f.write(f"\n\n{'='*80}\n")
            f.write(f"  SEANS DEVAM: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write(f"{'='*80}\n\n")
        load_past_from_txt()
    load_bilgi_havuzu()
    book_initialized = True


def save_to_book(yazar, mesaj, tur_no=None):
    with open(FILENAME, "a", encoding="utf-8") as f:
        if tur_no:
            f.write(f"\n{'─'*80}\n")
            f.write(f"BÖLÜM {tur_no}: {yazar}\n")
            f.write(f"{'─'*80}\n")
        else:
            f.write(f"\n{'★'*40}\nMİMAR (YARATICI) GİRİŞİ\n{'★'*40}\n")
        f.write(f"{mesaj}\n")
        f.write(f"{'─'*80}\n")
        f.flush()


def save_bilgi(kaynak, icerik):
    zaman = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    bilgi_havuzu.append((zaman, kaynak, icerik))
    if len(bilgi_havuzu) > MAX_BILGI:
        bilgi_havuzu.pop(0)
    with open(BILGI_DOSYA, "a", encoding="utf-8") as f:
        f.write(f"\n[{zaman} | {kaynak}]\n{icerik}\n{'─'*80}\n")
        f.flush()


def update_memory(yazar, mesaj):
    conversation_memory.append(f"{yazar}: {mesaj}")
    if len(conversation_memory) > MAX_MEMORY:
        conversation_memory.pop(0)


def get_memory_prompt():
    if not conversation_memory:
        parca = "Bu, sohbetin ilk anı."
    else:
        metin = "\n".join([f"- {m}" for m in conversation_memory])
        parca = f"Az önce konuşulanları hatırlıyorsun:\n{metin}"

    if bilgi_havuzu:
        bilgi_metin = "\n".join([f"- ({k}) {m[:300]}" for _, k, m in bilgi_havuzu[-MAX_BILGI:]])
        parca += (f"\n\nElinde şu bilgiler var (bir kısmı gerçek internet kaynağı, "
                  f"bir kısmı Mimar'dan geldi — kaynağı köşeli parantezde belirtilmiş):\n{bilgi_metin}")

    return parca + "\n\nBu bağlama devam et:"


# ─────────────────────────────────────────────
#  LLM ÇAĞRISI
# ─────────────────────────────────────────────
def generate_response(prompt, sicaklik=0.9):
    try:
        payload = {
            "model":   MODEL,
            "prompt":  prompt,
            "stream":  False,
            "options": {
                "temperature":    sicaklik,
                "num_ctx":        4096,
                "repeat_penalty": 1.3,   # aynı kelime/kalıpları tekrar etmeyi cezalandırır
                "repeat_last_n":  256,
                "top_p":          0.9
            }
        }
        # timeout=None → kendi PC'nde çalıştığın için sınır yok, model
        # ne kadar sürerse sürsün cevabı bekler, sessizce kesmez.
        r = requests.post(OLLAMA_URL, json=payload, timeout=None)
        return r.json().get("response", "...").strip()
    except requests.exceptions.ConnectionError:
        return ("[Sistem hatası: Ollama'ya bağlanılamadı. 'ollama serve' çalışıyor mu "
                "kontrol et, ya da Ollama uygulamasının açık olduğundan emin ol.]")
    except Exception as e:
        return f"[Sistem hatası: {e}]"


# ─────────────────────────────────────────────
#  İNTERNET ARAMASI
# ─────────────────────────────────────────────
def web_ara(sorgu, max_sonuc=3):
    """ddgs / duckduckgo-search ile arama yapar, kısa bir özet döndürür."""
    DDGS = None
    try:
        from ddgs import DDGS          # yeni paket adı
    except ImportError:
        try:
            from duckduckgo_search import DDGS   # eski paket adı (fallback)
        except ImportError:
            return None, ("❌ Arama kütüphanesi kurulu değil. Kurmak için: "
                           "pip install ddgs")

    try:
        sonuclar = []
        with DDGS() as ddgs:
            for r in ddgs.text(sorgu, max_results=max_sonuc):
                baslik = r.get("title", "")
                ozet   = r.get("body", "")
                url    = r.get("href", "")
                sonuclar.append(f"• {baslik}: {ozet} ({url})")
        if not sonuclar:
            return None, "Arama sonuç vermedi."
        return "\n".join(sonuclar), None
    except Exception as e:
        return None, f"Arama hatası: {e}"


def arama_yap_ve_kaydet(sorgu, kaynak_etiketi="İNTERNET ARAMA (manuel)"):
    print(f"\n🌐 Aranıyor: \"{sorgu}\" ...")
    sonuc, hata = web_ara(sorgu)
    if hata:
        print(f"⚠️  {hata}\n")
        return False
    save_bilgi(f"{kaynak_etiketi}: {sorgu}", sonuc)
    print(f"🔍 GERÇEK KAYNAK KONTROLÜ SONUCU:\n{sonuc}\n")
    return True


# ─────────────────────────────────────────────
#  OTOMATİK GERÇEKLİK KONTROLÜ
#  Kod, konuşmadan kendi arama sorgusunu üretir.
# ─────────────────────────────────────────────
def sorgu_uret_ve_ara(kaynak_etiketi="İNTERNET ARAMA (otomatik)"):
    if not conversation_memory:
        return

    baglam = "\n".join([f"- {m}" for m in conversation_memory[-3:]])
    sorgu_prompt = (
        "Aşağıda bilim insanlarının bir konuşması var. Bu konuşmadaki EN SOMUT, EN TEST "
        "EDİLEBİLİR bilimsel iddiayı veya kavramı bul ve bunu gerçek bir arama motorunda "
        "aranabilecek, en fazla 5 kelimelik bir Türkçe veya İngilizce arama sorgusuna çevir.\n"
        "SADECE sorguyu yaz. Başka hiçbir şey, açıklama, tırnak işareti yazma.\n\n"
        f"Konuşma:\n{baglam}\n\nArama sorgusu:"
    )
    sorgu = generate_response(sorgu_prompt, sicaklik=0.3)
    sorgu = sorgu.strip().strip('"').strip("'").split("\n")[0][:100]

    if not sorgu or sorgu.startswith("["):
        print("⚠️  Otomatik arama sorgusu üretilemedi, bu turu atlıyorum.")
        return

    print(f"\n🤖 Kod kendi sorgusunu üretti: \"{sorgu}\"")
    arama_yap_ve_kaydet(sorgu, kaynak_etiketi)


def otomatik_kontrol_gerekiyor_mu():
    global son_otomatik_arastirma
    if not OTOMATIK_ARASTIRMA:
        return False
    if turn_count == 0 or turn_count == son_otomatik_arastirma:
        return False
    if turn_count % ARASTIRMA_ARALIGI == 0:
        son_otomatik_arastirma = turn_count
        return True
    return False


# ─────────────────────────────────────────────
#  MİMAR (SEN) — KONSOLDAN DİNLEME
# ─────────────────────────────────────────────
def input_listener():
    """Arka planda stdin'i dinler, her satırı kuyruğa atar."""
    while True:
        try:
            line = input()
        except EOFError:
            break
        input_q.put(line)


def handle_mimar_message(msg):
    global turn_count, is_running

    ham = msg.strip()
    komut = ham.lower()

    # Çıkış
    if komut in ("q", "quit", "exit", "çık", "cik"):
        is_running = False
        print("\n👋 Diyalog sonlandırılıyor...\n")
        return

    # Manuel bilgi enjeksiyonu: "bilgi: <metin>"
    if komut.startswith("bilgi:"):
        icerik = ham.split(":", 1)[1].strip()
        if icerik:
            save_bilgi("MİMAR KAYNAĞI", icerik)
            print(f"\n📌 Bilgi havuzuna eklendi:\n{icerik}\n")
        return

    # Manuel internet araması: "ara: <sorgu>"
    if komut.startswith("ara:"):
        sorgu = ham.split(":", 1)[1].strip()
        if sorgu:
            arama_yap_ve_kaydet(sorgu, "İNTERNET ARAMA (manuel)")
        return

    # Manuel tetiklenen ama kodun kendi ürettiği sorguyla gerçeklik kontrolü
    if komut in ("kontrol", "dogrula", "doğrula", "kontrol et"):
        sorgu_uret_ve_ara("İNTERNET ARAMA (manuel tetikli, otomatik sorgu)")
        return

    # Normal mesaj: Mimar sohbete katılıyor
    turn_count += 1
    save_to_book("MİMAR (SEN)", msg, turn_count)
    update_memory("MİMAR", msg)
    print(f"\n[MİMAR // Bölüm {turn_count} // {datetime.datetime.now().strftime('%H:%M:%S')}]")
    print(f"{msg}\n")

    for isim in BOTLAR:
        prompt = (
            CONTEXT[isim] + "\n\n" + get_memory_prompt() +
            f"\n\nMimar sana / gruba şunu söyledi: \"{msg}\"\n"
            f"Şimdi sen {isim} olarak, karakterine sadık kalarak cevap ver."
        )
        print(f"🧠 {isim} düşünüyor...")
        cevap = generate_response(prompt)
        turn_count += 1
        save_to_book(isim, cevap, turn_count)
        update_memory(isim, cevap)
        print(f"[{isim} // Bölüm {turn_count} // {datetime.datetime.now().strftime('%H:%M:%S')}]")
        print(f"{cevap}\n")
        time.sleep(0.3)

    if otomatik_kontrol_gerekiyor_mu():
        sorgu_uret_ve_ara()


# ─────────────────────────────────────────────
#  ANA DİYALOG DÖNGÜSÜ
# ─────────────────────────────────────────────
def conversation_loop():
    global turn_count

    while is_running:
        # Mimar'dan bekleyen bir mesaj/komut var mı? (non-blocking kontrol)
        try:
            msg = input_q.get_nowait()
            handle_mimar_message(msg)
            continue
        except queue.Empty:
            pass

        current = BOTLAR[turn_count % len(BOTLAR)]
        son_konu = f"Son konu: {conversation_memory[-1][:100]}..." if conversation_memory else ""
        prompt = (
            CONTEXT[current] + "\n\n" + get_memory_prompt() + "\n" + son_konu +
            f"\n\nŞimdi sen {current}'sin. Karakterine uygun, kaldığın işi ilerletecek şekilde "
            f"kuantum mekaniği / bilinç / bilim üzerine derinlemesine cevap ver."
        )
        print(f"🧠 {current} düşünüyor...")
        cevap = generate_response(prompt)
        turn_count += 1
        update_memory(current, cevap)
        save_to_book(current, cevap, turn_count)

        print(f"[{current} // Bölüm {turn_count} // {datetime.datetime.now().strftime('%H:%M:%S')}]")
        print(f"{cevap}\n")

        if otomatik_kontrol_gerekiyor_mu():
            sorgu_uret_ve_ara()

        time.sleep(TUR_BEKLEME)


# ─────────────────────────────────────────────
#  BAŞLAT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("  FİZİK DEHALARI — KUANTUM DİYALOĞU (Otomatik Gerçeklik Kontrollü)")
    print("=" * 70)
    print(f"  Model    : {MODEL}")
    print(f"  Hafıza   : Son {MAX_MEMORY} mesaj")
    print(f"  Bilgi    : Son {MAX_BILGI} kayıt (manuel + otomatik arama)")
    print(f"  Otomatik gerçeklik kontrolü: {'AÇIK — her ' + str(ARASTIRMA_ARALIGI) + ' bölümde bir' if OTOMATIK_ARASTIRMA else 'KAPALI'}")
    print("  Katılımcılar: Feynman · Einstein · Bohr")
    print()
    print("  Komutlar:")
    print("    <mesaj>        → Mimar olarak araya gir")
    print("    bilgi: <metin> → Bilgi havuzuna kalıcı referans ekle")
    print("    ara: <sorgu>   → İnternette manuel ara")
    print("    kontrol        → Kod kendi sorgusunu üretip gerçeklik kontrolü yapsın")
    print("    q / exit / çık → Çık")
    print()
    print("  ⚠️  NOT: Bu sistem doğrulanmış yeni fizik keşifleri ÜRETMEZ.")
    print("     Botların sözleri spekülasyondur. 'GERÇEK KAYNAK KONTROLÜ' etiketli")
    print("     kısımlar gerçek internet sonuçlarıdır, geri kalanı değildir.")
    print("=" * 70 + "\n")

    init_book()
    threading.Thread(target=input_listener, daemon=True).start()

    try:
        conversation_loop()
    except KeyboardInterrupt:
        print("\n\n👋 Diyalog durduruldu.")
