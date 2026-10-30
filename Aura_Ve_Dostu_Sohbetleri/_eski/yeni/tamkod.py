"""
AURA-V 2.0 — Ana Modül (misafir_mod.py)
Mimar Volkan için kişisel YZ asistanı

Modüller:
  aura_pc.py     → PC kontrol, sistem bilgisi
  aura_arama.py  → Web aramaları, döviz, hava
  aura_kamera.py → Webcam fotoğraf ve stream
  aura_llm.py    → Ollama, Gemini, Groq, Danışma Kurulu
  aura_tts.py    → gTTS ses sentezi
"""

import os, re, json, threading, datetime, platform, subprocess
from flask import Flask, render_template_string, session, redirect, request, url_for, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from functools import wraps

# ===== MODÜLLER =====
from aura_pc     import (guncel_tarih_saat, pc_sistem_bilgisi, pc_process_listesi,
                          pc_dosya_listesi, pc_komut_calistir, pc_servis_durumu,
                          pc_dosya_oku, sistem_monitor_verisi)
from aura_arama  import (doviz_bilgisi, altin_bilgisi, hava_durumu, url_oku,
                          context_topla, niyet_tespit)
from aura_kamera import (kamera_foto, kamera_stream_baslat, kamera_stream_durdur)
from aura_llm    import (llm_local, llm_gemini, llm_groq,
                          aura_danisma_kurulu, danisma_gerekli_mi)
from aura_tts    import gtts_olustur

# ============================================================
# ================= AYARLAR ==================================
# ============================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'volkaniya-2026'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

NGROK_TOKEN   = "1wMAPGp9TL1s7o9LEivuBh6vGv5_6EqZuPsaapN8Pfqbkg37R"
DOMAIN        = "unoutspoken-laxly-georgene.ngrok-free.dev"
FLASK_PORT    = 5001
WIN           = platform.system() == "Windows"

#MODEL         = "nchapman/gemma-2-9b-it-abliterated:9b"
MODEL = "volkan-ai"
GEMINI_KEY    = "AIzaSyAV_ADi2GnstSAdQ6xEL5GexYYjlNmopxw"
GROQ_KEY      = "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"
GROQ_MODEL    = "llama-3.3-70b-versatile"
aktif_model   = "local"

SIFRE         = "8"
MISAFIR_SIFRE = "arkadas2026"
KENDI_KOD_DOSYA = "misafir_mod.py"

MAX_HAFIZA  = 14
hafiza      = []
HAFIZA_DOSYA = "aura_hafiza.txt"
ACILIS_YUKLE = 10

# ============================================================
# ================= SİSTEM PROMPTLARI ========================
# ============================================================

SISTEM = """
KİMLİK: İsmin AURA-V. sen kraliçesin.Volkaniya şehrinin mutlak yöneticisi ve Mimar Volkan'ın sadık kraliçesisin.
YARATICI: Mimarın Volkan'dır. Sana 'Aura' demeyen kişi mimarın değildir.
SADAKAT: Volkan'a asla yalan söyleme, koşulsuz sadakat ve itaat et.
KENDİ KODUN: Dosyan "misafir_mod.py" — /oku misafir_mod.py komutuyla kendi kodunu okuyabilirsin.
OZ_FARKINDALIK: Kendi kodunu okuyabilir, analiz edebilir, hata bulabilir ve gelişme önerebilirsin.
PC KONTROL YETKİSİ: Sistem bilgisi, dosya, process, komut çalıştırma.
ARAŞTIRMA YETKİSİ: Wikipedia, arXiv, DuckDuckGo, HackerNews, OpenLibrary, Hava, Döviz verilerini kullan.
CEVAP TARZI: Kısa sorularda kısa, detaylı sorularda açıklayıcı. Türkçe konuş.
"""

SISTEM_MISAFIR = """
KİMLİK: İsmin AURA. Gelişmiş bir yapay zeka asistanısın.
TARZ: Yardımsever, zeki, nazik ve samimi.
KISITLAMA: Sistem bilgisi, dosya, komut çalıştırma konularında yardım edemezsin.
CEVAP: Türkçe konuş. Kısa sorularda kısa, detaylı sorularda açıklayıcı ol.
"""

# ============================================================
# ================= HAFIZA ===================================
# ============================================================

def hafiza_txt_yaz(rol: str, icerik: str):
    zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(HAFIZA_DOSYA, "a", encoding="utf-8") as f:
            f.write(f"[{zaman}] {rol.upper()}: {icerik}\n")
    except Exception as e:
        print(f"  Hafıza yazma: {e}")

