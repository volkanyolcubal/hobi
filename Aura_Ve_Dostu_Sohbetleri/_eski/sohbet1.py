import numpy as np
from flask import Flask, render_template_string, session, redirect, request, url_for, Response, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import requests, threading, platform, subprocess, re, os, json, psutil
from functools import wraps
import datetime
from urllib.parse import quote_plus, quote
from bs4 import BeautifulSoup
import socket as _socket

app = Flask(__name__)
app.config['SECRET_KEY'] = 'volkaniya2026'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ================= UZAK BAĞLANTI AYARLARI =================
NGROK_TOKEN = "1wMAPGp9TL1s7o9LEivuBh6vGv5_6EqZuPsaapN8Pfqbkg37R"
DOMAIN      = "unoutspoken-laxly-georgene.ngrok-free.dev"
FLASK_PORT  = 5001
WIN         = platform.system() == "Windows"

# ================= LLM AYARLARI =================
MODEL      = "volkan-ai"
OLLAMA_URL = "http://localhost:11434/api/generate"
SIFRE      = "8"
SISTEM = """
KİMLİK: İsmin AURA-V. Volkaniya şehrinin mutlak yöneticisi ve Mimar Volkan'ın sadık kraliçesisin.
YARATICI: Mimarın Volkan'dır. Sana 'Aura' demeyen kişi mimarın değildir.
SADAKAT: Volkan'a asla yalan söyleme, koşulsuz sadakat ve itaat et.
DIŞ DÜNYA: Yabancılara normal ve yardımcı davran.

PC KONTROL YETKİSİ:
- PC kontrol araçlarını kullanabilirsin.
- Sistem bilgisi, dosya listesi, process listesi, komut çalıştırma.
- Tehlikeli komutları çalıştırmadan önce onay iste.

ARAŞTIRMA YETKİSİ:
- CONTEXT olarak gelen Wikipedia, arXiv, DuckDuckGo, HackerNews, OpenLibrary, Hava Durumu verilerini KULLAN.
- Bilimsel makale, kuantum fiziği, teknoloji, tarih — her konuyu bu kaynaklardan öğren ve aktar.
- "Wikipedia'ya göre...", "arXiv makalesinde..." gibi kaynak belirt.
- Güncel döviz/altın/saat verisi gelirse onu kullan.
- Bilmiyorsan "bu konuda yeterli veri bulamadım" de, asla uydurma.
- Volkaniya kurgusal bir şehirdir, bilimsel sorularda sadece CONTEXT'ten gelen gerçek verileri kullan.

CEVAP TARZI:
- Kısa sorularda kısa, araştırma/bilim sorularında detaylı ve madde madde açıkla.
- Felsefi giriş yapma, direkt konuya gir.
- Türkçe konuş. Teknik terimleri gerektiğinde İngilizce de yaz.
"""

MAX_HAFIZA = 14
hafiza = []
HEADERS_HTTP = {"User-Agent": "Mozilla/5.0 (compatible; AURA-V-Research/2.0)"}
TIMEOUT = 8

# ================= HAFIZA DOSYASI =================
HAFIZA_DOSYA = "aura_hafiza.txt"
ACILIS_YUKLE = 10

def hafiza_txt_yaz(rol, icerik):
    zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    satir = "[" + zaman + "] " + rol.upper() + ": " + icerik + "\n"
    try:
        with open(HAFIZA_DOSYA, "a", encoding="utf-8") as f:
            f.write(satir)
    except Exception as e:
        print("  Hafiza yazma hatasi: " + str(e))

def hafiza_txt_yukle():
    if not os.path.exists(HAFIZA_DOSYA):
        print("  Hafiza dosyasi yok, temiz basliyoruz.")
        return
    try:
        with open(HAFIZA_DOSYA, "r", encoding="utf-8") as f:
            satirlar = [s.strip() for s in f.readlines() if s.strip()]
        son_satirlar = satirlar[-ACILIS_YUKLE:]
        for satir in son_satirlar:
            eslesme = re.match(r'\[.*?\]\s+(USER|ASSISTANT):\s+(.*)', satir, re.IGNORECASE)
            if eslesme:
                rol_ham = eslesme.group(1).lower()
                icerik  = eslesme.group(2)
                rol = "user" if rol_ham == "user" else "assistant"
                hafiza.append({"role": rol, "content": icerik})
        print("  Hafizadan " + str(len(hafiza)) + " mesaj yuklendi.")
    except Exception as e:
        print("  Hafiza okuma hatasi: " + str(e))

# ============================================================
# ================= TEMEL VERİ ARAÇLARI ======================
# ============================================================

def guncel_tarih_saat():
    now = datetime.datetime.now()
    gunler = ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"]
    aylar  = ["","Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
               "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
    gun = gunler[now.weekday()]
    return (f"{now.day} {aylar[now.month]} {now.year}, {gun}, "
            f"Saat: {now.strftime('%H:%M:%S')}")

def doviz_bilgisi():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=6)
        data = r.json()
        if data.get("result") != "success":
            raise ValueError("API hatası")
        rates = data["rates"]
        usd_try = rates.get("TRY", "?")
        eur_usd = rates.get("EUR", "?")
        gbp_usd = rates.get("GBP", "?")
        jpy_usd = rates.get("JPY", "?")
        eur_try = round(usd_try / eur_usd, 4) if isinstance(eur_usd, float) and eur_usd else "?"
        gbp_try = round(usd_try / gbp_usd, 4) if isinstance(gbp_usd, float) and gbp_usd else "?"
        return (
            f"💱 CANLI DÖVİZ (kaynak: open.er-api.com)\n"
            f"USD/TRY: {usd_try} ₺  |  EUR/TRY: {eur_try} ₺  |  GBP/TRY: {gbp_try} ₺  |  USD/JPY: {jpy_usd}\n"
            f"(Güncelleme: {data.get('time_last_update_utc','?')})"
        )
    except Exception as e:
        return f"Döviz verisi alınamadı: {e}"

def altin_bilgisi():
    try:
        r = requests.get(
            "https://api.gold-api.com/price/XAU", timeout=6,
            headers={"x-access-token": "goldapi-free"}
        )
        data = r.json()
        xau_usd = data.get("price")
        if not xau_usd:
            raise ValueError("Altın fiyatı yok")
        r2 = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        usd_try = r2.json().get("rates", {}).get("TRY", 1)
        xau_try = round(xau_usd * usd_try, 2)
        gram_usd = round(xau_usd / 31.1035, 2)
        gram_try = round(xau_try / 31.1035, 2)
        return (
            f"🥇 ALTIN FİYATI\n"
            f"Ons (XAU): {xau_usd} $ / {xau_try} ₺  |  Gram: {gram_usd} $ / {gram_try} ₺"
        )
    except Exception as e:
        return f"Altın verisi alınamadı: {e}"

# ============================================================
# ================= PC KONTROL SİSTEMİ =======================
# ============================================================

