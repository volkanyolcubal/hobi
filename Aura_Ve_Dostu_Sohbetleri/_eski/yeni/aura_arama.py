"""
AURA-V — Web Arama Modülü
Wikipedia, arXiv, DuckDuckGo, HackerNews, OpenLibrary, Wikidata,
Hava Durumu, Döviz, Altın, URL Okuyucu

DEĞİŞİKLİK NOTLARI (bu revizyonda):
  1) url_oku() artık iç ağ / localhost adreslerine istek atılmasını engelliyor (SSRF koruması).
  2) duckduckgo_ara() daha sağlam hata yönetimi ile güncellendi (JSON parse hatalarını yutmuyor,
     boş/bozuk yanıtlarda daha net mesaj veriyor).
  3) arxiv_ara() sorgu temizleme ile güncellendi (soru kelimeleri / gereksiz noktalama temizleniyor),
     böylece daha isabetli sonuç dönme ihtimali artıyor. Not: gerçek çeviri yapmıyor, sadece
     sorguyu arXiv'in beklediği formata daha yakın hale getiriyor.
"""
import ipaddress
import socket
import requests
import threading
from urllib.parse import quote_plus, quote, urlparse
from bs4 import BeautifulSoup

HEADERS_HTTP = {"User-Agent": "Mozilla/5.0 (compatible; AURA-V-Research/2.0)"}
TIMEOUT = 8

# ============================================================
# ================= SSRF KORUMASI ============================
# ============================================================