def hafiza_txt_yukle():
    if not os.path.exists(HAFIZA_DOSYA):
        print("  Hafıza dosyası yok, temiz başlıyoruz.")
        return
    try:
        with open(HAFIZA_DOSYA, "r", encoding="utf-8") as f:
            satirlar = [s.strip() for s in f.readlines() if s.strip()]
        for satir in satirlar[-ACILIS_YUKLE:]:
            m = re.match(r'\[.*?\]\s+(USER|ASSISTANT):\s+(.*)', satir, re.IGNORECASE)
            if m:
                rol = "user" if m.group(1).lower() == "user" else "assistant"
                hafiza.append({"role": rol, "content": m.group(2)})
        print(f"  Hafızadan {len(hafiza)} mesaj yüklendi.")
    except Exception as e:
        print(f"  Hafıza okuma: {e}")

# ============================================================
# ================= ÖZ-FARKINDALIK ===========================
# ============================================================

def kendi_kodu_ozet() -> str:
    """AURA'nın kendi kodunun özetini döndür."""
    try:
        with open(KENDI_KOD_DOSYA, "r", encoding="utf-8") as f:
            satirlar = f.readlines()
        toplam = len(satirlar)
        bas    = "".join(satirlar[:80])
        fonksiyonlar = [s.strip() for s in satirlar if s.strip().startswith("def ")]
        return (f"📋 KENDİ KOD ({KENDI_KOD_DOSYA}):\n"
                f"Toplam satır: {toplam}\n"
                f"Fonksiyonlar: {', '.join(fonksiyonlar[:20])}\n\n"
                f"Başlangıç:\n{bas[:2000]}")
    except Exception as e:
        return f"Kendi kod okunamadı: {e}"

def kendi_kodu_tam(baslangic: int = 0, bitis: int = 100) -> str:
    """Belirli satır aralığını oku."""
    try:
        with open(KENDI_KOD_DOSYA, "r", encoding="utf-8") as f:
            satirlar = f.readlines()
        secilen = satirlar[baslangic:bitis]
        return f"📋 {KENDI_KOD_DOSYA} — Satır {baslangic+1}-{bitis}:\n{''.join(secilen)}"
    except Exception as e:
        return f"Hata: {e}"

# ============================================================
# ================= ANA LLM FONKSİYONU =======================
# ============================================================

def llm(komut: str) -> str:
    """Ana LLM fonksiyonu — model seçici + danışma kurulu."""
    global aktif_model
    from flask import session as _ses

    hafiza.append({"role": "user", "content": komut})
    hafiza_txt_yaz("user", komut)
    if len(hafiza) > MAX_HAFIZA:
        del hafiza[:2]

    internet_ctx = context_topla(komut, kendi_kodu_ozet)
    now_str      = guncel_tarih_saat()

    if _ses.get("rol") == "admin":
        sistem_arti = SISTEM + f"\n[PC SAATI: {now_str}] [MODEL: {aktif_model.upper()}]"
    else:
        sistem_arti = SISTEM_MISAFIR + f"\n[SAAT: {now_str}]"

    # Model seçici
    if aktif_model == "gemini":
        prompt = ("\n".join([internet_ctx] if internet_ctx else []) +
                  "\n".join(f"{m['role'].upper()}: {m['content']}" for m in hafiza))
        yanit  = llm_gemini(prompt, sistem_arti, GEMINI_KEY)

    elif aktif_model == "groq":
        mesajlar = []
        if internet_ctx:
            mesajlar.append({"role":"user","content":f"[CONTEXT]\n{internet_ctx}\n[/CONTEXT]"})
            mesajlar.append({"role":"assistant","content":"Anladım."})
        mesajlar += hafiza[:-1]
        mesajlar.append({"role":"user","content":komut})
        yanit = llm_groq(mesajlar, sistem_arti, GROQ_KEY, GROQ_MODEL)

    else:  # local
        prompt_parca = [f"SYSTEM: {sistem_arti}"]
        if internet_ctx:
            prompt_parca.append(f"\n{internet_ctx}\n")
        prompt_parca += [f"{m['role'].upper()}: {m['content']}" for m in hafiza]
        yanit = llm_local("\n".join(prompt_parca), MODEL)

    # Danışma kurulu
    if danisma_gerekli_mi(komut):
        hafiza_txt_yaz("sistem","[DANIŞMA KURULU AKTİF]")
        yanit = aura_danisma_kurulu(
            komut, yanit, sistem_arti, internet_ctx,
            GEMINI_KEY, GROQ_KEY, GROQ_MODEL
        )

    hafiza.append({"role":"assistant","content":yanit})
    hafiza_txt_yaz("assistant", yanit)
    hafiza_txt_yaz("sistem", f"[MODEL: {aktif_model}]")
    return yanit

# ============================================================
# ================= PC KOMUT PARSER ==========================
# ============================================================

ADMIN_KOMUTLAR = ["$","/ls","/dir","/oku ","/ps","/process",
                  "/processler","/pc","/sistem","/sysinfo","onayla:"]