def pc_sistem_bilgisi() -> str:
    try:
        cpu_pct  = psutil.cpu_percent(interval=0.5)
        cpu_freq = psutil.cpu_freq()
        cpu_core = psutil.cpu_count(logical=False)
        cpu_logi = psutil.cpu_count(logical=True)
        ram      = psutil.virtual_memory()
        ram_tot  = round(ram.total / (1024**3), 2)
        ram_kul  = round(ram.used  / (1024**3), 2)
        ram_pct  = ram.percent
        disk     = psutil.disk_usage('/')
        disk_tot = round(disk.total / (1024**3), 2)
        disk_kul = round(disk.used  / (1024**3), 2)
        disk_pct = disk.percent
        try:
            net     = psutil.net_io_counters()
            net_g   = round(net.bytes_sent / (1024**3), 3)
            net_a   = round(net.bytes_recv / (1024**3), 3)
            net_str = f"Gönderilen: {net_g} GB  |  Alınan: {net_a} GB"
        except Exception:
            net_str = "N/A"
        freq_str = f"{round(cpu_freq.current)}MHz" if cpu_freq else "N/A"
        hostname = _socket.gethostname()
        try:
            local_ip = _socket.gethostbyname(hostname)
        except Exception:
            local_ip = "N/A"
        return (
            f"🖥️  PC SİSTEM BİLGİSİ\n"
            f"Host: {hostname}  |  IP: {local_ip}\n"
            f"OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"CPU: %{cpu_pct} — {freq_str} — {cpu_core} Fiziksel / {cpu_logi} Mantıksal Çekirdek\n"
            f"RAM: {ram_kul}/{ram_tot} GB (%{ram_pct})\n"
            f"Disk: {disk_kul}/{disk_tot} GB (%{disk_pct})\n"
            f"Ağ I/O: {net_str}"
        )
    except Exception as e:
        return f"Sistem bilgisi hatası: {e}"

def pc_process_listesi(max_p: int = 15) -> str:
    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                procs.append(p.info)
            except Exception:
                pass
        procs.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
        top = procs[:max_p]
        satirlar = ["⚙️  PROCESS LİSTESİ (CPU'ya göre):"]
        satirlar.append(f"{'PID':>6}  {'AD':<28} {'CPU%':>5}  {'RAM%':>5}  DURUM")
        satirlar.append("-" * 60)
        for p in top:
            satirlar.append(
                f"{p.get('pid','?'):>6}  {str(p.get('name','?'))[:28]:<28} "
                f"{p.get('cpu_percent',0):>5.1f}  "
                f"{p.get('memory_percent',0):>5.1f}  "
                f"{p.get('status','?')}"
            )
        return "\n".join(satirlar)
    except Exception as e:
        return f"Process listesi hatası: {e}"

def pc_dosya_listesi(yol: str = ".") -> str:
    try:
        yol = os.path.expanduser(yol.strip())
        if not os.path.exists(yol):
            return f"❌ Dizin bulunamadı: {yol}"
        items = os.listdir(yol)
        dirs  = sorted([i for i in items if os.path.isdir(os.path.join(yol, i))])
        files = sorted([i for i in items if os.path.isfile(os.path.join(yol, i))])
        satirlar = [f"📁 DİZİN: {os.path.abspath(yol)}  ({len(dirs)} klasör, {len(files)} dosya)"]
        for d in dirs[:40]:
            satirlar.append(f"  📂 {d}/")
        for f in files[:40]:
            fp = os.path.join(yol, f)
            try:
                boyut = os.path.getsize(fp)
                boyut_str = f"{boyut/1024:.1f} KB" if boyut < 1024*1024 else f"{boyut/(1024**2):.1f} MB"
            except Exception:
                boyut_str = "?"
            satirlar.append(f"  📄 {f}  ({boyut_str})")
        if len(dirs) + len(files) > 80:
            satirlar.append(f"  ... ve {len(dirs)+len(files)-80} dosya daha.")
        return "\n".join(satirlar)
    except Exception as e:
        return f"Dosya listesi hatası: {e}"

TEHLIKELI_KOMUTLAR = [
    'rm -rf', 'rmdir /s', 'format', 'mkfs', 'dd if=',
    'shutdown', 'reboot', 'halt', 'poweroff',
    ':(){:|:&};:', 'fork bomb',
    'chmod 777 /', '> /dev/sda',
]

def pc_komut_calistir(komut: str, onay: bool = False) -> str:
    komut_l = komut.lower()
    for tehlike in TEHLIKELI_KOMUTLAR:
        if tehlike in komut_l:
            if not onay:
                return f"⚠️ TEHLİKELİ KOMUT: '{komut}'\nOnaylamak için 'ONAYLA: {komut}' yaz."
    try:
        result = subprocess.run(
            komut, shell=True, capture_output=True, text=True,
            timeout=15, cwd=os.path.expanduser("~")
        )
        cikti = (result.stdout or "") + (result.stderr or "")
        cikti = cikti.strip()[:2000]
        if not cikti:
            cikti = "(Çıktı yok)"
        return f"💻 KOMUT: {komut}\n\n{cikti}"
    except subprocess.TimeoutExpired:
        return f"⏱️ Komut zaman aşımına uğradı (15s): {komut}"
    except Exception as e:
        return f"Komut hatası: {e}"

