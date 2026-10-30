"""
╔══════════════════════════════════════════════════════════════╗
║  AURA-V WEB ARAMA DÜZELTMESİ                                ║
║                                                              ║
║  NEDEN BOZUKTU:                                              ║
║  web_ara()              → Google HTML scraping → 403 HATA   ║
║  dunya_haberlerini...() → Site HTML scraping   → 403 HATA   ║
║                                                              ║
║  ÇÖZÜM:                                                      ║
║  web_ara()              → DDG JSON API + Wikipedia API       ║
║  dunya_haberlerini...() → RSS feed okuma (403 yok)          ║
║                                                              ║
║  KURULUM: pip install feedparser                             ║
║                                                              ║
║  NASIL KULLANILIR:                                           ║
║  aura.py içinde 3244. satırdan itibaren olan                 ║
║  web_sayfa_oku, web_ara, dunya_haberlerini_analiz_et         ║
║  fonksiyonlarını aşağıdakiyle değiştir.                      ║
╚══════════════════════════════════════════════════════════════╝
"""

# ============================================================
# GEREKLİ IMPORT (dosyanın en üstündeki import bloğuna ekle)
# ============================================================
# try:
#     import feedparser
#     FEEDPARSER_MOD = True
# except ImportError:
#     FEEDPARSER_MOD = False
#     print("💡 feedparser kurulu değil (haber RSS): pip install feedparser")

# ============================================================
# HABER KAYNAKLARI — RSS FEED'LERİ (artık HTML değil)
# HTML scraping 403 verir, RSS her zaman açık kalır
# ============================================================
HABER_KAYNAKLARI_RSS = [
    ("BBC Türkçe",    "https://feeds.bbci.co.uk/turkish/rss.xml"),
    ("DW Türkçe",     "https://rss.dw.com/rdf/rss-tur-all"),
    ("Reuters",       "https://feeds.reuters.com/reuters/topNews"),
    ("TechCrunch",    "https://techcrunch.com/feed/"),
    ("The Verge",     "https://www.theverge.com/rss/index.xml"),
]

# ============================================================
# FONKSIYON 1: web_sayfa_oku (değişmedi, ama session eklendi)
# 3244. satırdan itibaren bu fonksiyonu yapıştır
# ============================================================
def web_sayfa_oku(url: str, max_karakter: int = 800) -> str:
    """Bir URL'nin tam metin içeriğini okur — reklamları temizler."""
    if not BS4_MOD:
        return ""
    try:
        # Session + cookie kabul → daha az 403
        session = requests.Session()
        session.headers.update(HEADERS)
        session.headers["Cookie"] = ""
        time.sleep(random.uniform(0.5, 1.5))
        r = session.get(url, timeout=10, allow_redirects=True)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer",
                         "header", "aside", "form", "button"]):
            tag.decompose()

        icerik = ""
        for selector in ["article", "main", ".content", ".post-content",
                         ".article-body", "#content", "body"]:
            bolum = soup.select_one(selector)
            if bolum:
                icerik = bolum.get_text(separator=" ", strip=True)
                break
        if not icerik:
            icerik = soup.get_text(separator=" ", strip=True)

        icerik = re.sub(r"\s{3,}", " ", icerik)
        return icerik[:max_karakter]
    except Exception:
        return ""