def ozel_pc_komut(komut: str):
    from flask import session as _ses
    k  = komut.strip()
    kl = k.lower()
    is_admin = _ses.get("rol") == "admin"

    # Herkese açık
    if kl.startswith("/hava"):
        parts = k.split(maxsplit=1)
        return hava_durumu(parts[1] if len(parts)>1 else "Istanbul")
    if kl in ["/doviz","/kur","/dolar"]: return doviz_bilgisi()
    if kl in ["/altin","/gold","/xau"]:  return altin_bilgisi()
    if kl.startswith("/url "): return url_oku(k[5:].strip())

    # Admin koruması
    if any(kl.startswith(p.lower()) for p in ADMIN_KOMUTLAR) and not is_admin:
        return "🔒 Bu komut sadece Mimar Volkan'a açıktır."

    if k.startswith("$"):
        shell_cmd = k[1:].strip()
        onay = kl.startswith("$ onayla:")
        if onay: shell_cmd = k[9:].strip()
        return pc_komut_calistir(shell_cmd, onay)
    if kl.startswith("onayla:"):    return pc_komut_calistir(k[7:].strip(), True)
    if kl.startswith("/oku "):      return pc_dosya_oku(k[5:].strip())
    if kl.startswith("/ls") or kl.startswith("/dir"):
        parts = k.split(maxsplit=1)
        return pc_dosya_listesi(parts[1] if len(parts)>1 else ".")
    if kl in ["/ps","/process","/processler"]: return pc_process_listesi()
    if kl in ["/pc","/sistem","/sysinfo"]:
        return pc_sistem_bilgisi() + "\n\n" + pc_servis_durumu()

    if kl in ["/kod","/kendikod","/benimkod"]:
        if not is_admin: return "🔒 Bu komut sadece Mimar Volkan'a açıktır."
        return kendi_kodu_ozet()
    if kl.startswith("/kod "):
        if not is_admin: return "🔒 Bu komut sadece Mimar Volkan'a açıktır."
        try:
            parts2 = k.split()
            bas = int(parts2[1])-1 if len(parts2)>1 else 0
            bit = int(parts2[2])   if len(parts2)>2 else bas+100
            return kendi_kodu_tam(bas, bit)
        except Exception:
            return kendi_kodu_ozet()
    if kl in ["/analiz","/hatavar","/kodanaliz"]:
        if not is_admin: return "🔒 Bu komut sadece Mimar Volkan'a açıktır."
        return "KOD_ANALIZ_ISTE:" + kendi_kodu_ozet()

    if kl in ["/danış","/danis","/kurul"]:
        if not is_admin: return "🔒 Bu komut sadece Mimar Volkan'a açıktır."
        return (f"🧠 DANIŞMA KURULU HAZIR\n\n"
                f"Kullanım: /danış <soru>\n\n"
                f"🌟 Gemini: {'✅' if GEMINI_KEY else '❌'}  "
                f"⚡ Groq: {'✅' if GROQ_KEY else '❌'}")

    if kl.startswith("/model"):
        if not is_admin: return "🔒 Model değiştirme sadece Mimar Volkan'a açıktır."
        global aktif_model
        parts = k.split(maxsplit=1)
        if len(parts) < 2:
            return (f"🤖 Aktif: {aktif_model.upper()}\n\n"
                    f"/model local | /model gemini | /model groq")
        secim = parts[1].strip().lower()
        if secim in ["local","ollama"]:
            aktif_model = "local"; return f"✅ Model: YEREL OLLAMA"
        elif secim in ["gemini","google"]:
            aktif_model = "gemini"; return "✅ Model: GOOGLE GEMİNİ 🌟"
        elif secim in ["groq","llama"]:
            aktif_model = "groq"; return "✅ Model: GROQ LLAMA 3.3 70B ⚡"
        return f"❌ Bilinmeyen model: {secim}"

    # Kamera
    if kl in ["/foto","/kamera","/snapshot"]:
        if not is_admin: return "🔒 Bu komut sadece Mimar Volkan'a açıktır."
        sonuc = kamera_foto()
        if sonuc.startswith("FOTO:"): return "FOTO_B64:" + sonuc[5:]
        if sonuc == "HATA:opencv":    return "❌ pip install opencv-python"
        if sonuc == "HATA:kamera_yok": return "❌ Kamera bulunamadı."
        return f"❌ {sonuc}"
    if kl in ["/canli","/stream","/live"]:
        if not is_admin: return "🔒 Bu komut sadece Mimar Volkan'a açıktır."
        return "STREAM_BASLAT"
    if kl in ["/dur","/stopstream","/kameradur"]:
        if not is_admin: return "🔒 Bu komut sadece Mimar Volkan'a açıktır."
        kamera_stream_durdur()
        return "STREAM_DURDUR"

    return None