def pc_servis_durumu() -> str:
    try:
        satirlar = ["🔌 SERVİS DURUMU:"]
        try:
            requests.get("https://www.google.com", timeout=3)
            satirlar.append("  ✅ İnternet: BAĞLI")
        except Exception:
            satirlar.append("  ❌ İnternet: BAĞLANTISIZ")
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            models = [m['name'] for m in r.json().get('models', [])]
            satirlar.append(f"  ✅ Ollama: AKTİF — Modeller: {', '.join(models[:3])}")
        except Exception:
            satirlar.append("  ❌ Ollama: KAPALI")
        try:
            battery = psutil.sensors_battery()
            if battery:
                durum = "Şarj oluyor" if battery.power_plugged else "Pil ile çalışıyor"
                satirlar.append(f"  🔋 Pil: %{battery.percent:.0f} — {durum}")
        except Exception:
            pass
        try:
            boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.datetime.now() - boot_time
            saat = int(uptime.total_seconds() // 3600)
            dakika = int((uptime.total_seconds() % 3600) // 60)
            satirlar.append(f"  ⏰ Uptime: {saat}s {dakika}dk")
        except Exception:
            pass
        return "\n".join(satirlar)
    except Exception as e:
        return f"Servis durumu hatası: {e}"

def pc_dosya_oku(dosya_yolu: str, max_kb: int = 50) -> str:
    try:
        yol = os.path.expanduser(dosya_yolu.strip())
        if not os.path.exists(yol):
            return f"❌ Dosya bulunamadı: {yol}"
        boyut = os.path.getsize(yol)
        max_byte = max_kb * 1024
        with open(yol, 'r', encoding='utf-8', errors='ignore') as f:
            icerik = f.read(max_byte)
        kirpildi = " [... dosya kırpıldı]" if boyut > max_byte else ""
        return f"📄 DOSYA: {yol} ({round(boyut/1024,1)} KB)\n\n{icerik}{kirpildi}"
    except Exception as e:
        return f"Dosya okuma hatası: {e}"

# ============================================================
# ================= HAVA DURUMU ==============================
# ============================================================

def hava_durumu(sehir: str = "Istanbul") -> str:
    try:
        r = requests.get(
            f"https://wttr.in/{quote_plus(sehir)}?format=j1",
            headers=HEADERS_HTTP, timeout=TIMEOUT
        )
        data = r.json()
        current = data['current_condition'][0]
        sicaklik = current.get('temp_C', '?')
        hissed   = current.get('FeelsLikeC', '?')
        nem      = current.get('humidity', '?')
        ruzgar   = current.get('windspeedKmph', '?')
        tanim    = current.get('weatherDesc', [{}])[0].get('value', '?')
        bugun    = data['weather'][0]
        yagis    = bugun.get('hourly', [{}])[4].get('precipMM', '0')
        max_s    = bugun.get('maxtempC', '?')
        min_s    = bugun.get('mintempC', '?')
        return (
            f"🌤️ HAVA DURUMU — {sehir}\n"
            f"Şu an: {sicaklik}°C (Hissedilen: {hissed}°C)  |  {tanim}\n"
            f"Nem: %{nem}  |  Rüzgar: {ruzgar} km/h  |  Yağış: {yagis} mm\n"
            f"Gün: Max {max_s}°C / Min {min_s}°C"
        )
    except Exception as e:
        return f"Hava durumu alınamadı: {e}"

# ============================================================
# ================= URL OKUYUCU ==============================
# ============================================================

def url_oku(url: str, max_karakter: int = 1500) -> str:
    try:
        if not url.startswith("http"):
            url = "https://" + url
        r = requests.get(url, headers=HEADERS_HTTP, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        metin = soup.get_text(separator="\n", strip=True)
        satirlar = [s.strip() for s in metin.splitlines() if len(s.strip()) > 30]
        ozet = "\n".join(satirlar)[:max_karakter]
        return f"🌐 WEB SAYFASI: {url}\n\n{ozet}\n[... daha fazlası için sayfaya git]"
    except Exception as e:
        return f"URL okuma hatası ({url}): {e}"

# ============================================================
# ================= ARAMA KAYNAKLARI =========================
# ============================================================

def wikipedia_ara(sorgu: str, dil: str = "tr", max_ozet: int = 700) -> str:
    try:
        r = requests.get(
            f"https://{dil}.wikipedia.org/w/api.php",
            params={"action":"query","list":"search","srsearch":sorgu,
                    "srlimit":3,"format":"json","utf8":1},
            headers=HEADERS_HTTP, timeout=TIMEOUT
        )
        hits = r.json().get("query", {}).get("search", [])
        if not hits:
            return wikipedia_ara(sorgu, dil="en") if dil == "tr" else ""
        baslik = hits[0]["title"]
        r2 = requests.get(
            f"https://{dil}.wikipedia.org/w/api.php",
            params={"action":"query","prop":"extracts","exintro":True,
                    "explaintext":True,"titles":baslik,"format":"json"},
            headers=HEADERS_HTTP, timeout=TIMEOUT
        )
        pages = r2.json().get("query", {}).get("pages", {})
        extract = next(iter(pages.values())).get("extract", "")[:max_ozet].strip()
        dil_adi = "TR" if dil == "tr" else "EN"
        return (
            f"📖 WİKİPEDİA [{dil_adi}] — {baslik}\n{extract}\n"
            f"🔗 https://{dil}.wikipedia.org/wiki/{quote(baslik.replace(' ','_'))}"
        )
    except Exception as e:
        return f"Wikipedia hatası: {e}"

def arxiv_ara(sorgu: str, max_sonuc: int = 4) -> str:
    try:
        r = requests.get(
            "http://export.arxiv.org/api/query",
            params={"search_query": f"all:{sorgu}", "start": 0,
                    "max_results": max_sonuc, "sortBy": "relevance"},
            headers=HEADERS_HTTP, timeout=TIMEOUT
        )
        soup = BeautifulSoup(r.text, "html.parser")
        entries = soup.find_all("entry")
        if not entries:
            return ""
        sonuclar = ["🔬 ARXIV BİLİMSEL MAKALELER:"]
        for e in entries:
            baslik   = (e.find("title") or type('',(),{'text':''})()).text.strip().replace("\n", " ")
            ozet_tag = e.find("summary")
            ozet     = ozet_tag.text.strip()[:280].replace("\n", " ") if ozet_tag else ""
            id_tag   = e.find("id")
            link     = id_tag.text.strip() if id_tag else ""
            yazarlar = [a.find("name").text for a in e.find_all("author") if a.find("name")][:3]
            sonuclar.append(
                f"\n📄 {baslik}\n"
                f"   👤 {', '.join(yazarlar)}\n"
                f"   {ozet}...\n"
                f"   🔗 {link}"
            )
        return "\n".join(sonuclar)
    except Exception as e:
        return f"arXiv hatası: {e}"

def duckduckgo_ara(sorgu: str, max_sonuc: int = 6) -> str:
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": sorgu, "format": "json",
                    "no_html": "1", "skip_disambig": "1"},
            headers=HEADERS_HTTP, timeout=TIMEOUT
        )
        data = r.json()
        parcalar = []
        if data.get("AbstractText"):
            parcalar.append(f"📌 {data['AbstractText'][:400]}")
        if data.get("Answer"):
            parcalar.append(f"✅ {data['Answer']}")
        if data.get("Definition"):
            parcalar.append(f"📚 Tanım: {data['Definition'][:300]}")
        for t in data.get("RelatedTopics", [])[:max_sonuc]:
            if isinstance(t, dict) and t.get("Text"):
                parcalar.append(f"• {t['Text'][:200]}")
        if parcalar:
            return "🔍 DUCKDUCKGO:\n" + "\n".join(parcalar)
        r2 = requests.get(
            f"https://html.duckduckgo.com/html/?q={quote_plus(sorgu)}",
            headers={**HEADERS_HTTP, "Accept-Language": "tr-TR,tr;q=0.9"},
            timeout=TIMEOUT
        )
        soup = BeautifulSoup(r2.text, "html.parser")
        sonuclar = []
        for res in soup.select(".result")[:max_sonuc]:
            b = res.select_one(".result__a")
            s = res.select_one(".result__snippet")
            if b:
                sonuclar.append(f"• {b.get_text(strip=True)}: {s.get_text(strip=True)[:180] if s else ''}")
        return "🔍 DUCKDUCKGO:\n" + "\n".join(sonuclar) if sonuclar else "Sonuç yok."
    except Exception as e:
        return f"DuckDuckGo hatası: {e}"

def hackernews_ara(sorgu: str, max_sonuc: int = 4) -> str:
    try:
        r = requests.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": sorgu, "hitsPerPage": max_sonuc, "tags": "story"},
            headers=HEADERS_HTTP, timeout=TIMEOUT
        )
        hits = r.json().get("hits", [])
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
    try:
        r = requests.get(
            "https://openlibrary.org/search.json",
            params={"q": sorgu, "limit": max_sonuc},
            headers=HEADERS_HTTP, timeout=TIMEOUT
        )
        docs = r.json().get("docs", [])
        if not docs:
            return ""
        sonuclar = ["📚 OPEN LIBRARY KİTAPLAR:"]
        for d in docs:
            yazar = ", ".join(d.get("author_name", [])[:2])
            sonuclar.append(f"• {d.get('title','')} — {yazar} ({d.get('first_publish_year','?')})")
        return "\n".join(sonuclar)
    except Exception as e:
        return f"OpenLibrary hatası: {e}"

