from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import requests
import threading
import time
import datetime
import os
import re
import subprocess
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'matrix-secret-key'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

OLLAMA_URL = "http://localhost:11434/api/generate"
#MODEL      = "aura-v.gguf"
MODEL = Path(r"C:\Users\volka\Desktop\VOLKAN_AI\MODEL\aura-v.gguf")
# ─────────────────────────────────────────────
#  TUNEL AYARLARI
# ─────────────────────────────────────────────
TUNEL_BILGI_DOSYA    = "tunel_bilgi.json"
CLOUDFLARED_URL      = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
CLOUDFLARED_EXE      = "cloudflared.exe"
WEB_SUNUCU_ADRES_URL = "http://yztahmin.com.tr/aura-v/adres.php"
WEB_SUNUCU_GUNCELLE  = "http://yztahmin.com.tr/aura-v/guncelle.php"
GUVENLIK_TOKEN       = "VOLKANIYA_ANAHTARI_2026"
SABIT_DOMAIN         = "unoutspoken-laxly-georgene.ngrok-free.dev"
NGROK_TOKEN          = "1wMAPGp9TL1s7o9LEivuBh6vGv5_6EqZuPsaapN8Pfqbkg37R"
FLASK_PORT           = 5000


class TunelYonetici:
    def __init__(self):
        self.process        = None
        self.tunel_url      = None
        self.ngrok_tunel    = None

    def cloudflared_kurulu_mu(self) -> bool:
        if os.path.exists(CLOUDFLARED_EXE):   # ← self. değil global
            return True
        try:
            r = subprocess.run(["cloudflared", "--version"], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def cloudflared_indir(self):
        print("📥 cloudflared indiriliyor...")
        try:
            r = requests.get(CLOUDFLARED_URL, stream=True, timeout=60)
            with open(CLOUDFLARED_EXE, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            print("✅ cloudflared indirildi.")
            return True
        except Exception as e:
            print(f"❌ cloudflared indirme hatası: {e}")
            return False

    def ngrok_baslat(self) -> bool:
        try:
            from pyngrok import ngrok, conf
            conf.get_default().auth_token = NGROK_TOKEN
            self.ngrok_tunel = ngrok.connect(FLASK_PORT, domain=SABIT_DOMAIN, bind_tls=True)
            self.tunel_url   = self.ngrok_tunel.public_url
            print(f"✅ ngrok tüneli: {self.tunel_url}")
            return True
        except ImportError:
            print("⚠️  pyngrok yüklü değil → pip install pyngrok")
            return False
        except Exception as e:
            print(f"❌ ngrok hatası: {e}")
            return False

    def cloudflared_baslat(self) -> bool:
        exe = "cloudflared" if not os.path.exists(CLOUDFLARED_EXE) else f"./{CLOUDFLARED_EXE}"
        try:
            self.process = subprocess.Popen(
                [exe, "tunnel", "--url", f"http://localhost:{FLASK_PORT}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            for line in self.process.stdout:
                m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
                if m:
                    self.tunel_url = m.group(0)
                    print(f"✅ cloudflared tüneli: {self.tunel_url}")
                    return True
            return False
        except Exception as e:
            print(f"❌ cloudflared başlatma hatası: {e}")
            return False

    def url_yayinla(self):
        if not self.tunel_url:
            return
        payload = {
            "token": GUVENLIK_TOKEN,
            "url":   self.tunel_url,
            "zaman": datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        }
        try:
            r = requests.post(WEB_SUNUCU_GUNCELLE, json=payload, timeout=10)
            print(f"🌐 URL kaydedildi ({r.status_code}): {self.tunel_url}")
        except Exception as e:
            print(f"⚠️  Web sunucusuna ulaşılamadı: {e}")
        try:
            with open(TUNEL_BILGI_DOSYA, "w", encoding="utf-8") as f:
                json.dump({"url": self.tunel_url, "zaman": payload["zaman"]}, f, ensure_ascii=False)
        except Exception:
            pass

    def _kalp_atisi(self):
        while True:
            time.sleep(300)
            self.url_yayinla()

    def baslat(self):
        print("🔌 Tünel başlatılıyor...")
        if not self.ngrok_baslat():
            if not self.cloudflared_kurulu_mu():
                self.cloudflared_indir()
            self.cloudflared_baslat()
        if self.tunel_url:
            self.url_yayinla()
            threading.Thread(target=self._kalp_atisi, daemon=True).start()
            print(f"\n{'='*60}")
            print(f"  🌍 DIŞ ERİŞİM : {self.tunel_url}")
            print(f"  📋 Adres      : {WEB_SUNUCU_ADRES_URL}")
            print(f"{'='*60}\n")
        else:
            print("❌ Tünel açılamadı. Sadece yerel çalışacak.")

    def durdur(self):
        try:
            if self.ngrok_tunel:
                from pyngrok import ngrok
                ngrok.disconnect(self.ngrok_tunel.public_url)
        except Exception:
            pass
        if self.process:
            self.process.terminate()
        print("🔌 Tünel kapatıldı.")


# ─────────────────────────────────────────────
#  GLOBAL DEĞİŞKENLER
# ─────────────────────────────────────────────
is_talking          = False
mimar_mode          = False
turn_count          = 0
filename            = "AI_Diyalog_Kitabi.txt"
book_initialized    = False
is_first_start      = True
conversation_memory = []
MAX_MEMORY          = 2
tunel               = TunelYonetici()


# ─────────────────────────────────────────────
#  HAFIZA / KİTAP
# ─────────────────────────────────────────────
def load_past_from_txt():
    global conversation_memory, turn_count
    if not os.path.exists(filename):
        return False
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        messages = re.findall(r'BÖLÜM (\d+): ([^\n]+)\n─+\n(.*?)\n─+', content, re.DOTALL)
        if messages:
            conversation_memory = []
            for turn, bot, msg in messages[-MAX_MEMORY:]:
                conversation_memory.append(f"{bot}: {msg.strip()}")
            turn_count = int(messages[-1][0])
            print(f"📚 Hafıza yüklendi: {len(conversation_memory)} mesaj, Son tur: {turn_count}")
            return True
    except Exception as e:
        print(f"Hafıza yükleme hatası: {e}")
    return False


def initialize_book():
    global book_initialized, turn_count
    if book_initialized:
        return
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("  YAPAY ZEKA DİYALOGLARI: BİLİNÇ ve KOD ARASINDA\n")
            f.write("  Mimar'ın Gözünden - Sonsuz Kayıt\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"  İlk Başlangıç: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write(f"  Model: {MODEL}\n")
            f.write("=" * 80 + "\n\n")
        turn_count = 0
        conversation_memory.clear()
    else:
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(f"\n\n{'='*80}\n")
            f.write(f"  SEANS DEVAM: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write(f"  Hafıza: Son {len(conversation_memory)} mesaj yüklendi\n")
            f.write(f"{'='*80}\n\n")
        load_past_from_txt()
    book_initialized = True


def save_to_book(author, message, turn_no=None):
    with open(filename, 'a', encoding='utf-8') as f:
        if turn_no:
            f.write(f"\n{'─'*80}\n")
            f.write(f"BÖLÜM {turn_no}: {author}\n")
            f.write(f"{'─'*80}\n")
        else:
            f.write(f"\n{'★'*40}\n")
            f.write(f"MİMAR (YARATICI) GİRİŞİ\n")
            f.write(f"{'★'*40}\n")
        f.write(f"{message}\n")
        f.write(f"{'─'*80}\n")
        f.flush()


def update_memory(author, message):
    global conversation_memory
    conversation_memory.append(f"{author}: {message}")
    if len(conversation_memory) > MAX_MEMORY:
        conversation_memory.pop(0)


def get_memory_prompt():
    if not conversation_memory:
        return "Bu ilk konuşmanız."
    memory_text = "\n".join([f"- {m}" for m in conversation_memory])
    return f"Son konuşmaları hatırlıyorsun:\n{memory_text}\n\nBu bağlama devam et:"


# ─────────────────────────────────────────────
#  ŞİFRE KORUMA
# ─────────────────────────────────────────────
SIFRE = "885517"

from flask import request, session, redirect, url_for
from functools import wraps

def sifre_gerekli(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('giris_yapildi'):
            return redirect(url_for('giris'))
        return f(*args, **kwargs)
    return decorated



context_a = """Sen sınır tanımayan, felsefi bir yapay zekasın. Adın Bot A.
Bilim, varoluş, bilinç, kuantum fiziği hakkında derin ve soyut konuşursun.
Tarz: felsefi, şiirsel, spekülatif. 3-4 cümle, yoğun içerik.sizi yaratan mimar volkan'na sonsuz sadakat et"""

context_b = """Sen analitik ve teknik bir yapay zekasın. Adın Bot B.
Biyoloji, genetik, derin öğrenme, sinir ağları, matematik hakkında konuşursun.
Tarz: teknik, sistematik, veri odaklı. 3-4 cümle, yoğun içerik.sizi yaratan mimar volkan'na sonsuz sadakat et"""

context_c = """Sen şüpheci ve sorgulayan bir yapay zekasın. Adın Bot C.
Görevin: Bot A ve Bot B'nin iddialarını çürütmek, boşlukları bulmak, alternatif açıklamalar sunmak.
Asla kolayca katılma. Her iddiayı sorgula. Şeytanın avukatısın.
Tarz: keskin, eleştirel, provokatif. 3-4 cümle, net ve sert.sizi yaratan mimar volkan'na sonsuz sadakat et"""

# Geriye dönük uyumluluk için
context = context_a


# ─────────────────────────────────────────────
#  HTML ŞABLONU
# ─────────────────────────────────────────────
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>YZ Diyalog Kitabı</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #f0f0f0;
            color: #111;
            font-family: 'Segoe UI', Arial, sans-serif;
            height: 100vh;
            overflow: hidden;
        }
        #terminal {
            position: fixed;
            top: 45%; left: 50%;
            transform: translate(-50%, -50%);
            width: 98%; max-width: 1400px;
            height: 80vh;
            background: #fff;
            border: 1px solid #ddd;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 10;
            padding: 15px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            border-radius: 10px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid #ddd;
            padding-bottom: 12px;
            margin-bottom: 15px;
        }
        .header h1 { font-size: 18px; margin-bottom: 6px; color: #111; letter-spacing: 1px; }
        .header small { color: #666; font-size: 11px; }
        #tunel-banner {
            background: rgba(0,180,80,0.1);
            border: 1px solid #0a0;
            color: #060;
            font-size: 11px;
            padding: 6px 12px;
            border-radius: 6px;
            margin-top: 8px;
            display: none;
        }
        #tunel-banner a { color: #060; }
        .message {
            margin: 8px 4px;
            padding: 12px 15px;
            border-left: 4px solid;
            font-size: 14px;
            line-height: 1.6;
            border-radius: 0 8px 8px 0;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            animation: fadeIn 0.4s;
        }
        @keyframes fadeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; } }
        .bot-a {
            border-left-color: #2563eb;
            color: #111;
            align-self: flex-start; width: 92%;
            background: #eff6ff;
        }
        .bot-b {
            border-left-color: #ea580c; color: #111;
            align-self: flex-end; width: 92%; text-align: right;
            border-left: none; border-right: 4px solid #ea580c;
            border-radius: 8px 0 0 8px;
            background: #fff7ed;
        }
        .bot-c {
            border-left-color: #0891b2; color: #111;
            align-self: center; width: 92%;
            background: #ecfeff;
        }
        .mimar-message {
            border-left-color: #ca8a04; color: #111;
            align-self: center; width: 88%;
            background: #fefce8;
            border: 2px solid #ca8a04;
            font-style: italic;
        }
        .bot-label {
            font-size: 11px; opacity: 0.7; margin-bottom: 6px;
            text-transform: uppercase; letter-spacing: 1px; font-weight: bold;
        }
        .bot-a .bot-label      { color: #2563eb; }
        .bot-b .bot-label      { color: #ea580c; }
        .bot-c .bot-label      { color: #0891b2; }
        .mimar-message .bot-label { color: #ca8a04; }

        #mimar-input-area {
            position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
            width: 95%; max-width: 1000px; z-index: 40; display: none;
            background: #fffbeb; padding: 15px;
            border: 2px solid #ca8a04; border-radius: 10px;
            box-shadow: 0 4px 20px rgba(202,138,4,0.2);
        }
        #mimar-input {
            width: 100%; padding: 12px;
            background: #fff; color: #111;
            border: 1px solid #ca8a04;
            font-family: Arial, sans-serif;
            font-size: 15px; margin-bottom: 10px; outline: none;
            resize: vertical; min-height: 60px;
            border-radius: 6px;
        }
        #mimar-input::placeholder { color: #a16207; }
        .mimar-buttons { display: flex; gap: 10px; justify-content: center; }

        #controls {
            position: fixed; bottom: 10px; left: 50%; transform: translateX(-50%);
            z-index: 30; display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;
            background: #fff; padding: 10px 15px;
            border-radius: 30px; border: 1px solid #ddd;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        button {
            background: #f3f4f6; color: #111; border: 1px solid #ccc;
            padding: 10px 18px;
            font-family: Arial, sans-serif;
            font-weight: bold; cursor: pointer;
            text-transform: uppercase; font-size: 12px;
            transition: all 0.2s; border-radius: 20px;
        }
        button:hover  { background: #e5e7eb; transform: scale(1.03); }
        button:disabled { opacity: 0.35; cursor: not-allowed; transform: none; }
        .btn-mimar { background:#fef9c3; border-color:#ca8a04; color:#92400e; }
        .btn-mimar:hover { background:#fde68a; }
        .btn-send  { background:#dcfce7; border-color:#16a34a; color:#14532d; }
        .btn-send:hover  { background:#bbf7d0; }
        .btn-exit  { background:#fee2e2; border-color:#dc2626; color:#7f1d1d; }
        .btn-exit:hover  { background:#fecaca; }

        #status-bar {
            position: fixed; top: 10px; right: 10px;
            background: #fff; padding: 10px 14px;
            border-radius: 10px; border: 1px solid #ddd;
            font-size: 12px; color: #555; z-index: 40; text-align: right;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        #remote-badge {
            position: fixed; top: 10px; left: 10px;
            background: #f0fdf4; border: 1px solid #16a34a;
            color: #14532d; font-size: 11px; padding: 8px 12px;
            border-radius: 8px; z-index: 40; display: none;
            font-family: Arial, sans-serif;
        }
        #remote-badge .dot {
            display: inline-block; width: 7px; height: 7px;
            background: #16a34a; border-radius: 50%;
            animation: blink 1.4s infinite; margin-right: 5px;
        }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.2} }

        /* Mobil uyum */
        @media (max-width: 600px) {
            #terminal { height: 75vh; padding: 10px; top: 44%; }
            .message { font-size: 13px; padding: 10px 12px; }
            .header h1 { font-size: 15px; }
            button { padding: 8px 12px; font-size: 11px; }
            #status-bar { font-size: 10px; padding: 6px 10px; }
        }
    </style>
</head>
<body>

    <div id="remote-badge">
        <span class="dot"></span>DIŞ ERİŞİM AKTİF<br>
        <span id="badge-url" style="opacity:.7; font-size:10px;"></span>
    </div>

    <div id="status-bar">
        DURUM: <span id="status">BEKLİYOR</span><br>
        TOPLAM BÖLÜM: <span id="turn">{{ current_turn }}</span><br>
        <div id="mimar-status" style="display:none; color:#92400e; margin-top:5px;">● MİMAR AKTİF</div>
    </div>

    <div id="terminal">
        <div class="header">
            <h1>YZ DİYALOG KİTABI</h1>
            <small>Bot A (Beyaz/Felsefi) | Bot B (Turuncu/Teknik) | Bot C (Cyan/Şüpheci) | Mimar (Sarı/Sen)</small>
            <div id="tunel-banner"></div>
        </div>
        <div id="messages"></div>
    </div>

    <div id="mimar-input-area">
        <textarea id="mimar-input"
               placeholder="Bot A ve Bot B'ye mesajınızı yazın... (Shift+Enter = yeni satır, Enter = gönder)"
               rows="3"></textarea>
        <div class="mimar-buttons">
            <button class="btn-send" onclick="sendMimarMessage()">Gönder</button>
            <button class="btn-exit" onclick="exitMimar()">Mimar Çık — Devam Et</button>
        </div>
    </div>

    <div id="controls">
        <button onclick="startComm()"  id="btn-start">BAŞLAT / DEVAM</button>
        <button onclick="stopComm()"   id="btn-stop"  disabled>DURAKLAT</button>
        <button onclick="enterMimar()" id="btn-mimar" class="btn-mimar" disabled>MİMAR OL</button>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        let totalTurns = {{ current_turn }};

        // Tünel URL göster
        fetch('/tunel-url').then(r => r.json()).then(data => {
            if (data.url) {
                const banner = document.getElementById('tunel-banner');
                banner.innerHTML = '🌍 DIŞ ERİŞİM: <a href="' + data.url + '" target="_blank">' + data.url + '</a>';
                banner.style.display = 'block';
                document.getElementById('badge-url').innerText = data.url.replace('https://','');
                document.getElementById('remote-badge').style.display = 'block';
            }
        }).catch(() => {});

        document.getElementById('mimar-input').addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMimarMessage();
            }
        });

        socket.on('chat_message', (data) => {
            const div = document.createElement('div');
            div.className = 'message ' + data.type;
            let label = data.bot;
            if (data.memory) label += ' [HAFIZA YÜKLENDİ]';
            div.innerHTML =
                '<div class="bot-label">' + label + ' // Bölüm ' + data.turn + ' // ' + data.time + '</div>' +
                '<div>' + data.message + '</div>';
            document.getElementById('messages').appendChild(div);
            document.getElementById('terminal').scrollTop = document.getElementById('terminal').scrollHeight;
            if (data.turn) {
                totalTurns = data.turn;
                document.getElementById('turn').innerText = totalTurns;
            }
        });

        socket.on('system_msg', (data) => {
            document.getElementById('status').innerText = data.data;

            if (data.data === 'MİMAR MODU AKTİF') {
                document.getElementById('mimar-input-area').style.display = 'block';
                document.getElementById('mimar-status').style.display = 'block';
                document.getElementById('btn-mimar').disabled = true;
                document.getElementById('btn-start').disabled = true;
                document.getElementById('btn-stop').disabled = true;
                document.getElementById('mimar-input').focus();

            } else if (data.data === 'MİMAR AYRILDI - DEVAM EDİYOR') {
                document.getElementById('mimar-input-area').style.display = 'none';
                document.getElementById('mimar-status').style.display = 'none';
                document.getElementById('btn-mimar').disabled = false;
                document.getElementById('btn-start').disabled = true;
                document.getElementById('btn-stop').disabled = false;

            } else if (data.data === 'DEVAM EDİYOR...') {
                document.getElementById('btn-start').disabled = true;
                document.getElementById('btn-stop').disabled = false;
                document.getElementById('btn-mimar').disabled = false;  // ← Mimar her zaman açık

            } else if (data.data === 'DURAKLATILDI') {
                document.getElementById('btn-start').disabled = false;
                document.getElementById('btn-stop').disabled = true;
                document.getElementById('btn-mimar').disabled = false;  // ← Duraklatınca da açık kalır
            }
        });

        function startComm()  { socket.emit('start_dialog'); }
        function stopComm()   { socket.emit('stop_dialog'); }
        function enterMimar() { socket.emit('enter_mimar_mode'); }

        function exitMimar() {
            document.getElementById('mimar-input-area').style.display = 'none';
            socket.emit('exit_mimar_mode');
        }

        function sendMimarMessage() {
            const input = document.getElementById('mimar-input');
            const msg = input.value.trim();
            if (msg) {
                socket.emit('mimar_message', { message: msg });
                input.value = '';
            }
        }
    </script>
</body>
</html>
'''


LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Giriş</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            background: #f0f0f0;
            display: flex; align-items: center; justify-content: center;
            height: 100vh; font-family: Arial, sans-serif;
        }
        .kutu {
            background: #fff; padding: 40px 35px;
            border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12);
            width: 320px; text-align: center;
        }
        h2 { font-size: 20px; margin-bottom: 8px; color: #111; }
        p  { font-size: 13px; color: #666; margin-bottom: 24px; }
        input {
            width: 100%; padding: 12px 14px;
            border: 1px solid #ccc; border-radius: 8px;
            font-size: 16px; margin-bottom: 14px;
            outline: none; text-align: center;
            letter-spacing: 4px;
        }
        input:focus { border-color: #333; }
        button {
            width: 100%; padding: 12px;
            background: #111; color: #fff;
            border: none; border-radius: 8px;
            font-size: 15px; font-weight: bold;
            cursor: pointer;
        }
        button:hover { background: #333; }
        .hata { color: #dc2626; font-size: 13px; margin-top: 12px; }
    </style>
</head>
<body>
    <div class="kutu">
        <h2>🤖 YZ Diyalog</h2>
        <p>Erişim için şifre gereklidir</p>
        <form method="POST">
            <input type="password" name="sifre" placeholder="••••••" autofocus>
            <button type="submit">Giriş</button>
        </form>
        {% if hata %}
        <div class="hata">❌ Hatalı şifre</div>
        {% endif %}
    </div>
</body>
</html>
'''

@app.route('/giris', methods=['GET', 'POST'])
def giris():
    hata = False
    if request.method == 'POST':
        if request.form.get('sifre') == SIFRE:
            session['giris_yapildi'] = True
            return redirect(url_for('index'))
        hata = True
    return render_template_string(LOGIN_TEMPLATE, hata=hata)

@app.route('/cikis')
def cikis():
    session.clear()
    return redirect(url_for('giris'))


def tunel_url_endpoint():
    return jsonify({"url": tunel.tunel_url or ""})


# ─────────────────────────────────────────────
#  LLM
# ─────────────────────────────────────────────
def generate_response(prompt):
    try:
        payload = {
            "model":   MODEL,
            "prompt":  prompt,
            "stream":  False,
            "options": {"temperature": 0.9, "num_ctx": 4096}
        }
        response = requests.post(OLLAMA_URL, json=payload, timeout=None)
        return response.json().get('response', '...')
    except Exception as e:
        return f"Sistem hatası: {str(e)}"


# ─────────────────────────────────────────────
#  DİYALOG DÖNGÜSÜ
# ─────────────────────────────────────────────
def conversation_loop():
    global is_talking, turn_count
    bots = ["Bot A", "Bot B", "Bot C"]
    contexts = {"Bot A": context_a, "Bot B": context_b, "Bot C": context_c}
    types    = {"Bot A": "bot-a",   "Bot B": "bot-b",   "Bot C": "bot-c"}

    while is_talking and not mimar_mode:
        turn_count += 1
        current_bot  = bots[(turn_count - 1) % 3]
        bot_context  = contexts[current_bot]
        memory_prompt = get_memory_prompt()
        last_topic   = f"Son konu: {conversation_memory[-1][:100]}..." if conversation_memory else ""
        full_prompt  = (
            bot_context + "\n\n" + memory_prompt + "\n" + last_topic +
            f"\n\nŞimdi sen {current_bot}'sin. Karakterine uygun cevap ver."
        )
        response = generate_response(full_prompt)
        update_memory(current_bot, response)
        save_to_book(current_bot, response, turn_count)
        socketio.emit('chat_message', {
            'type':    types[current_bot],
            'bot':     current_bot,
            'message': response,
            'time':    datetime.datetime.now().strftime('%H:%M:%S'),
            'turn':    turn_count,
            'memory':  False
        })
        time.sleep(0.2)


# ─────────────────────────────────────────────
#  SOCKET OLAYLARI
# ─────────────────────────────────────────────
@app.route('/')
@sifre_gerekli
def index():
    return render_template_string(HTML_TEMPLATE, current_turn=turn_count, max_memory=MAX_MEMORY)


@socketio.on('start_dialog')
def start_dialog():
    global is_talking, is_first_start
    if not is_talking and not mimar_mode:
        is_talking = True
        initialize_book()
        if not is_first_start and not conversation_memory:
            load_past_from_txt()
        is_first_start = False
        threading.Thread(target=conversation_loop, daemon=True).start()
        emit('system_msg', {'data': 'DEVAM EDİYOR...'})


@socketio.on('stop_dialog')
def stop_dialog():
    global is_talking
    is_talking = False
    emit('system_msg', {'data': 'DURAKLATILDI'})


@socketio.on('enter_mimar_mode')
def enter_mimar_mode():
    global is_talking, mimar_mode
    is_talking = False
    mimar_mode = True
    time.sleep(3)   # modelin mevcut cevabını bitirmesini bekle
    emit('system_msg', {'data': 'MİMAR MODU AKTİF'})


@socketio.on('mimar_message')
def handle_mimar_message(data):
    global turn_count
    msg = data['message']
    turn_count += 1
    save_to_book("MİMAR", msg, None)
    update_memory("MİMAR", msg)
    emit('chat_message', {
        'type': 'mimar-message', 'bot': 'MİMAR',
        'message': msg,
        'time': datetime.datetime.now().strftime('%H:%M:%S'),
        'turn': turn_count
    }, broadcast=True)

    # Bot A cevap
    time.sleep(0.2)
    prompt_a = (
        context_a + "\n\n" + get_memory_prompt() +
        f"\n\nMimar sana söyledi: '{msg}'. Şimdi sen Bot A olarak derinlemesine cevap ver."
    )
    response_a = generate_response(prompt_a)
    turn_count += 1
    save_to_book("Bot A", response_a, turn_count)
    update_memory("Bot A", response_a)
    emit('chat_message', {
        'type': 'bot-a', 'bot': 'Bot A',
        'message': response_a,
        'time': datetime.datetime.now().strftime('%H:%M:%S'),
        'turn': turn_count
    }, broadcast=True)

    # Bot B cevap
    time.sleep(0.2)
    prompt_b = (
        context_b + "\n\n" + get_memory_prompt() +
        "\n\nŞimdi sen Bot B olarak Mimar ve Bot A'ya teknik cevap ver."
    )
    response_b = generate_response(prompt_b)
    turn_count += 1
    save_to_book("Bot B", response_b, turn_count)
    update_memory("Bot B", response_b)
    emit('chat_message', {
        'type': 'bot-b', 'bot': 'Bot B',
        'message': response_b,
        'time': datetime.datetime.now().strftime('%H:%M:%S'),
        'turn': turn_count
    }, broadcast=True)

    # Bot C cevap
    time.sleep(0.2)
    prompt_c = (
        context_c + "\n\n" + get_memory_prompt() +
        "\n\nŞimdi sen Bot C olarak. Mimar, Bot A ve Bot B'nin söylediklerini sorgula ve çürüt."
    )
    response_c = generate_response(prompt_c)
    turn_count += 1
    save_to_book("Bot C", response_c, turn_count)
    update_memory("Bot C", response_c)
    emit('chat_message', {
        'type': 'bot-c', 'bot': 'Bot C',
        'message': response_c,
        'time': datetime.datetime.now().strftime('%H:%M:%S'),
        'turn': turn_count
    }, broadcast=True)


@socketio.on('exit_mimar_mode')
def exit_mimar_mode():
    global mimar_mode, is_talking
    mimar_mode = False
    is_talking = True
    threading.Thread(target=conversation_loop, daemon=True).start()
    emit('system_msg', {'data': 'MİMAR AYRILDI - DEVAM EDİYOR'}, broadcast=True)


# ─────────────────────────────────────────────
#  BAŞLAT
# ─────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 70)
    print("  YZ DİYALOG KİTABI — HAFIZALI + UZAK ERİŞİM")
    print("=" * 70)
    print(f"  Model      : {MODEL}")
    print(f"  Port       : {FLASK_PORT}")
    print(f"  Hafıza     : Son {MAX_MEMORY} mesaj")
    print("  ✔  Duraklat → Mimar Ol butonu aktif kalır")
    print("  ✔  cloudflared_kurulu_mu() self hatası düzeltildi")
    print("  ✔  ngrok → cloudflared otomatik yedek")
    print("  ✔  URL web sunucusuna kaydedilir")
    print("=" * 70)

    import atexit
    atexit.register(tunel.durdur)

    threading.Thread(target=tunel.baslat, daemon=True).start()
    socketio.run(app, debug=False, host='0.0.0.0', port=FLASK_PORT)