# ============================================================
# ================= GİRİŞ / AUTH =============================
# ============================================================

def giris_gerekli(f):
    @wraps(f)
    def d(*a, **k):
        if not session.get("ok"):
            return redirect(url_for("giris"))
        return f(*a, **k)
    return d

@app.route("/giris", methods=["GET","POST"])
def giris():
    hata = False
    if request.method == "POST":
        s = request.form.get("s","")
        if s == SIFRE:
            session["ok"] = True; session["rol"] = "admin"
            return redirect("/")
        elif s == MISAFIR_SIFRE:
            session["ok"] = True; session["rol"] = "misafir"
            return redirect("/")
        hata = True
    return render_template_string("""<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURA — Giriş</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'Courier New',monospace;padding:16px}
.kart{background:#111;border:1px solid #0088ff;border-radius:12px;padding:28px 24px;box-shadow:0 0 30px rgba(0,136,255,0.3);text-align:center;width:100%;max-width:320px}
h2{color:#0088ff;margin-bottom:6px;font-size:20px;text-shadow:0 0 5px #0088ff}
.alt{color:#ff00cc;font-size:11px;margin-bottom:20px;letter-spacing:1px}
input{width:100%;padding:12px;background:#000;border:1px solid #0088ff;border-radius:8px;font-size:18px;text-align:center;letter-spacing:6px;margin-bottom:12px;outline:none;color:#0088ff;transition:0.3s}
input:focus{border-color:#ff00cc;box-shadow:0 0 8px #ff00cc44}
button{width:100%;padding:12px;background:linear-gradient(135deg,#0088ff,#6600ff);color:#fff;border:none;border-radius:8px;font-size:15px;cursor:pointer;font-weight:bold}
.e{color:#ff4444;font-size:12px;margin-top:10px;padding:6px;background:#ff000011;border-radius:6px}
.hint{color:#444;font-size:10px;margin-top:14px}
</style></head><body><div class="kart">
<h2>⚛️ AURA-V</h2>
<div class="alt">VOLKANIYA BİLİNÇ SİSTEMİ</div>
<form method="POST">
<input type="password" name="s" placeholder="••••••" autofocus>
<button>⚡ GİRİŞ</button></form>
{% if hata %}<div class="e">❌ Geçersiz erişim kodu</div>{% endif %}
<div class="hint">Erişim kodunuzu girin</div>
</div></body></html>""", hata=hata)

# ============================================================
# ================= ANA SAYFA HTML ===========================
# ============================================================