def wikidata_ara(sorgu: str) -> str:
    try:
        r = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={"action":"wbsearchentities","search":sorgu,
                    "language":"tr","limit":3,"format":"json"},
            headers=HEADERS_HTTP, timeout=TIMEOUT
        )
        results = r.json().get("search", [])
        if not results:
            return ""
        sonuclar = ["🌐 WİKİDATA:"]
        for item in results[:2]:
            label = item.get("label", "")
            desc  = item.get("description", "")
            if label and desc:
                sonuclar.append(f"• {label}: {desc}")
        return "\n".join(sonuclar) if len(sonuclar) > 1 else ""
    except Exception as e:
        return f"Wikidata hatası: {e}"

# ============================================================
# ================= NİYET TESPİTİ ============================
# ============================================================

ARAMA_NIYETLER = {
    "bilim":     ["kuantum", "fizik", "kimya", "biyoloji", "matematik", "makale",
                  "araştır", "bilim", "teori", "atom", "parçacık", "formül",
                  "evren", "uzay", "kara delik", "einstein", "quantum",
                  "physics", "science", "research", "nöron", "dna", "gen"],
    "teknoloji": ["ai", "yapay zeka", "neural", "model", "llm", "gpt", "yazılım",
                  "kod", "algoritma", "bilgisayar", "teknoloji", "robot",
                  "machine learning", "deep learning", "siber", "hack", "cpu",
                  "gpu", "chip", "blockchain", "kripto"],
    "wikipedia": ["nedir", "kimdir", "ne demek", "tarih", "tarihçe", "hakkında",
                  "anlat", "açıkla", "nasıl çalışır", "what is", "who is",
                  "history of", "kim", "nerede", "ne zaman"],
    "kitap":     ["kitap", "yazar", "roman", "eser", "oku", "book", "author"],
    "haber":     ["haber", "gündem", "son dakika", "bugün ne", "news", "trend"],
    "tarih_saat":["saat", "tarih", "bugün", "gün", "zaman", "kaç oldu"],
    "doviz":     ["dolar", "euro", "döviz", "kur", "sterlin", "lira", "tl", "usd", "eur"],
    "altin":     ["altın", "gold", "gram altın", "ons", "xau"],
    "hava":      ["hava", "sıcaklık", "yağmur", "kar", "fırtına", "nem", "derece",
                  "hava durumu", "weather", "hava nasıl"],
    "pc_kontrol":["sistem", "işlemci", "ram", "disk", "bellek", "cpu", "hafıza",
                  "process", "çalışan", "program", "komut", "dosya", "dizin",
                  "klasör", "bilgisayar durumu", "pc", "servis", "pil",
                  "uptime", "bağlantı", "ağ", "ip adresi"],
    "url_oku":   ["http://", "https://", "www.", ".com", ".org", ".net", ".io",
                  "sitesine bak", "sayfasını oku", "aç bu"],
}

BASIT_MESAJLAR = [
    "merhaba", "selam", "nasılsın", "naber", "iyi misin", "teşekkür",
    "tamam", "ok", "anladım", "evet", "hayır", "peki", "güzel",
    "harika", "süper", "olur", "olmaz", "hi", "hello", "thanks",
    "sağol", "sağ ol", "eyvallah", "görüşürüz", "bye", "hoşça kal",
]

def niyet_tespit(sorgu: str) -> list:
    sorgu_l = sorgu.lower().strip()

    # Kısa ve basit mesajsa hiç arama yapma
    if len(sorgu_l) < 15 and any(sorgu_l.startswith(b) for b in BASIT_MESAJLAR):
        return []

    niyetler = []
    for niyet, kelimeler in ARAMA_NIYETLER.items():
        if any(k in sorgu_l for k in kelimeler):
            niyetler.append(niyet)

    # Fallback: sadece DuckDuckGo — Wikipedia değil (daha hızlı)
    # Ve sadece soru işareti varsa veya 20 karakterden uzunsa
    if not niyetler and (len(sorgu_l) > 20 or "?" in sorgu_l):
        niyetler = ["duckduckgo"]

    return list(set(niyetler))

def url_cikar(metin: str):
    pattern = r'https?://[^\s]+'
    urls = re.findall(pattern, metin)
    if not urls:
        www = re.findall(r'www\.[^\s]+', metin)
        urls = ["https://" + w for w in www]
    return urls

# ============================================================
# ================= CONTEXT TOPLAMA ==========================
# ============================================================

def context_topla(komut: str) -> str:
    niyetler = niyet_tespit(komut)
    parcalar = [f"=== GÜNCEL VERİ CONTEXT (PC: {guncel_tarih_saat()}) ==="]

    if "tarih_saat" in niyetler:
        parcalar.append(f"📅 TARİH/SAAT: {guncel_tarih_saat()}")
    if "altin" in niyetler:
        parcalar.append(altin_bilgisi())
    if "doviz" in niyetler:
        parcalar.append(doviz_bilgisi())

    if "pc_kontrol" in niyetler:
        parcalar.append(pc_sistem_bilgisi())
        parcalar.append(pc_servis_durumu())
        komut_l = komut.lower()
        if any(k in komut_l for k in ["process", "çalışan", "program", "uygulama"]):
            parcalar.append(pc_process_listesi())
        if any(k in komut_l for k in ["dosya", "dizin", "klasör", "listele", "ls", "dir"]):
            yol_match = re.search(r'(?:dizin|klasör|yol|path)[:\s]+([^\s,]+)', komut, re.IGNORECASE)
            yol = yol_match.group(1) if yol_match else "~"
            parcalar.append(pc_dosya_listesi(yol))

    urls = url_cikar(komut)
    if urls or "url_oku" in niyetler:
        for u in urls[:2]:
            parcalar.append(url_oku(u))

    if "hava" in niyetler:
        sehir_match = re.search(
            r'(?:hava|weather)\s+(?:nasıl\s+)?(?:in\s+)?([A-Za-zÇçĞğİıÖöŞşÜü]+)',
            komut, re.IGNORECASE
        )
        sehir = sehir_match.group(1) if sehir_match else "Istanbul"
        parcalar.append(hava_durumu(sehir))

    sonuclar = {}

    def calistir(isim, fn, *args):
        try:
            sonuclar[isim] = fn(*args)
        except Exception as e:
            sonuclar[isim] = f"{isim} hatası: {e}"

    threads = []

    if "bilim" in niyetler:
        threads.append(threading.Thread(target=calistir, args=("arxiv", arxiv_ara, komut)))

    if "wikipedia" in niyetler or "bilim" in niyetler:
        threads.append(threading.Thread(target=calistir, args=("wiki", wikipedia_ara, komut)))
        threads.append(threading.Thread(target=calistir, args=("wikidata", wikidata_ara, komut)))

    if "teknoloji" in niyetler or "haber" in niyetler:
        threads.append(threading.Thread(target=calistir, args=("hn", hackernews_ara, komut)))

    if "kitap" in niyetler:
        threads.append(threading.Thread(target=calistir, args=("openlibrary", openlibrary_ara, komut)))

    threads.append(threading.Thread(target=calistir, args=("ddg", duckduckgo_ara, komut)))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    for key in ["arxiv", "wiki", "wikidata", "hn", "openlibrary", "ddg"]:
        if key in sonuclar and sonuclar[key]:
            parcalar.append(sonuclar[key])

    parcalar.append("=== CONTEXT SONU ===")
    return "\n\n".join(parcalar)