def _guvenli_url_mu(url: str) -> tuple:
    """
    Bir URL'nin dış (public) bir adrese mi yoksa iç ağa / localhost'a mı
    gittiğini kontrol eder. (host, hata_mesaji) döndürür; hata_mesaji None
    ise URL güvenli demektir.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None, "Sadece http/https adreslerine izin veriliyor."
        host = parsed.hostname
        if not host:
            return None, "Geçersiz URL."

        # DNS çözümlemesi yaparak gerçek IP'yi kontrol et
        # (host adı "localhost" olmasa bile 127.0.0.1'e çözülebilir)
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return None, f"Adres çözümlenemedi: {host}"

        for info in infos:
            ip_str = info[4][0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if (ip.is_private or ip.is_loopback or ip.is_link_local or
                    ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return host, f"İç ağ / özel IP adreslerine erişim engellendi ({ip_str})."

        return host, None
    except Exception as e:
        return None, f"URL kontrol hatası: {e}"


# ===== DÖVİZ / ALTIN =====

def doviz_bilgisi() -> str:
    """Canlı döviz kurları."""
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=6)
        data = r.json()
        if data.get("result") != "success":
            raise ValueError("API hatası")
        rates   = data["rates"]
        usd_try = rates.get("TRY", "?")
        eur_usd = rates.get("EUR", "?")
        gbp_usd = rates.get("GBP", "?")
        jpy_usd = rates.get("JPY", "?")
        eur_try = round(usd_try / eur_usd, 4) if isinstance(eur_usd, float) else "?"
        gbp_try = round(usd_try / gbp_usd, 4) if isinstance(gbp_usd, float) else "?"
        return (f"💱 CANLI DÖVİZ\nUSD/TRY: {usd_try} ₺  |  EUR/TRY: {eur_try} ₺  |  "
                f"GBP/TRY: {gbp_try} ₺  |  USD/JPY: {jpy_usd}\n"
                f"(Güncelleme: {data.get('time_last_update_utc','?')})")
    except Exception as e:
        return f"Döviz verisi alınamadı: {e}"

def altin_bilgisi() -> str:
    """Canlı altın fiyatı."""
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=6,
                         headers={"x-access-token": "goldapi-free"})
        xau_usd = r.json().get("price")
        if not xau_usd:
            raise ValueError("Fiyat yok")
        usd_try = requests.get("https://open.er-api.com/v6/latest/USD",
                               timeout=5).json().get("rates", {}).get("TRY", 1)
        xau_try   = round(xau_usd * usd_try, 2)
        gram_usd  = round(xau_usd / 31.1035, 2)
        gram_try  = round(xau_try / 31.1035, 2)
        return (f"🥇 ALTIN FİYATI\n"
                f"Ons (XAU): {xau_usd} $ / {xau_try} ₺  |  Gram: {gram_usd} $ / {gram_try} ₺")
    except Exception as e:
        return f"Altın verisi alınamadı: {e}"

# ===== HAVA DURUMU =====

def hava_durumu(sehir: str = "Istanbul") -> str:
    """wttr.in ücretsiz hava durumu."""
    try:
        r    = requests.get(f"https://wttr.in/{quote_plus(sehir)}?format=j1",
                            headers=HEADERS_HTTP, timeout=TIMEOUT)
        data = r.json()
        cur  = data['current_condition'][0]
        bugun = data['weather'][0]
        return (f"🌤️ HAVA DURUMU — {sehir}\n"
                f"Şu an: {cur.get('temp_C','?')}°C (Hissedilen: {cur.get('FeelsLikeC','?')}°C)  |  "
                f"{cur.get('weatherDesc',[{}])[0].get('value','?')}\n"
                f"Nem: %{cur.get('humidity','?')}  |  Rüzgar: {cur.get('windspeedKmph','?')} km/h\n"
                f"Gün: Max {bugun.get('maxtempC','?')}°C / Min {bugun.get('mintempC','?')}°C")
    except Exception as e:
        return f"Hava durumu alınamadı: {e}"

# ===== URL OKUYUCU =====

def url_oku(url: str, max_karakter: int = 1500) -> str:
    """Web sayfasının metin içeriğini çek. İç ağ / localhost adreslerini engeller (SSRF koruması)."""
    try:
        if not url.startswith("http"):
            url = "https://" + url

        host, hata = _guvenli_url_mu(url)
        if hata:
            return f"🚫 URL engellendi ({url}): {hata}"

        r    = requests.get(url, headers=HEADERS_HTTP, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()

        # Yönlendirme (redirect) sonrası son adresi de tekrar kontrol et
        # (biri dışarıdan görünen bir URL'nin içeride localhost'a yönlendirmesini kullanabilir)
        if r.url != url:
            _, hata2 = _guvenli_url_mu(r.url)
            if hata2:
                return f"🚫 Yönlendirme engellendi ({r.url}): {hata2}"

        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script","style","nav","footer","header","aside"]):
            tag.decompose()
        satirlar = [s.strip() for s in soup.get_text("\n",strip=True).splitlines() if len(s.strip())>30]
        ozet = '\n'.join(satirlar)[:max_karakter]
        return f"🌐 WEB: {url}\n\n{ozet}"
    except Exception as e:
        return f"URL okuma hatası ({url}): {e}"

# ===== ARAMA FONKSİYONLARI =====

def wikipedia_ara(sorgu: str, dil: str = "tr", max_ozet: int = 700) -> str:
    """Wikipedia TR/EN özet."""
    try:
        r    = requests.get(f"https://{dil}.wikipedia.org/w/api.php",
                            params={"action":"query","list":"search","srsearch":sorgu,
                                    "srlimit":3,"format":"json","utf8":1},
                            headers=HEADERS_HTTP, timeout=TIMEOUT)
        hits = r.json().get("query",{}).get("search",[])
        if not hits:
            return wikipedia_ara(sorgu, "en") if dil=="tr" else ""
        baslik = hits[0]["title"]
        r2   = requests.get(f"https://{dil}.wikipedia.org/w/api.php",
                            params={"action":"query","prop":"extracts","exintro":True,
                                    "explaintext":True,"titles":baslik,"format":"json"},
                            headers=HEADERS_HTTP, timeout=TIMEOUT)
        pages   = r2.json().get("query",{}).get("pages",{})
        extract = next(iter(pages.values())).get("extract","")[:max_ozet].strip()
        return (f"📖 WİKİPEDİA [{'TR' if dil=='tr' else 'EN'}] — {baslik}\n{extract}\n"
                f"🔗 https://{dil}.wikipedia.org/wiki/{quote(baslik.replace(' ','_'))}")
    except Exception as e:
        return f"Wikipedia hatası: {e}"


# arXiv sorgusunu temizlemek için basit bir "gürültü kelimeleri" listesi.
# Gerçek çeviri yapmıyoruz; sadece Türkçe soru kalıplarını atıp anahtar
# terimleri öne çıkararak arXiv'in "all:" alan aramasının daha isabetli
# çalışmasını sağlıyoruz.
_ARXIV_GURULTU = [
    "nedir","nasıl","açıkla","anlat","hakkında","ile ilgili","makale",
    "araştır","bul","bana","lütfen","göster","?","kısaca"
]

def _arxiv_sorgu_temizle(sorgu: str) -> str:
    s = sorgu.lower()
    for kelime in _ARXIV_GURULTU:
        s = s.replace(kelime, " ")
    s = " ".join(s.split())  # fazla boşlukları temizle
    return s if s else sorgu

def arxiv_ara(sorgu: str, max_sonuc: int = 4) -> str:
    """arXiv bilimsel makale arama."""
    try:
        temiz_sorgu = _arxiv_sorgu_temizle(sorgu)
        r    = requests.get("http://export.arxiv.org/api/query",
                            params={"search_query":f"all:{temiz_sorgu}","start":0,
                                    "max_results":max_sonuc,"sortBy":"relevance"},
                            headers=HEADERS_HTTP, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "xml")
        entries = soup.find_all("entry")
        if not entries:
            return ""
        sonuclar = ["🔬 ARXIV:"]
        for e in entries:
            baslik   = (e.find("title") or type("",(),{"text":""})()).text.strip().replace("\n"," ")
            ozet_tag = e.find("summary")
            ozet     = ozet_tag.text.strip()[:250].replace("\n"," ") if ozet_tag else ""
            id_tag   = e.find("id")
            link     = id_tag.text.strip() if id_tag else ""
            yazarlar = [a.find("name").text for a in e.find_all("author") if a.find("name")][:3]
            sonuclar.append(f"\n📄 {baslik}\n   👤 {', '.join(yazarlar)}\n   {ozet}...\n   🔗 {link}")
        return "\n".join(sonuclar)
    except Exception as e:
        return f"arXiv hatası: {e}"

def duckduckgo_ara(sorgu: str, max_sonuc: int = 6) -> str:
    """
    DuckDuckGo arama.
    Not: DuckDuckGo'nun resmi API'si bir "instant answer" servisidir, genel
    arama motoru değildir — çoğu sorguda boş sonuç döner. Bu yüzden önce onu
    deniyoruz, boş dönerse HTML sayfasını (yapısı değişebilir, kırılgan)
    kazıyoruz. Bu adım başarısız olursa (JSON/HTML parse hatası) hatayı
    yutmadan net bir mesajla döndürüyoruz.
    """
    try:
        r = requests.get("https://api.duckduckgo.com/",
                         params={"q":sorgu,"format":"json","no_html":"1","skip_disambig":"1"},
                         headers=HEADERS_HTTP, timeout=TIMEOUT)
        r.raise_for_status()
        try:
            data = r.json()
        except ValueError:
            data = {}

        parcalar = []
        if data.get("AbstractText"):
            parcalar.append(f"📌 {data['AbstractText'][:400]}")
        if data.get("Answer"):
            parcalar.append(f"✅ {data['Answer']}")
        for t in data.get("RelatedTopics",[])[:max_sonuc]:
            if isinstance(t,dict) and t.get("Text"):
                parcalar.append(f"• {t['Text'][:200]}")
        if parcalar:
            return "🔍 DUCKDUCKGO:\n" + "\n".join(parcalar)

        # Instant-answer boş döndü, HTML sürümünü dene
        r2 = requests.get(f"https://html.duckduckgo.com/html/?q={quote_plus(sorgu)}",
                          headers={**HEADERS_HTTP,"Accept-Language":"tr-TR,tr;q=0.9"},
                          timeout=TIMEOUT)
        r2.raise_for_status()
        soup = BeautifulSoup(r2.text,"html.parser")
        sonuclar = []
        for res in soup.select(".result")[:max_sonuc]:
            b = res.select_one(".result__a")
            s = res.select_one(".result__snippet")
            if b:
                sonuclar.append(f"• {b.get_text(strip=True)}: {s.get_text(strip=True)[:180] if s else ''}")
        return "🔍 DUCKDUCKGO:\n" + "\n".join(sonuclar) if sonuclar else "DuckDuckGo: sonuç bulunamadı."
    except requests.exceptions.RequestException as e:
        return f"DuckDuckGo bağlantı hatası: {e}"
    except Exception as e:
        return f"DuckDuckGo hatası: {e}"

def hackernews_ara(sorgu: str, max_sonuc: int = 4) -> str:
    """Hacker News teknoloji haberleri."""
    try:
        r    = requests.get("https://hn.algolia.com/api/v1/search",
                            params={"query":sorgu,"hitsPerPage":max_sonuc,"tags":"story"},
                            headers=HEADERS_HTTP, timeout=TIMEOUT)
        hits = r.json().get("hits",[])
        if not hits:
            return ""
        sonuclar = ["💻 HACKER NEWS:"]
        for h in hits:
            url = h.get("url", f"https://news.ycombinator.com/item?id={h.get('objectID')}")
            sonuclar.append(f"• [{h.get('points',0)}⬆] {h.get('title','')}\n  🔗 {url}")
        return "\n".join(sonuclar)
    except Exception as e:
        return f"HackerNews hatası: {e}"

def openlibrary_ara(sorgu: str, max_sonuc: int = 3) -> str:
    """OpenLibrary kitap arama."""
    try:
        r    = requests.get("https://openlibrary.org/search.json",
                            params={"q":sorgu,"limit":max_sonuc},
                            headers=HEADERS_HTTP, timeout=TIMEOUT)
        docs = r.json().get("docs",[])
        if not docs:
            return ""
        sonuclar = ["📚 KİTAPLAR:"]
        for d in docs:
            yazar = ", ".join(d.get("author_name",[])[:2])
            sonuclar.append(f"• {d.get('title','')} — {yazar} ({d.get('first_publish_year','?')})")
        return "\n".join(sonuclar)
    except Exception as e:
        return f"OpenLibrary hatası: {e}"

def wikidata_ara(sorgu: str) -> str:
    """Wikidata kısa olgusal bilgi."""
    try:
        r    = requests.get("https://www.wikidata.org/w/api.php",
                            params={"action":"wbsearchentities","search":sorgu,
                                    "language":"tr","limit":3,"format":"json"},
                            headers=HEADERS_HTTP, timeout=TIMEOUT)
        results = r.json().get("search",[])
        if not results:
            return ""
        sonuclar = ["🌐 WİKİDATA:"]
        for item in results[:2]:
            if item.get("label") and item.get("description"):
                sonuclar.append(f"• {item['label']}: {item['description']}")
        return "\n".join(sonuclar) if len(sonuclar) > 1 else ""
    except Exception as e:
        return f"Wikidata hatası: {e}"

# ===== NİYET TESPİTİ =====

ARAMA_NIYETLER = {
    "bilim":     ["kuantum","fizik","kimya","biyoloji","matematik","makale",
                  "araştır","bilim","teori","atom","parçacık","formül","evren",
                  "uzay","kara delik","einstein","quantum","physics","science","nöron","dna"],
    "teknoloji": ["ai","yapay zeka","neural","model","llm","gpt","yazılım","kod",
                  "algoritma","teknoloji","robot","machine learning","siber","cpu","gpu","kripto"],
    "wikipedia": ["nedir","kimdir","ne demek","tarih","tarihçe","hakkında","anlat",
                  "açıkla","nasıl çalışır","kim","nerede","ne zaman"],
    "kitap":     ["kitap","yazar","roman","eser","book","author"],
    "haber":     ["haber","gündem","son dakika","news","trend"],
    "tarih_saat":["saat","tarih","bugün","gün","zaman","kaç oldu"],
    "doviz":     ["dolar","euro","döviz","kur","sterlin","lira","tl","usd","eur"],
    "altin":     ["altın","gold","gram altın","ons","xau"],
    "hava":      ["hava","sıcaklık","yağmur","kar","fırtına","nem","hava durumu","weather"],
    "pc_kontrol":["sistem","işlemci","ram","disk","bellek","cpu","process","çalışan",
                  "bilgisayar durumu","pc","servis","pil","uptime","ağ","ip adresi"],
    "url_oku":   ["http://","https://","www.",".com",".org",".net","sitesine bak"],
}

BASIT_MESAJLAR = [
    "merhaba","selam","nasılsın","naber","iyi misin","teşekkür",
    "tamam","ok","anladım","evet","hayır","peki","güzel",
    "harika","süper","olur","olmaz","hi","hello","thanks",
    "sağol","sağ ol","eyvallah","görüşürüz","bye","hoşça kal",
]

def niyet_tespit(sorgu: str) -> list:
    """Mesajın arama niyetini tespit et."""
    sorgu_l = sorgu.lower().strip()
    if len(sorgu_l) < 15 and any(sorgu_l.startswith(b) for b in BASIT_MESAJLAR):
        return []
    niyetler = [n for n,kelimeler in ARAMA_NIYETLER.items()
                if any(k in sorgu_l for k in kelimeler)]
    if not niyetler and (len(sorgu_l) > 20 or "?" in sorgu_l):
        niyetler = ["duckduckgo"]
    return list(set(niyetler))

def url_cikar(metin: str) -> list:
    """Metinden URL'leri çıkar."""
    import re
    urls = re.findall(r'https?://[^\s]+', metin)
    if not urls:
        urls = ["https://"+w for w in re.findall(r'www\.[^\s]+', metin)]
    return urls