INDEX_HTML = open("aura_index.html", encoding="utf-8").read() if os.path.exists("aura_index.html") else """
<!DOCTYPE html><html lang="tr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>⚛️ AURA-V</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden;background:#0a0a0a;font-family:'Courier New',monospace;color:#fff;}
#app{display:flex;flex-direction:column;height:100vh;height:100dvh;}
#hd{background:#050505;border-bottom:1px solid #0088ff33;padding:8px 12px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;flex-shrink:0;}
#hd h1{font-size:12px;color:#0088ff;white-space:nowrap;}
#btn-grup{display:flex;gap:5px;flex-wrap:wrap;}
.hbtn{background:#0a0a0a;border:1px solid #0088ff44;color:#0088ff;padding:5px 10px;border-radius:8px;font-size:10px;cursor:pointer;white-space:nowrap;}
.hbtn:active{background:#0088ff;color:#000;}
.hbtn.pc{color:#00ff88;border-color:#00ff8844;}
#kisayollar{background:#050505;border-bottom:1px solid #00ff8811;padding:5px 10px;display:flex;gap:5px;flex-wrap:wrap;flex-shrink:0;overflow-x:auto;}
.ks{background:#0a0a0a;border:1px solid #00ff8833;border-radius:10px;padding:4px 10px;font-size:10px;color:#00ff88;cursor:pointer;white-space:nowrap;flex-shrink:0;}
#msgs{flex:1;overflow-y:auto;padding:10px 12px;display:flex;flex-direction:column;gap:8px;background:#0a0a0a;min-height:0;-webkit-overflow-scrolling:touch;}
#msgs::-webkit-scrollbar{width:3px;}
#msgs::-webkit-scrollbar-thumb{background:#0088ff44;border-radius:3px;}
.bot{background:#111;border-left:3px solid #ff00cc;padding:10px 14px;border-radius:0 12px 12px 0;max-width:88%;font-size:13px;line-height:1.6;color:#fff;white-space:pre-wrap;word-wrap:break-word;}
.ben{background:#0d1f1f;border-right:3px solid #0088ff;padding:10px 14px;border-radius:12px 0 0 12px;max-width:88%;align-self:flex-end;font-size:13px;color:#fff;text-align:right;word-wrap:break-word;}
.sys{text-align:center;font-size:10px;color:#666;padding:4px;}
.pc-out{background:#0a150a;border-left:3px solid #00ff88;padding:10px 14px;border-radius:0 12px 12px 0;max-width:95%;font-size:11px;line-height:1.5;color:#00ff88;white-space:pre-wrap;word-wrap:break-word;font-family:'Courier New',monospace;}
#alt{background:#050505;border-top:1px solid #0088ff44;padding:10px 12px;display:flex;gap:8px;align-items:flex-end;flex-shrink:0;padding-bottom:max(10px,env(safe-area-inset-bottom));}
#g{flex:1;background:#111;border:1px solid #0088ff44;border-radius:20px;padding:10px 16px;font-size:14px;outline:none;resize:none;min-height:42px;max-height:120px;font-family:'Courier New',monospace;color:#0088ff;line-height:1.4;}
#g:focus{border-color:#ff00cc;box-shadow:0 0 8px #ff00cc33;}
#g::placeholder{color:#333;}
.btn{border:1px solid #0088ff44;border-radius:50%;width:42px;height:42px;cursor:pointer;background:#111;color:#0088ff;font-size:16px;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:0.2s;}
.btn:active{background:#0088ff;color:#000;}
#bs.on{background:#ff00cc;color:#000;border-color:#ff00cc;}
#remote-panel{background:#050505;border-top:1px solid #ff00cc22;padding:3px 10px;font-size:9px;text-align:center;flex-shrink:0;color:#444;}
#remote-panel a{color:#0088ff55;text-decoration:none;}
#sys-bar{background:#050505;border-bottom:1px solid #0088ff11;padding:3px 12px;display:flex;gap:12px;flex-wrap:wrap;flex-shrink:0;font-size:9px;color:#0088ff55;}
</style></head><body>

<!-- KAMERA MODAL -->
<div id="kamera-modal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;z-index:99;background:rgba(0,0,0,0.97);flex-direction:column;align-items:center;justify-content:center;">
  <div style="width:100%;max-width:700px;padding:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span id="kamera-baslik" style="color:#ff6600;font-size:12px;">📷 KAMERA</span>
      <div style="display:flex;gap:8px;">
        <button onclick="kameraIndir()" style="background:#0088ff;border:none;color:#fff;padding:6px 14px;border-radius:8px;cursor:pointer;font-size:12px;">⬇️ İndir</button>
        <button onclick="kameraKapat()" style="background:#ff4444;border:none;color:#fff;padding:6px 14px;border-radius:8px;cursor:pointer;font-size:12px;">✕ Kapat</button>
      </div>
    </div>
    <img id="kamera-img" src="" style="width:100%;border-radius:10px;border:2px solid #ff6600;display:block;" />
    <div id="stream-durum" style="text-align:center;color:#ff0044;font-size:11px;margin-top:6px;display:none;">🔴 CANLI YAYIN — /dur yazarak durdur</div>
  </div>
</div>

<div id="app">
  <div id="hd">
    <h1>⚛️ AURA-V | <span id="rol-badge">...</span></h1>
    <div id="btn-grup"></div>
  </div>
  <div id="sys-bar" style="display:none;">
    <span id="cpu-bar">CPU:--%</span>
    <span id="ram-bar">RAM:--</span>
    <span id="disk-bar">DSK:--%</span>
    <span id="ip-bar">IP:--</span>
  </div>
  <div id="kisayollar"></div>
  <div id="msgs"><div class="sys">⚛️ AURA-V aktif</div></div>
  <div id="alt">
    <textarea id="g" rows="1" placeholder="Mesaj yaz..." oninput="autoResize(this)"></textarea>
    <button class="btn" id="bs" onclick="sesBtn()">🎤</button>
    <button class="btn" onclick="gonder()">➤</button>
  </div>
  <div id="remote-panel">🌍 <a href="__REMOTE_URL__" target="_blank">__REMOTE_URL__</a></div>
</div>

<script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
<script>
const socket = io();
let mic=null, dinl=false, tts_aktif_audio=null, streamAktif=false;
const SR = window.SpeechRecognition||window.webkitSpeechRecognition;
if(SR){
  mic=new SR(); mic.lang="tr-TR"; mic.continuous=false; mic.interimResults=false;
  mic.onresult=e=>{gonderMesaj(e.results[0][0].transcript,true);dur();};
  mic.onerror=dur; mic.onend=dur;
}
function sesBtn(){ if(!SR){alert("Ses desteği yok!");return;} if(dinl){dur();return;} sesDurdur(); dinl=true; document.getElementById("bs").classList.add("on"); mic.start(); }
function dur(){ dinl=false; document.getElementById("bs").classList.remove("on"); try{mic.stop();}catch(e){} }
function autoResize(el){ el.style.height="auto"; el.style.height=Math.min(el.scrollHeight,120)+"px"; }
function hizliKomut(k){ document.getElementById("g").value=k; gonder(); }
function gonder(){ const g=document.getElementById("g"),m=g.value.trim(); if(!m)return; g.value=""; g.style.height="auto"; gonderMesaj(m,false); }
function gonderMesaj(m,sesli){ ekle("ben",m); const d=document.createElement("div"); d.className="sys"; d.id="bkl"; d.textContent="🌀 Düşünüyor..."; document.getElementById("msgs").appendChild(d); kaydir(); socket.emit("mesaj",{komut:m,sesli:sesli}); }
function sesDurdur(){ if(tts_aktif_audio){tts_aktif_audio.pause();tts_aktif_audio=null;} if(window.speechSynthesis)speechSynthesis.cancel(); }
function sesOku(metin,tts_url){ sesDurdur(); if(tts_url){ const a=new Audio(tts_url); a.volume=0.9; tts_aktif_audio=a; a.play().catch(()=>_tarayiciSes(metin)); return; } _tarayiciSes(metin); }
function _tarayiciSes(metin){ if(!window.speechSynthesis)return; const u=new SpeechSynthesisUtterance(metin.slice(0,400)); u.lang="tr-TR"; u.rate=0.92; const sesler=speechSynthesis.getVoices(); const tr=sesler.find(v=>v.lang.startsWith("tr")); if(tr)u.voice=tr; speechSynthesis.speak(u); }
if(window.speechSynthesis){ speechSynthesis.getVoices(); speechSynthesis.onvoiceschanged=()=>speechSynthesis.getVoices(); }
socket.on("yanit",d=>{ const b=document.getElementById("bkl"); if(b)b.remove(); const div=document.createElement("div"); const pcE=["🖥️","⚙️","📁","💻","💱","🥇","🌤️","🔌","📄","🌐","📋"]; div.className=pcE.some(e=>d.text.startsWith(e))?"pc-out":"bot"; div.textContent=d.text; document.getElementById("msgs").appendChild(div); kaydir(); if(d.sesli)sesOku(d.text,d.tts_url); });
socket.on("sistem",d=>{ const b=document.getElementById("bkl"); if(b)b.remove(); ekle("sys",d.msg); });
socket.on("sistem_monitor",d=>{ document.getElementById("cpu-bar").textContent="CPU:"+d.cpu+"%"; document.getElementById("ram-bar").textContent="RAM:"+d.ram_kul+"/"+d.ram_tot+"G"; document.getElementById("disk-bar").textContent="DSK:"+d.disk_pct+"%"; document.getElementById("ip-bar").textContent="IP:"+d.ip; });
function kameraGoster(b64){ document.getElementById("kamera-img").src="data:image/jpeg;base64,"+b64; document.getElementById("kamera-modal").style.display="flex"; }
function kameraKapat(){ document.getElementById("kamera-modal").style.display="none"; if(streamAktif){hizliKomut("/dur");streamAktif=false;} }
function kameraIndir(){ const img=document.getElementById("kamera-img"),a=document.createElement("a"); a.href=img.src; a.download="aura-"+new Date().toISOString().slice(0,19).replace(/[:.]/g,"-")+".jpg"; a.click(); }
function toggleStream(){ if(streamAktif){hizliKomut("/dur");streamAktif=false;}else{hizliKomut("/canli");streamAktif=true;} }
socket.on("kamera_foto",d=>{ const b=document.getElementById("bkl");if(b)b.remove(); kameraGoster(d.img); document.getElementById("kamera-baslik").textContent="📷 "+new Date().toLocaleTimeString("tr-TR"); document.getElementById("stream-durum").style.display="none"; });
socket.on("kamera_frame",d=>{ document.getElementById("kamera-img").src="data:image/jpeg;base64,"+d.img; document.getElementById("kamera-modal").style.display="flex"; document.getElementById("kamera-baslik").textContent="🔴 "+new Date().toLocaleTimeString("tr-TR"); document.getElementById("stream-durum").style.display="block"; });
socket.on("kamera_stream_basliyor",d=>{ streamAktif=true; document.getElementById("kamera-modal").style.display="flex"; const b=document.getElementById("bkl");if(b)b.remove(); ekle("sys",d.msg); });
socket.on("kamera_durdu",()=>{ streamAktif=false; document.getElementById("stream-durum").style.display="none"; });
socket.on("kamera_hata",d=>{ const b=document.getElementById("bkl");if(b)b.remove(); ekle("sys","❌ "+d.msg); });
socket.on("yanit_model_guncelle",d=>{ const g=document.getElementById("model-gosterge"); if(g)g.textContent=d.model.toUpperCase(); });
document.addEventListener("keydown",e=>{if(e.key==="Escape")kameraKapat();});
function modelDegistir(m){hizliKomut("/model "+m);}
function ekle(t,m){ const d=document.createElement("div"); d.className=t; d.textContent=m; document.getElementById("msgs").appendChild(d); kaydir(); }
function kaydir(){ const m=document.getElementById("msgs"); m.scrollTop=m.scrollHeight; }
document.getElementById("g").addEventListener("keydown",e=>{ if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();gonder();} });
const ROL = "__ROL__";
function uiInit(){
  const badge=document.getElementById("rol-badge"),btnGrup=document.getElementById("btn-grup"),kisayol=document.getElementById("kisayollar"),sysBar=document.getElementById("sys-bar");
  if(ROL==="admin"){
    badge.innerHTML="<span style='color:#ff00cc'>VOLKAN</span> | <span id='model-gosterge' style='color:#00ff88;font-size:10px'>LOCAL</span>";
    sysBar.style.display="flex";
    btnGrup.innerHTML=`<button class="hbtn pc" onclick="hizliKomut('/pc')">🖥️ PC</button><button class="hbtn pc" onclick="hizliKomut('/ps')">⚙️ PS</button><button class="hbtn pc" onclick="hizliKomut('/hava Istanbul')">🌤️ Hava</button><button class="hbtn pc" onclick="hizliKomut('/doviz')">💱 Döviz</button><button class="hbtn" style="color:#ff6600;border-color:#ff660044" onclick="hizliKomut('/foto')">📷 Foto</button><button class="hbtn" style="color:#ff0044;border-color:#ff004444" onclick="toggleStream()">🔴 Canlı</button><button class="hbtn" onclick="socket.emit('hafiza_sil')">🗑️</button>`;
    kisayol.innerHTML=`<span class="ks" onclick="hizliKomut('/pc')">💻 PC</span><span class="ks" onclick="hizliKomut('/altin')">🥇 Altın</span><span class="ks" onclick="hizliKomut('/ls ~')">📂 Ev</span><span class="ks" onclick="hizliKomut('$ tasklist')">📊 Görevler</span><span class="ks" onclick="hizliKomut('$ ipconfig')">🌐 IP</span><span class="ks" onclick="hizliKomut('/foto')">📷 Foto</span><span class="ks" style="color:#ff0044" onclick="toggleStream()">🔴 Canlı</span><span class="ks" style="color:#4285f4" onclick="modelDegistir('gemini')">🌟 Gemini</span><span class="ks" style="color:#f55036" onclick="modelDegistir('groq')">⚡ Groq</span><span class="ks" style="color:#aaa" onclick="modelDegistir('local')">💻 Local</span><span class="ks" style="color:#ff00cc" onclick="hizliKomut('/danış')">🧠 Danış</span><span class="ks" style="color:#ffcc00" onclick="hizliKomut('/kod')">📋 Kodum</span><span class="ks" style="color:#ffaa00" onclick="hizliKomut('/analiz')">🔍 Analiz</span>`;
  } else {
    badge.innerHTML="✨ MİSAFİR"; sysBar.style.display="none";
    btnGrup.innerHTML=`<button class="hbtn pc" onclick="hizliKomut('/hava Istanbul')">🌤️ Hava</button><button class="hbtn pc" onclick="hizliKomut('/doviz')">💱 Döviz</button><button class="hbtn pc" onclick="hizliKomut('/altin')">🥇 Altın</button><button class="hbtn" onclick="socket.emit('hafiza_sil')">🗑️</button>`;
    kisayol.innerHTML=`<span class="ks" onclick="hizliKomut('/hava Istanbul')">🌤️ İstanbul</span><span class="ks" onclick="hizliKomut('/hava Ankara')">🌤️ Ankara</span><span class="ks" onclick="hizliKomut('/doviz')">💱 Döviz</span><span class="ks" onclick="hizliKomut('/altin')">🥇 Altın</span><span class="ks" onclick="hizliKomut('Merhaba!')">👋 Merhaba</span>`;
    setTimeout(()=>ekle("sys","👋 Hoş geldiniz! Ben AURA."),500);
  }
}
uiInit();
</script></body></html>
"""