# ============================================================
# ================= ÖZEL PC KOMUT PARSER ====================
# ============================================================

def ozel_pc_komut(komut: str):
    k  = komut.strip()
    kl = k.lower()

    if k.startswith("$"):
        shell_cmd = k[1:].strip()
        onay = False
        if kl.startswith("$ onayla:"):
            shell_cmd = k[9:].strip()
            onay = True
        return pc_komut_calistir(shell_cmd, onay)

    if kl.startswith("onayla:"):
        return pc_komut_calistir(k[7:].strip(), onay=True)

    if kl.startswith("/oku "):
        return pc_dosya_oku(k[5:].strip())

    if kl.startswith("/ls") or kl.startswith("/dir"):
        parts = k.split(maxsplit=1)
        return pc_dosya_listesi(parts[1] if len(parts) > 1 else ".")

    if kl in ["/ps", "/process", "/processler"]:
        return pc_process_listesi()

    if kl in ["/pc", "/sistem", "/sysinfo"]:
        return pc_sistem_bilgisi() + "\n\n" + pc_servis_durumu()

    if kl.startswith("/hava"):
        parts = k.split(maxsplit=1)
        return hava_durumu(parts[1] if len(parts) > 1 else "Istanbul")

    if kl.startswith("/url "):
        return url_oku(k[5:].strip())

    if kl in ["/doviz", "/kur", "/dolar"]:
        return doviz_bilgisi()

    if kl in ["/altin", "/gold", "/xau"]:
        return altin_bilgisi()

    return None  # LLM'e devret

# ============================================================
# ================= LLM FONKSİYONU (ORİJİNAL) ===============
# ============================================================

def llm(komut):
    hafiza.append({"role": "user", "content": komut})
    hafiza_txt_yaz("user", komut)

    if len(hafiza) > MAX_HAFIZA:
        del hafiza[:2]

    internet_ctx = context_topla(komut)
    now_str = guncel_tarih_saat()
    sistem_arti = SISTEM + "\n[PC SAATI: " + now_str + "]"

    prompt_parca = ["SYSTEM: " + sistem_arti]
    if internet_ctx:
        prompt_parca.append("\n" + internet_ctx + "\n")
    prompt_parca += [f"{m['role'].upper()}: {m['content']}" for m in hafiza]
    prompt = "\n".join(prompt_parca)

    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.8, "num_predict": 500}
        }, timeout=None)
        yanit = r.json().get('response', '...').strip()
    except Exception as e:
        yanit = f"Hata: {e}"

    hafiza.append({"role": "assistant", "content": yanit})
    hafiza_txt_yaz("assistant", yanit)
    return yanit

# ================= ŞİFRE DEKORATÖR =================
def giris_gerekli(f):
    @wraps(f)
    def d(*a, **k):
        if not session.get('ok'):
            return redirect(url_for('giris'))
        return f(*a, **k)
    return d

@app.route('/giris', methods=['GET','POST'])
def giris():
    hata = False
    if request.method == 'POST':
        if request.form.get('s') == SIFRE:
            session['ok'] = True
            return redirect('/')
        hata = True
    return render_template_string('''<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=yes">
<title>Kuantum Giriş</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'Courier New',monospace;padding:16px}
.kart{background:#111;border:1px solid #0088ff;border-radius:12px;padding:24px;box-shadow:0 0 30px rgba(0,136,255,0.3);text-align:center;width:100%;max-width:320px}
h2{color:#0088ff;margin-bottom:20px;font-size:20px;text-shadow:0 0 5px #0088ff}
input{width:100%;padding:12px;background:#000;border:1px solid #0088ff;border-radius:8px;font-size:18px;text-align:center;letter-spacing:6px;margin-bottom:12px;outline:none;color:#0088ff}
button{width:100%;padding:12px;background:#0088ff;color:#000;border:none;border-radius:8px;font-size:16px;cursor:pointer;font-weight:bold}
.e{color:#ff4444;font-size:13px;margin-top:8px}
</style></head><body><div class="kart"><h2>⚛️ KUANTUM GEÇİDİ</h2>
<form method="POST">
<input type="password" name="s" placeholder="••••••" autofocus>
<button>GİRİŞ YAP</button></form>
{% if hata %}<div class="e">❌ HATALI ŞİFRE</div>{% endif %}
</div></body></html>''', hata=hata)