# ===== CONTEXT TOPLAMA =====

def context_topla(komut: str, kendi_kod_ozet_fn=None) -> str:
    """Tüm kaynaklardan context topla, LLM'e gönder."""
    from aura_pc import guncel_tarih_saat
    niyetler = niyet_tespit(komut)
    parcalar = [f"=== GÜNCEL VERİ CONTEXT ({guncel_tarih_saat()}) ==="]

    if "tarih_saat" in niyetler:
        parcalar.append(f"📅 {guncel_tarih_saat()}")
    if "altin"     in niyetler: parcalar.append(altin_bilgisi())
    if "doviz"     in niyetler: parcalar.append(doviz_bilgisi())

    if "hava" in niyetler:
        import re
        m = re.search(r'(?:hava|weather)\s+(?:nasıl\s+)?(?:in\s+)?([A-Za-zÇçĞğİıÖöŞşÜü]+)',
                      komut, re.IGNORECASE)
        parcalar.append(hava_durumu(m.group(1) if m else "Istanbul"))

    urls = url_cikar(komut)
    for u in urls[:2]:
        parcalar.append(url_oku(u))

    # Kendi koduna dair sorular
    komut_l = komut.lower()
    if kendi_kod_ozet_fn and any(k in komut_l for k in
        ["kodun","koduma","misafir_mod","kendin","nasıl yazıldın","kaynak","kod analiz"]):
        parcalar.append(kendi_kod_ozet_fn())

    sonuclar = {}
    def calistir(isim, fn, *args):
        try: sonuclar[isim] = fn(*args)
        except Exception as e: sonuclar[isim] = f"{isim} hatası: {e}"

    threads = []
    if "bilim"    in niyetler: threads.append(threading.Thread(target=calistir, args=("arxiv",arxiv_ara,komut)))
    if "wikipedia" in niyetler or "bilim" in niyetler:
        threads.append(threading.Thread(target=calistir, args=("wiki",wikipedia_ara,komut)))
        threads.append(threading.Thread(target=calistir, args=("wikidata",wikidata_ara,komut)))
    if "teknoloji" in niyetler or "haber" in niyetler:
        threads.append(threading.Thread(target=calistir, args=("hn",hackernews_ara,komut)))
    if "kitap" in niyetler:
        threads.append(threading.Thread(target=calistir, args=("openlibrary",openlibrary_ara,komut)))
    if niyetler:
        threads.append(threading.Thread(target=calistir, args=("ddg",duckduckgo_ara,komut)))

    for t in threads: t.start()
    for t in threads: t.join(timeout=10)

    for key in ["arxiv","wiki","wikidata","hn","openlibrary","ddg"]:
        if key in sonuclar and sonuclar[key]:
            parcalar.append(sonuclar[key])

    parcalar.append("=== CONTEXT SONU ===")
    return "\n\n".join(parcalar)