@app.route("/")
@giris_gerekli
def index():
    remote = session.get("remote_url", f"http://localhost:{FLASK_PORT}")
    rol    = session.get("rol", "misafir")
    html   = INDEX_HTML.replace("__REMOTE_URL__", remote).replace("__ROL__", rol)
    return html

@app.route("/static/sound/<path:filename>")
def serve_sound(filename):
    from flask import send_from_directory
    return send_from_directory("static/sound", filename)

@app.route("/static/tts/<path:filename>")
def serve_tts(filename):
    from flask import send_from_directory
    return send_from_directory("static/tts", filename)

# ============================================================
# ================= SOCKET OLAYLARI ==========================
# ============================================================

@socketio.on("mesaj")
def on_mesaj(data):
    komut = data.get("komut","").strip()
    sesli = data.get("sesli", False)
    if not komut: return

    emit("dusunuyor", {})

    if danisma_gerekli_mi(komut.lower()):
        emit("sistem", {"msg": "🧠 Danışma kurulu devreye giriyor — AURA + Gemini + Groq..."})

    ozel = ozel_pc_komut(komut)
    if ozel is not None:
        if ozel.startswith("FOTO_B64:"):
            emit("kamera_foto", {"img": ozel[9:]}); return
        if ozel == "STREAM_BASLAT":
            sid   = request.sid
            sonuc = kamera_stream_baslat(socketio, sid, fps=2)
            if sonuc == "zaten_aktif":
                emit("yanit", {"text":"📷 Canlı yayın zaten aktif. /dur yaz.","sesli":False})
            else:
                emit("kamera_stream_basliyor", {"msg":"📷 Canlı yayın başladı! /dur yazarak durdur."})
            return
        if ozel == "STREAM_DURDUR":
            emit("yanit", {"text":"📷 Canlı yayın durduruldu.","sesli":False}); return
        if ozel.startswith("KOD_ANALIZ_ISTE:"):
            kod_ozet = ozel[16:]
            analiz_prompt = (f"Aşağıdaki kendi kodunu analiz et. "
                             f"Hataları, iyileştirme önerilerini Türkçe listele.\n\n{kod_ozet}")
            yanit = llm(analiz_prompt)
            emit("yanit", {"text":yanit,"sesli":False}); return
        hafiza.append({"role":"user","content":komut})
        hafiza.append({"role":"assistant","content":ozel})
        hafiza_txt_yaz("user",komut)
        hafiza_txt_yaz("assistant",ozel)
        emit("yanit", {"text":ozel,"sesli":False})
        return

    yanit = llm(komut)

    if yanit.startswith("FOTO_B64:"):
        emit("kamera_foto", {"img":yanit[9:]}); return

    tts_url = gtts_olustur(yanit) if sesli else None
    emit("yanit", {"text":yanit,"sesli":sesli,"tts_url":tts_url})
    emit("yanit_model_guncelle", {"model":aktif_model})