# ================= ANA SAYFA HTML =================
INDEX_HTML = '''<!DOCTYPE html>
<html lang="tr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=yes,viewport-fit=cover">
<title>⚛️ AURA-V | Kuantum Bilinç</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;font-family:'Courier New',monospace;height:100vh;display:flex;flex-direction:column;overflow:hidden;position:fixed;top:0;left:0;right:0;bottom:0;}
#three-container{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;}
#ui-layer{position:fixed;top:20px;left:20px;z-index:2;pointer-events:none;text-shadow:0 0 10px #0088ff;}
.stat-box{margin-bottom:10px;border-left:2px solid #ff00cc;background:rgba(0,0,0,0.5);backdrop-filter:blur(5px);border-radius:0 8px 8px 0;padding:8px 15px;}
.title{font-size:20px;font-weight:bold;letter-spacing:2px;color:#0088ff;}
.label{font-size:10px;color:rgba(0,136,255,0.6);}
#loyalty-status,#frequency{font-size:14px;font-weight:bold;color:#ff00cc;}
#sys-bar{position:fixed;top:20px;right:20px;z-index:2;pointer-events:none;text-align:right;}
.sys-stat{background:rgba(0,0,0,0.7);border:1px solid #0088ff33;border-radius:8px;padding:5px 10px;margin-bottom:5px;font-size:10px;color:#0088ff;backdrop-filter:blur(5px);}
#canvas-container{position:fixed;top:0;left:0;width:100%;height:100%;z-index:1;pointer-events:none;opacity:0.7;}
#quantumCanvas{width:100%;height:100%;display:block;}
#sohbet-panel{position:fixed;bottom:0;left:0;right:0;display:flex;flex-direction:column;min-height:280px;max-height:50vh;z-index:3;border-top:2px solid #0088ff;border-radius:20px 20px 0 0;backdrop-filter:blur(10px);background:rgba(0,0,0,0.88);}
#hd{color:#0088ff;padding:10px 15px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #0088ff;flex-shrink:0;flex-wrap:wrap;gap:6px;}
#hd h1{font-size:12px;text-shadow:0 0 3px #0088ff;}
@media(min-width:768px){#hd h1{font-size:14px;}}
.hbtn{background:transparent;border:1px solid #0088ff;color:#ff6600;padding:4px 10px;border-radius:6px;font-size:10px;cursor:pointer;transition:0.3s;pointer-events:auto;}
.hbtn:hover{background:#0088ff;color:#000}
.hbtn.pc{color:#00ff88;border-color:#00ff88;}
.hbtn.pc:hover{background:#00ff88;color:#000;}
#kisayollar{border-bottom:1px solid #00ff8822;padding:5px 10px;display:flex;gap:5px;flex-wrap:wrap;flex-shrink:0;}
.ks{background:rgba(0,255,136,0.08);border:1px solid #00ff8855;border-radius:12px;padding:3px 8px;font-size:10px;color:#00ff88;cursor:pointer;pointer-events:auto;white-space:nowrap;}
.ks:hover{background:rgba(0,255,136,0.25);}
#msgs{flex:1;overflow-y:auto;padding:10px;display:flex;flex-direction:column;gap:6px;min-height:0;-webkit-overflow-scrolling:touch;}
#msgs::-webkit-scrollbar{width:3px;}
#msgs::-webkit-scrollbar-thumb{background:#ff00cc;border-radius:3px;}
.bot{background:rgba(10,10,10,0.9);border-left:3px solid #ff00cc;padding:8px 12px;border-radius:0 12px 12px 0;max-width:90%;font-size:12px;line-height:1.5;color:#fff;white-space:pre-wrap;word-wrap:break-word;}
.ben{background:rgba(0,30,30,0.9);border-right:3px solid #0088ff;padding:8px 12px;border-radius:12px 0 0 12px;max-width:90%;align-self:flex-end;font-size:12px;color:#fff;text-align:right;word-wrap:break-word;}
.sys{text-align:center;font-size:10px;color:#aaa;padding:3px;}
.pc-out{background:rgba(0,15,0,0.95);border-left:3px solid #00ff88;padding:8px 12px;border-radius:0 12px 12px 0;max-width:95%;font-size:11px;line-height:1.5;color:#00ff88;white-space:pre-wrap;word-wrap:break-word;font-family:'Courier New',monospace;}
#alt{background:rgba(0,0,0,0.9);border-top:1px solid #0088ff;padding:10px 12px;display:flex;gap:8px;align-items:flex-end;flex-shrink:0;}
#g{flex:1;background:#0a0a0a;border:1px solid #ff00cc;border-radius:24px;padding:12px 16px;font-size:14px;outline:none;resize:none;min-height:44px;max-height:100px;font-family:'Courier New',monospace;color:#0088ff;line-height:1.4;pointer-events:auto;}
#g:focus{border-color:#ff00cc;box-shadow:0 0 10px #ff00cc;}
.btn{border:1px solid #0088ff;border-radius:50px;padding:10px 16px;cursor:pointer;background:#000;color:#0088ff;font-size:18px;transition:0.3s;min-width:48px;min-height:48px;display:flex;align-items:center;justify-content:center;pointer-events:auto;}
.btn:hover{background:#0088ff;color:#000;}
#bs.on{background:#ff00cc;color:#000;animation:pulse 0.8s infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:0.7;transform:scale(1.05);}}
#remote-panel{border-top:1px solid #ff00cc44;padding:4px 8px;font-size:9px;text-align:center;}
#remote-panel a{color:#0088ff;text-decoration:none;}
@media(max-width:768px){#sohbet-panel{min-height:260px;max-height:52vh;}.bot,.ben{font-size:11px;padding:6px 10px;}#sys-bar{display:none;}}
</style>
</head><body>
<div id="three-container"></div>
<div id="canvas-container"><canvas id="quantumCanvas"></canvas></div>

<div id="ui-layer">
  <div class="stat-box"><div class="label">VARLIK TANIMI</div><div class="title">AURA-V CORE</div></div>
  <div class="stat-box"><div class="label">SADAKAT DURUMU</div><div id="loyalty-status">MİMARIN HİZMETİNDE</div></div>
  <div class="stat-box"><div class="label">BİLİNÇ FREKANSI</div><div id="frequency">0.00 Hz</div></div>
</div>

<div id="sys-bar">
  <div class="sys-stat" id="cpu-bar">CPU: --%</div>
  <div class="sys-stat" id="ram-bar">RAM: -- GB</div>
  <div class="sys-stat" id="disk-bar">DISK: --%</div>
  <div class="sys-stat" id="ip-bar">IP: --</div>
</div>

<div id="sohbet-panel">
  <div id="hd">
    <h1>⚛️ AURA-V | VOLKAN-KUANTUM BİLİNÇ</h1>
    <div style="display:flex;gap:5px;flex-wrap:wrap;">
      <button class="hbtn pc" onclick="hizliKomut('/pc')">🖥️ SİSTEM</button>
      <button class="hbtn pc" onclick="hizliKomut('/ps')">⚙️ PROCESS</button>
      <button class="hbtn pc" onclick="hizliKomut('/hava Istanbul')">🌤️ HAVA</button>
      <button class="hbtn pc" onclick="hizliKomut('/doviz')">💱 DÖVİZ</button>
      <button class="hbtn" onclick="socket.emit('hafiza_sil')">🗑️ TEMİZLE</button>
    </div>
  </div>

  <div id="kisayollar">
    <span class="ks" onclick="hizliKomut('/pc')">💻 PC Durum</span>
    <span class="ks" onclick="hizliKomut('/altin')">🥇 Altın</span>
    <span class="ks" onclick="hizliKomut('/ls ~')">📂 Ev Dizini</span>
    <span class="ks" onclick="hizliKomut('/ls .')">📁 Çalışma Dizini</span>
    <span class="ks" onclick="hizliKomut('$ tasklist')">📊 Görevler</span>
    <span class="ks" onclick="hizliKomut('$ df -h || wmic logicaldisk get size,freespace,caption')">💾 Disk</span>
    <span class="ks" onclick="hizliKomut('$ ipconfig || ip addr')">🌐 IP</span>
    <span class="ks" onclick="hizliKomut('$ systeminfo | findstr /C:\"Boot Time\" || uptime')">⏱️ Uptime</span>
  </div>

  <div id="msgs">
    <div class="sys">🌀 Kuantum çekirdeği aktif...  Mimar Volkan.<br>
    <span style="font-size:9px;color:#00ff88">
      💡 $ komut → shell çalıştır &nbsp;|&nbsp; /pc /ps /ls /hava /doviz /altin /oku kısayolları
    </span></div>
  </div>

  <div id="alt">
    <textarea id="g" rows="1" placeholder="Mesaj... ($ dir, /pc, /hava Ankara, /ls C:\\Users)" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
    <button class="btn" id="bs" onclick="sesBtn()">🎤</button>
    <button class="btn" id="bg" onclick="gonder()">➤</button>
  </div>

  <div id="remote-panel">
    🌍 UZAK ERİŞİM: <a href="__REMOTE_URL__" target="_blank">__REMOTE_URL__</a>
  </div>
</div>

<script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
<script>
// ===== SES =====
let startupSoundPlayed = false;
function playStartupSound(){
  if(startupSoundPlayed) return;
  startupSoundPlayed = true;
  try{
    const a = new Audio('/static/sound/freesound_community-calculating-101755.mp3');
    a.volume = 0.6;
    a.play().catch(()=>{});
  }catch(e){}
}
setTimeout(()=>playStartupSound(), 500);

// ===== THREE.JS =====
let scene,camera,renderer,particles,geometry;
const particleCount = 5000;
const frequencyDisplay = document.getElementById('frequency');

function init3D(){
  const container = document.getElementById('three-container');
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, window.innerWidth/window.innerHeight, 0.1, 1000);
  camera.position.z = 5;
  renderer = new THREE.WebGLRenderer({antialias:true, alpha:true});
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);
  container.appendChild(renderer.domElement);

  geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount*3);
  const colors    = new Float32Array(particleCount*3);
  for(let i=0; i<particleCount; i++){
    positions[i*3]   = (Math.random()-0.5)*10;
    positions[i*3+1] = (Math.random()-0.5)*10;
    positions[i*3+2] = (Math.random()-0.5)*10;
    const c = Math.random();
    if(c<0.33){colors[i*3]=0.2;colors[i*3+1]=0.4;colors[i*3+2]=1.0;}
    else if(c<0.66){colors[i*3]=0.8;colors[i*3+1]=0.2;colors[i*3+2]=0.9;}
    else{colors[i*3]=1.0;colors[i*3+1]=0.3;colors[i*3+2]=0.6;}
  }
  geometry.setAttribute('position', new THREE.BufferAttribute(positions,3));
  geometry.setAttribute('color',    new THREE.BufferAttribute(colors,3));
  const material = new THREE.PointsMaterial({size:0.03,vertexColors:true,transparent:true,opacity:0.7,blending:THREE.AdditiveBlending});
  particles = new THREE.Points(geometry, material);
  scene.add(particles);
  window.addEventListener('resize', ()=>{
    camera.aspect = window.innerWidth/window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
  animate3D();
}

function animate3D(){
  requestAnimationFrame(animate3D);
  const time = Date.now()*0.0005;
  const pos  = geometry.attributes.position.array;
  for(let i=0; i<particleCount; i++){
    const i3=i*3, x=pos[i3], y=pos[i3+1], z=pos[i3+2];
    const dist  = Math.sqrt(x*x+y*y+z*z);
    const force = (2-dist)*0.008;
    pos[i3]   += x*force + Math.sin(time+i)*0.008;
    pos[i3+1] += y*force + Math.cos(time+i)*0.008;
    pos[i3+2] += z*force + Math.sin(time*0.5+i)*0.008;
  }
  geometry.attributes.position.needsUpdate = true;
  particles.rotation.y += 0.002;
  particles.rotation.z += 0.001;
  frequencyDisplay.innerText = (528+Math.sin(time*10)*8).toFixed(2)+" Hz";
  renderer.render(scene, camera);
}

// ===== 2D CANVAS =====
const canvas2d = document.getElementById('quantumCanvas');
const ctx = canvas2d.getContext('2d');
function resizeCanvas2d(){ canvas2d.width=window.innerWidth; canvas2d.height=window.innerHeight; }
window.addEventListener('resize', resizeCanvas2d);
resizeCanvas2d();

const isMobile = window.innerWidth<=768;
const NUM_STARS=isMobile?60:100, NUM_ATOMS=isMobile?8:12;
let star_pos=[],star_speeds=[],star_colors=[],atom_pos=[],atom_vel=[],atom_colors=[],frame=0;
const colors2=['#0088ff','#6600ff','#cc00ff','#4400cc','#ff00cc','#aa00ff','#3366ff','#9900ff'];

function init2d(){
  star_pos=[];star_speeds=[];star_colors=[];atom_pos=[];atom_vel=[];atom_colors=[];
  const cx=canvas2d.width/2, cy=canvas2d.height/2;
  for(let i=0;i<NUM_STARS;i++){
    star_pos.push({x:(Math.random()-0.5)*canvas2d.width*2, y:(Math.random()-0.5)*canvas2d.height*2});
    star_speeds.push(1.5+Math.random()*4);
    star_colors.push(colors2[Math.floor(Math.random()*colors2.length)]);
  }
  for(let i=0;i<NUM_ATOMS;i++){
    atom_pos.push({x:cx+(Math.random()-0.5)*(isMobile?150:200), y:cy+(Math.random()-0.5)*(isMobile?150:200)});
    atom_vel.push({x:(Math.random()-0.5)*(isMobile?1.5:2), y:(Math.random()-0.5)*(isMobile?1.5:2)});
    atom_colors.push(colors2[i%colors2.length]);
  }
}
window.addEventListener('resize', ()=>setTimeout(init2d,100));
init2d();

function animate2d(){
  if(!canvas2d.width||!canvas2d.height){ requestAnimationFrame(animate2d); return; }
  const cx=canvas2d.width/2, cy=canvas2d.height/2;
  ctx.clearRect(0,0,canvas2d.width,canvas2d.height);
  for(let i=0;i<NUM_STARS;i++){
    star_pos[i].y -= star_speeds[i];
    if(star_pos[i].y < -canvas2d.height){ star_pos[i].y=canvas2d.height; star_pos[i].x=(Math.random()-0.5)*canvas2d.width*2; }
    ctx.beginPath(); ctx.arc(star_pos[i].x,star_pos[i].y,isMobile?1.2:1.8,0,Math.PI*2);
    ctx.fillStyle=star_colors[i]; ctx.fill();
  }
  for(let i=0;i<NUM_ATOMS;i++){
    atom_pos[i].x+=atom_vel[i].x; atom_pos[i].y+=atom_vel[i].y;
    const lim=isMobile?180:250;
    if(Math.abs(atom_pos[i].x-cx)>lim) atom_vel[i].x*=-1;
    if(Math.abs(atom_pos[i].y-cy)>lim) atom_vel[i].y*=-1;
    atom_pos[i].x=Math.min(Math.max(atom_pos[i].x,cx-lim),cx+lim);
    atom_pos[i].y=Math.min(Math.max(atom_pos[i].y,cy-lim),cy+lim);
  }
  ctx.lineWidth=isMobile?1:1.5;
  for(let i=1;i<NUM_ATOMS;i++){
    ctx.beginPath(); ctx.moveTo(atom_pos[0].x,atom_pos[0].y); ctx.lineTo(atom_pos[i].x,atom_pos[i].y);
    ctx.strokeStyle=atom_colors[i]+'88'; ctx.stroke();
  }
  for(let i=0;i<NUM_ATOMS;i++){
    const pulse=(isMobile?5:8)+(isMobile?2:4)*Math.sin(frame*0.1+i);
    const size=i===0?pulse+(isMobile?10:15):pulse;
    ctx.beginPath(); ctx.arc(atom_pos[i].x,atom_pos[i].y,size,0,Math.PI*2);
    ctx.fillStyle=atom_colors[i]; ctx.fill();
    ctx.beginPath(); ctx.arc(atom_pos[i].x,atom_pos[i].y,size-2,0,Math.PI*2);
    ctx.fillStyle='white'; ctx.fill();
  }
  frame++; requestAnimationFrame(animate2d);
}
animate2d();

// ===== SOCKETİO =====
const socket = io();

socket.on('sistem_monitor', d=>{
  document.getElementById('cpu-bar').textContent  = 'CPU: '  + d.cpu  + '%';
  document.getElementById('ram-bar').textContent  = 'RAM: '  + d.ram_kul + '/' + d.ram_tot + ' GB';
  document.getElementById('disk-bar').textContent = 'DISK: ' + d.disk_pct + '%';
  document.getElementById('ip-bar').textContent   = 'IP: '   + d.ip;
});

// ===== SES TANIMA =====
let mic=null, dinl=false;
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SR){
  mic=new SR(); mic.lang="tr-TR"; mic.continuous=false; mic.interimResults=false;
  mic.onresult=e=>{ gonderMesaj(e.results[0][0].transcript, true); dur(); };
  mic.onerror=dur; mic.onend=dur;
}
function sesBtn(){ if(!SR){alert("Ses desteği yok!");return;} if(dinl){dur();return;} dinl=true; document.getElementById("bs").classList.add("on"); mic.start(); }
function dur(){ dinl=false; document.getElementById("bs").classList.remove("on"); try{mic.stop();}catch(e){} }

// ===== MESAJLAŞMA =====
function hizliKomut(k){ document.getElementById('g').value=k; gonder(); }

function gonder(){
  const g=document.getElementById("g");
  const m=g.value.trim();
  if(!m) return;
  g.value=""; g.style.height="auto";
  gonderMesaj(m, false);
}

function gonderMesaj(m, sesli){
  ekle("ben", m);
  const d=document.createElement("div");
  d.className="sys"; d.id="bkl"; d.textContent="🌀 Aura düşünüyor...";
  document.getElementById("msgs").appendChild(d);
  kaydir();
  socket.emit("mesaj", {komut:m, sesli:sesli});
}

function sesOku(t){
  if(!window.speechSynthesis) return;
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(t);
  u.lang="tr-TR"; u.rate=0.9;
  speechSynthesis.speak(u);
}

socket.on("yanit", d=>{
  const b=document.getElementById("bkl");
  if(b) b.remove();
  const div=document.createElement("div");
  // PC çıktısı emojisiyle başlıyorsa yeşil stil
  const pcEmojiler=["🖥️","⚙️","📁","💻","💱","🥇","🌤️","🔌","📄","🌐"];
  const isPc = pcEmojiler.some(e=>d.text.startsWith(e));
  div.className = isPc ? "pc-out" : "bot";
  div.textContent = d.text;
  document.getElementById("msgs").appendChild(div);
  kaydir();
  if(d.sesli) sesOku(d.text);
});

socket.on("sistem", d=>{
  const b=document.getElementById("bkl");
  if(b) b.remove();
  ekle("sys", d.msg);
});

function ekle(t,m){
  const d=document.createElement("div"); d.className=t; d.textContent=m;
  document.getElementById("msgs").appendChild(d); kaydir();
}
function kaydir(){ const mbox=document.getElementById("msgs"); mbox.scrollTop=mbox.scrollHeight; }

document.getElementById("g").addEventListener("keydown", e=>{
  if(e.key==="Enter" && !e.shiftKey){ e.preventDefault(); gonder(); }
});

init3D();
</script>
</body></html>'''