# ============================================================
# FONKSIYON 2: web_ara — TAMAMEN YENİDEN YAZILDI
# Strateji: DDG JSON API → Wikipedia API → Sayfa oku
# 3277. satırdan itibaren bu fonksiyonu yapıştır
# ============================================================
def web_ara(sorgu: str, derinlik: int = 1) -> str:
    """
    Çok katmanlı web arama:
    1. DuckDuckGo Instant Answer API  (JSON, ücretsiz, kayıt yok)
    2. Wikipedia Arama API             (TR → EN sırası)
    3. Sayfa oku fallback
    """
    sonuc_parcalari = []

    # ── KATMAN 1: DuckDuckGo Instant Answer API ──────────────
    try:
        ddg_url = (
            "https://api.duckduckgo.com/"
            f"?q={requests.utils.quote(sorgu)}"
            "&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        )
        r = requests.get(ddg_url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            veri = r.json()

            # Doğrudan cevap varsa — en iyi durum
            ozet = veri.get("AbstractText", "").strip()
            if ozet:
                kaynak = veri.get("AbstractURL", "")
                sonuc_parcalari.append(f"📖 {ozet[:400]}")
                if kaynak:
                    sonuc_parcalari.append(f"🔗 Kaynak: {kaynak}")

            # İlgili konular
            if not ozet:
                konular = veri.get("RelatedTopics", [])[:5]
                for konu in konular:
                    if isinstance(konu, dict) and konu.get("Text"):
                        sonuc_parcalari.append(f"• {konu['Text'][:150]}")

            # Tanım varsa ekle
            tanim = veri.get("Definition", "").strip()
            if tanim:
                sonuc_parcalari.append(f"📚 Tanım: {tanim[:200]}")

    except Exception as e:
        pass  # Sessizce sonraki katmana geç

    # ── KATMAN 2: Wikipedia API (TR önce, EN fallback) ───────
    if not sonuc_parcalari:
        for lang, wiki_base in [("tr", "tr.wikipedia.org"), ("en", "en.wikipedia.org")]:
            try:
                # Önce arama yap — doğru sayfa adını bul
                arama_url = (
                    f"https://{wiki_base}/w/api.php"
                    f"?action=query&list=search"
                    f"&srsearch={requests.utils.quote(sorgu)}"
                    f"&format=json&srlimit=1&utf8=1"
                )
                r_arama = requests.get(arama_url, headers=HEADERS, timeout=8)
                if r_arama.status_code != 200:
                    continue

                sonuclar = r_arama.json().get("query", {}).get("search", [])
                if not sonuclar:
                    continue

                sayfa_adi = sonuclar[0]["title"]

                # Sayfa özetini al
                ozet_url = (
                    f"https://{wiki_base}/api/rest_v1/page/summary/"
                    f"{requests.utils.quote(sayfa_adi.replace(' ', '_'))}"
                )
                r_ozet = requests.get(ozet_url, headers=HEADERS, timeout=8)
                if r_ozet.status_code == 200:
                    v = r_ozet.json()
                    aciklama = v.get("extract", "").strip()
                    if aciklama:
                        dil_etiketi = "🇹🇷 Wikipedia" if lang == "tr" else "🇬🇧 Wikipedia (EN)"
                        sonuc_parcalari.append(
                            f"📖 {dil_etiketi} — {sayfa_adi}\n{aciklama[:500]}"
                        )
                        wiki_link = v.get("content_urls", {}).get("desktop", {}).get("page", "")
                        if wiki_link:
                            sonuc_parcalari.append(f"🔗 {wiki_link}")
                        break  # TR bulunduysa EN'e geçme

            except Exception:
                continue

    # ── KATMAN 3: Sayfa oku (derinlik=2 istenirse) ───────────
    if not sonuc_parcalari and derinlik >= 2:
        # Wikipedia'dan direkt oku
        try:
            url_direkt = (
                f"https://tr.wikipedia.org/wiki/"
                f"{requests.utils.quote(sorgu.replace(' ', '_'))}"
            )
            icerik = web_sayfa_oku(url_direkt, max_karakter=600)
            if icerik and len(icerik) > 50:
                sonuc_parcalari.append(f"📄 {icerik}")
        except Exception:
            pass

    # ── SONUÇ ─────────────────────────────────────────────────
    if sonuc_parcalari:
        return "🔍 ARAMA SONUCU:\n" + "\n".join(sonuc_parcalari)

    return (
        "❌ Sonuç bulunamadı.\n"
        "💡 İpucu: Türkçe veya İngilizce anahtar kelime dene.\n"
        f"   Örnek: 'ara: {sorgu} wikipedia'"
    )


# ============================================================
# FONKSIYON 3: dunya_haberlerini_analiz_et — RSS KULLANIR
# 3403. satırdan itibaren bu fonksiyonu yapıştır
# ============================================================
def dunya_haberlerini_analiz_et() -> str:
    """
    RSS feed'lerinden haber çeker.
    HTML scraping yerine RSS — 403 olmaz, her zaman çalışır.
    feedparser kurulu değilse requests ile fallback XML okur.
    """
    try:
        import feedparser
        fp_var = True
    except ImportError:
        fp_var = False

    haberler = []

    for kaynak_adi, rss_url in HABER_KAYNAKLARI_RSS:
        try:
            if fp_var:
                # ── feedparser ile oku (en temiz yol) ──
                feed = feedparser.parse(rss_url)
                for girdi in feed.entries[:4]:
                    baslik = girdi.get("title", "").strip()
                    if baslik and len(baslik) > 10:
                        haberler.append(f"[{kaynak_adi}] {baslik}")
            else:
                # ── feedparser yoksa requests + regex ile oku ──
                r = requests.get(rss_url, headers=HEADERS, timeout=6)
                if r.status_code == 200:
                    # XML'den title etiketlerini çek
                    basliklar = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
                    if not basliklar:
                        basliklar = re.findall(r"<title>(.*?)</title>", r.text)
                    # İlk entry (feed başlığı değil, haberler) genelde 2. başlıktan itibaren
                    for b in basliklar[1:5]:
                        b = b.strip()
                        if b and len(b) > 10:
                            haberler.append(f"[{kaynak_adi}] {b}")
        except Exception:
            continue

    if not haberler:
        return (
            "🌋 Haber alınamadı.\n"
            "💡 Çözüm: pip install feedparser\n"
            "   veya internet bağlantısını kontrol et."
        )

    haberler = list(dict.fromkeys(haberler))[:20]  # Tekrarları kaldır
    metin = "\n".join(f"- {h[:150]}" for h in haberler)

    analiz = aura_sor(
        f"Şu haber başlıklarını analiz et, en önemli 5'ini seç ve yorumla:\n\n{metin}",
        sistem_mesaji="Sen dünya olaylarını analiz eden zeki bir asistansın. Türkçe yaz."
    )
    return f"🌍 AURA-V HABER ANALİZİ:\n\n{analiz}"