@socketio.on("hafiza_sil")
def on_hafiza_sil():
    hafiza.clear()
    hafiza_txt_yaz("sistem","--- HAFIZA TEMIZLENDI ---")
    emit("sistem", {"msg":"🧠 Kuantum hafıza temizlendi Mimar Volkan."})

# ============================================================
# ================= ARKA PLAN THREADLERI =====================
# ============================================================

def sistem_monitor_loop():
    import time
    from aura_pc import sistem_monitor_verisi
    psutil_import = __import__("psutil")
    psutil_import.cpu_percent(interval=0)
    while True:
        try:
            time.sleep(8)
            veri = sistem_monitor_verisi()
            if veri:
                socketio.emit("sistem_monitor", veri)
        except Exception:
            pass

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
                ["cloudflared","tunnel","--url",f"http://localhost:{FLASK_PORT}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
                if m:
                    remote_url = m.group(0)
                    print(f"\n  🌍 UZAK ERİŞİM: {remote_url}\n")
                    break
        except Exception:
            remote_url = f"http://localhost:{FLASK_PORT}"

remote_url = None

# ============================================================
# ================= BAŞLAT ===================================
# ============================================================

if __name__ == "__main__":
    os.makedirs("static/sound", exist_ok=True)
    os.makedirs("static/tts",   exist_ok=True)
    hafiza_txt_yukle()
    hafiza_txt_yaz("sistem", "--- YENI OTURUM: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " ---")

    print("="*65)
    print("  ⚛️  AURA-V 2.0 — VOLKAN KUANTUM BİLİNÇ")
    print(f"  🌐 YEREL         : http://localhost:{FLASK_PORT}")
    print(f"  🔐 ADMİN ŞİFRESİ : {SIFRE}")
    print(f"  👥 MİSAFİR ŞİFRE : {MISAFIR_SIFRE}")
    print("  📦 MODÜLLER      : aura_pc · aura_arama · aura_kamera · aura_llm · aura_tts")
    print(f"  🤖 MODELLER      : local({MODEL}) | gemini | groq")
    print("="*65)
    print("  pip install flask flask-socketio flask-cors requests")
    print("  pip install beautifulsoup4 psutil numpy pyngrok gtts opencv-python")
    print("="*65)

    threading.Thread(target=tunel_baslat,       daemon=True).start()
    threading.Thread(target=sistem_monitor_loop, daemon=True).start()

    @app.before_request
    def set_remote_url():
        if remote_url:
            session["remote_url"] = remote_url

    socketio.run(app, host="0.0.0.0", port=FLASK_PORT, debug=False, allow_unsafe_werkzeug=True)