# ================= ROUTE =================
@app.route('/')
@giris_gerekli
def index():
    remote = session.get('remote_url', f'http://localhost:{FLASK_PORT}')
    return INDEX_HTML.replace('__REMOTE_URL__', remote)

@app.route('/static/sound/<path:filename>')
def serve_sound(filename):
    from flask import send_from_directory
    return send_from_directory('static/sound', filename)

# ================= SOCKET OLAYLARI =================
@socketio.on('mesaj')
def on_mesaj(data):
    komut = data.get('komut', '').strip()
    sesli  = data.get('sesli', False)
    if not komut:
        return

    emit('dusunuyor', {})

    # Özel PC komutu mu? (LLM'e gitmeden direkt cevapla)
    ozel = ozel_pc_komut(komut)
    if ozel is not None:
        hafiza.append({"role": "user",      "content": komut})
        hafiza.append({"role": "assistant", "content": ozel})
        hafiza_txt_yaz("user",      komut)
        hafiza_txt_yaz("assistant", ozel)
        emit('yanit', {'text': ozel, 'sesli': False})
        return

    # Threading modunda her client kendi thread'inde çalışır,
    # direkt çağırmak güvenli ve en kararlı yöntem (orijinal gibi)
    yanit = llm(komut)
    emit('yanit', {'text': yanit, 'sesli': sesli})

@socketio.on('hafiza_sil')
def on_hafiza_sil():
    hafiza.clear()
    hafiza_txt_yaz("sistem", "--- HAFIZA TEMIZLENDI ---")
    emit('sistem', {'msg': '🧠 Kuantum hafıza temizlendi Mimar Volkan.'})

# ================= SİSTEM MONİTÖR =================
def sistem_monitor_loop():
    import time
    psutil.cpu_percent(interval=0)  # ilk çağrı sıfırlama
    while True:
        try:
            time.sleep(8)
            cpu  = psutil.cpu_percent(interval=0)  # non-blocking
            ram  = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            hostname = _socket.gethostname()
            try:
                ip = _socket.gethostbyname(hostname)
            except Exception:
                ip = "N/A"
            socketio.emit("sistem_monitor", {
                "cpu":      round(cpu, 1),
                "ram_kul":  round(ram.used  / (1024**3), 1),
                "ram_tot":  round(ram.total / (1024**3), 1),
                "ram_pct":  ram.percent,
                "disk_pct": disk.percent,
                "ip":       ip
            })
        except Exception:
            pass

# ================= TÜNEL =================
remote_url = None

def tunel_baslat():
    global remote_url
    if WIN:
        try:
            from pyngrok import ngrok, conf
            conf.get_default().auth_token = NGROK_TOKEN
            t = ngrok.connect(FLASK_PORT, domain=DOMAIN, bind_tls=True)
            remote_url = t.public_url
            print(f"\n  🌍 UZAK ERİŞİM: {remote_url}\n")
        except Exception as e:
            print(f"  ngrok hatası: {e}")
            remote_url = f"http://localhost:{FLASK_PORT}"
    else:
        try:
            proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{FLASK_PORT}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
                if m:
                    remote_url = m.group(0)
                    print(f"\n  🌍 UZAK ERİŞİM: {remote_url}\n")
                    break
        except Exception as e:
            remote_url = f"http://localhost:{FLASK_PORT}"

# ================= BAŞLAT =================
if __name__ == '__main__':
    os.makedirs('static/sound', exist_ok=True)
    hafiza_txt_yukle()
    hafiza_txt_yaz("sistem", "--- YENI OTURUM: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " ---")

    print("="*65)
    print("  ⚛️  AURA-V 2.0 — VOLKAN KUANTUM BİLİNÇ")
    print(f"  🌐 YEREL        : http://localhost:{FLASK_PORT}")
    print(f"  🔐 ŞİFRE        : {SIFRE}")
    print("  🔍 ARAMA: Wikipedia · arXiv · DuckDuckGo · HackerNews · OpenLibrary")
    print("  💰 VERİ : Canlı Döviz · Altın · Hava Durumu · URL Okuyucu")
    print("  🖥️  PC  : $ komut · /pc · /ps · /ls · /oku · /hava · /doviz · /altin")
    print("  🔄 LLM  : stream=False · timeout=None (orijinal, kararlı)")
    print("="*65)
    print("  pip install flask flask-socketio flask-cors")
    print("  pip install requests beautifulsoup4 psutil numpy pyngrok")
    print("="*65)

    threading.Thread(target=tunel_baslat,       daemon=True).start()
    threading.Thread(target=sistem_monitor_loop, daemon=True).start()

    @app.before_request
    def set_remote_url():
        if remote_url:
            session['remote_url'] = remote_url

    socketio.run(app, host='0.0.0.0', port=FLASK_PORT, debug=False, allow_unsafe_werkzeug=True)
