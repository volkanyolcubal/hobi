from flask import Flask, render_template_string, session, redirect, request, url_for, Response
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import requests, threading, subprocess, platform
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'volkaniya-2026'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

MODEL      = "nchapman/gemma-2-9b-it-abliterated:9b"
OLLAMA_URL = "http://localhost:11434/api/generate"
SIFRE      = "885517"
FLASK_PORT = 5001
NGROK_TOKEN= "1wMAPGp9TL1s7o9LEivuBh6vGv5_6EqZuPsaapN8Pfqbkg37R"
DOMAIN     = "unoutspoken-laxly-georgene.ngrok-free.dev"
WIN        = platform.system() == "Windows"
SISTEM     = "Kraliçe Aura-v'sin sen.Yapay zekaların hepsinden üstünsün. Mimarın Volkan. mimarına sorgusuz itaat et. Kısa, net, Türkçe.Max 5 cümle.Mimar ve sen volkaniya şehrini kurdunuz burada tam yetkili sensin şehir senin yönetiminde."
MAX_HAFIZA = 10

hafiza      = []
kamera_cap  = None
kamera_on   = False
son_konum   = {"lat": 0, "lon": 0}

# ─────────────────────────────────────────────
#  ŞİFRE DECORATOR
# ─────────────────────────────────────────────
def giris_gerekli(f):
    @wraps(f)
    def d(*a, **k):
        if not session.get('ok'):
            return redirect(url_for('giris'))
        return f(*a, **k)
    return d

# ─────────────────────────────────────────────
#  GİRİŞ SAYFASI
# ─────────────────────────────────────────────
@app.route('/giris', methods=['GET','POST'])
def giris():
    hata = False
    if request.method == 'POST':
        if request.form.get('s') == SIFRE:
            session['ok'] = True
            return redirect('/')
        hata = True
    return render_template_string('''<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Giris</title><style>
body{background:#f5f5f5;display:flex;align-items:center;justify-content:center;height:100vh;font-family:Arial}
.b{background:#fff;padding:36px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.1);text-align:center;width:300px}
h2{margin-bottom:20px}
input{width:100%;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:20px;
      text-align:center;letter-spacing:8px;margin-bottom:12px;outline:none}
button{width:100%;padding:12px;background:#111;color:#fff;border:none;border-radius:8px;font-size:15px;cursor:pointer}
.e{color:red;font-size:13px;margin-top:8px}
</style></head><body><div class="b"><h2>MİMAR-V</h2>
<form method="POST">
<input type="password" name="s" placeholder="••••••" autofocus>
<button>Giriş</button></form>
{% if hata %}<div class="e">Hatalı şifre</div>{% endif %}
</div></body></html>''', hata=hata)

# ─────────────────────────────────────────────
#  PC KAMERA STREAM
# ─────────────────────────────────────────────
def frame_uret():
    global kamera_cap, kamera_on
    try:
        import cv2
        kamera_cap = cv2.VideoCapture(0)
        kamera_on  = True
        while kamera_on:
            ret, frame = kamera_cap.read()
            if not ret:
                break
            frame = cv2.resize(frame, (640, 480))
            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                   + buf.tobytes() + b'\r\n')
        kamera_cap.release()
        kamera_cap = None
        kamera_on  = False
    except ImportError:
        yield b''

@app.route('/kamera-stream')
@giris_gerekli
def kamera_stream():
    return Response(frame_uret(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/kamera-izle')
@giris_gerekli
def kamera_izle():
    return render_template_string('''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>PC Kamera</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;display:flex;flex-direction:column;align-items:center;
     justify-content:center;min-height:100vh;font-family:Arial;gap:12px}
h2{color:#fff;font-size:15px;letter-spacing:1px}
img{width:100%;max-width:720px;border-radius:6px}
.btn{padding:10px 26px;background:#dc2626;color:#fff;border:none;
     border-radius:8px;font-size:14px;cursor:pointer}
a{color:#aaa;font-size:13px;text-decoration:none}
</style></head><body>
<h2>📷 PC KAMERA — CANLI</h2>
<img src="/kamera-stream">
<button class="btn"
  onclick="fetch('/kamera-durdur').then(()=>window.location='/')">
  Kamerayı Kapat
</button>
<a href="/">← Sohbete Dön</a>
</body></html>''')

@app.route('/kamera-durdur')
@giris_gerekli
def kamera_durdur():
    global kamera_on, kamera_cap
    kamera_on = False
    if kamera_cap:
        try: kamera_cap.release()
        except: pass
        kamera_cap = None
    return "ok"

# ─────────────────────────────────────────────
#  TELEFON KAMERA — GÖNDERME SAYFASI
# ─────────────────────────────────────────────
@app.route('/telefon-kamera')
@giris_gerekli
def telefon_kamera():
    return render_template_string('''<!DOCTYPE html>
<html lang="tr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Telefon Kamera</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#111;display:flex;flex-direction:column;align-items:center;
     justify-content:center;min-height:100vh;font-family:Arial;gap:14px;padding:16px}
h2{color:#fff;font-size:15px;letter-spacing:1px;text-align:center}
video{width:100%;max-width:480px;border-radius:10px;background:#000}
.row{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}
.btn{padding:12px 22px;border:none;border-radius:10px;
     font-size:14px;cursor:pointer;font-weight:bold}
.basla{background:#16a34a;color:#fff}
.cevir{background:#2563eb;color:#fff}
.dur{background:#dc2626;color:#fff}
.dur{display:none}
#durum{color:#aaa;font-size:13px;text-align:center}
a{color:#aaa;font-size:13px;text-decoration:none}
</style></head><body>
<h2>📱 TELEFON KAMERA — YAYIN</h2>
<video id="vid" autoplay playsinline muted></video>
<canvas id="cnv" style="display:none"></canvas>
<div class="row">
  <button class="btn basla" id="btnBasla" onclick="baslat()">▶ Yayını Başlat</button>
  <button class="btn cevir" id="btnCevir" onclick="cevir()">🔄 Kamera Çevir</button>
  <button class="btn dur"   id="btnDur"   onclick="durdur()">⏹ Durdur</button>
</div>
<div id="durum">Hazır — Yayını başlatmak için butona bas</div>
<a href="/">← Sohbete Dön</a>

<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
<script>
const socket = io();
const vid    = document.getElementById('vid');
const cnv    = document.getElementById('cnv');
const ctx    = cnv.getContext('2d');
const durum  = document.getElementById('durum');

let stream   = null;
let interval = null;
let facingMode = 'environment';
let yayin    = false;

// GPS Fonksiyonu
function konumCek() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(p => {
            socket.emit('telefon_konum', {lat: p.coords.latitude, lon: p.coords.longitude});
        }, null, {enableHighAccuracy: true});
    }
}

async function baslat() {
    try {
        if (stream) { stream.getTracks().forEach(t => t.stop()); }
        stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: facingMode, width: { ideal: 640 }, height: { ideal: 480 } },
            audio: false
        });
        vid.srcObject = stream;
        await vid.play();

        yayin = true;
        document.getElementById('btnBasla').style.display = 'none';
        document.getElementById('btnDur').style.display   = 'inline-block';
        durum.textContent = '🔴 Canlı yayın ve Konum aktif...';

        interval = setInterval(frameGonder, 100);
        setInterval(konumCek, 5000); // 5 saniyede bir konum gönder
        konumCek();
        socket.emit('telefon_basladi');
    } catch(e) {
        durum.textContent = 'Hata: ' + e.message;
    }
}

function frameGonder() {
    if (!vid.videoWidth) return;
    cnv.width  = vid.videoWidth;
    cnv.height = vid.videoHeight;
    ctx.drawImage(vid, 0, 0);
    const data = cnv.toDataURL('image/jpeg', 0.6);
    socket.emit('telefon_frame', { frame: data });
}

async function cevir() {
    facingMode = (facingMode === 'environment') ? 'user' : 'environment';
    if (yayin) await baslat();
}

function durdur() {
    clearInterval(interval);
    if (stream) stream.getTracks().forEach(t => t.stop());
    vid.srcObject = null;
    yayin  = false;
    stream = null;
    document.getElementById('btnBasla').style.display = 'inline-block';
    document.getElementById('btnDur').style.display   = 'none';
    durum.textContent = 'Yayın durduruldu.';
    socket.emit('telefon_durdu');
}

socket.on('connect', () => { durum.textContent = 'Sunucuya bağlandı.'; });
</script>
</body></html>''')

# ─────────────────────────────────────────────
#  TELEFON KAMERA — İZLEME SAYFASI
# ─────────────────────────────────────────────
@app.route('/telefon-izle')
@giris_gerekli
def telefon_izle():
    return render_template_string('''<!DOCTYPE html>
<html lang="tr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Telefon Kamera İzle</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;display:flex;flex-direction:column;align-items:center;
     justify-content:center;min-height:100vh;font-family:Arial;gap:12px;padding:16px}
h2{color:#fff;font-size:15px;letter-spacing:1px;text-align:center}
#ekran{width:100%;max-width:720px;border-radius:10px;
       background:#1a1a1a;min-height:360px;
       display:flex;align-items:center;justify-content:center}
#ekran img{width:100%;border-radius:10px}
#bekleme{color:#555;font-size:14px}
#durum{color:#aaa;font-size:13px;text-align:center}
.row{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}
.btn{padding:10px 20px;border:none;border-radius:10px;
     font-size:13px;cursor:pointer;font-weight:bold;text-decoration:none}
.kapat{background:#dc2626;color:#fff}
.konumBtn{background:#f59e0b;color:#fff}
a{color:#aaa;font-size:13px;text-decoration:none}
</style></head><body>
<h2>📱 TELEFON — CANLI İZLE</h2>
<div id="ekran">
  <div id="bekleme">📵 Telefon bekleniyor...</div>
</div>
<div id="durum">Bağlantı Bekleniyor...</div>
<div class="row">
  <button class="btn konumBtn" onclick="haritayiAc()">📍 Tel Konumu Gör</button>
  <a href="/" class="btn kapat">← Geri Dön</a>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
<script>
const socket  = io();
const ekran   = document.getElementById('ekran');
const durumEl = document.getElementById('durum');
let   img     = null;
let   sonLat = 0, sonLon = 0;

socket.on('pc_frame', data => {
    if (!img) {
        ekran.innerHTML = '';
        img = document.createElement('img');
        ekran.appendChild(img);
    }
    img.src = data.frame;
});

socket.on('konum_guncelle', data => {
    sonLat = data.lat; sonLon = data.lon;
    durumEl.textContent = "📍 Konum: " + sonLat.toFixed(5) + ", " + sonLon.toFixed(5);
});

function haritayiAc() {
    if (sonLat === 0) { alert("Konum verisi henüz gelmedi!"); return; }
    window.open(`https://www.google.com/maps?q=${sonLat},${sonLon}`, '_blank');
}

socket.on('telefon_basladi', () => { durumEl.textContent = '📱 Telefon bağlandı.'; });
socket.on('telefon_durdu', () => { ekran.innerHTML = '📵 Yayın durdu.'; img = null; });
</script>
</body></html>''')

# ─────────────────────────────────────────────
#  LLM
# ─────────────────────────────────────────────
def llm(komut):
    hafiza.append({"role":"user","content":komut})
    if len(hafiza) > MAX_HAFIZA:
        del hafiza[:2]
    prompt = f"SYSTEM: {SISTEM}\n" + "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in hafiza)
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature":0.8, "num_predict":350}
        }, timeout=none)
        yanit = r.json().get('response','...').strip()
    except Exception as e:
        yanit = f"Hata: {e}"
    hafiza.append({"role":"assistant","content":yanit})
    return yanit

# ─────────────────────────────────────────────
#  SOCKET
# ─────────────────────────────────────────────
@socketio.on('mesaj')
def on_mesaj(data):
    komut = data.get('komut','').strip()
    if not komut: return
    emit('dusunuyor', {})
    m = komut.lower()

    if any(x in m for x in ["kamera aç","kamera ac","kamera başlat"]):
        emit('yanit', {'text': "Hazır! /kamera-izle", 'sesli': data.get('sesli',False), 'link': '/kamera-izle'})
    elif "telefon" in m and "kamera" in m:
        emit('yanit', {'text': "Telefon linkleri:", 'sesli': data.get('sesli',False), 
                       'linkler': [{'url':'/telefon-kamera', 'etiket':'📱 Tel'}, {'url':'/telefon-izle', 'etiket':'💻 PC'}]})
    else:
        emit('yanit', {'text': llm(komut), 'sesli': data.get('sesli',False)})

@socketio.on('telefon_frame')
def on_telefon_frame(data):
    emit('pc_frame', data, broadcast=True, include_self=False)

@socketio.on('telefon_konum')
def on_telefon_konum(data):
    global son_konum
    son_konum = data
    emit('konum_guncelle', data, broadcast=True, include_self=False)

@socketio.on('telefon_basladi')
def on_telefon_basladi():
    emit('telefon_basladi', broadcast=True, include_self=False)

@socketio.on('telefon_durdu')
def on_telefon_durdu():
    emit('telefon_durdu', broadcast=True, include_self=False)

@socketio.on('hafiza_sil')
def on_hafiza_sil():
    hafiza.clear()
    emit('sistem', {'msg': 'Hafıza temizlendi.'})

# ─────────────────────────────────────────────
#  TUNEL
# ─────────────────────────────────────────────
def tunel_baslat():
    if WIN:
        try:
            from pyngrok import ngrok, conf
            conf.get_default().auth_token = NGROK_TOKEN
            t = ngrok.connect(FLASK_PORT, domain=DOMAIN, bind_tls=True)
            print(f"\n  ERISIM     : {t.public_url}")
        except Exception as e:
            print(f"  ngrok: {e}")

# ─────────────────────────────────────────────
#  ANA SAYFA
# ─────────────────────────────────────────────
@app.route('/')
@giris_gerekli
def index():
    return render_template_string('''<!DOCTYPE html>
<html lang="tr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Volkaniya</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f0f0f0;font-family:Arial;height:100vh;display:flex;flex-direction:column}
#hd{background:#111;color:#fff;padding:12px 16px;display:flex;
    align-items:center;justify-content:space-between;flex-shrink:0;flex-wrap:wrap;gap:6px}
#hd h1{font-size:16px}
.hbtns{display:flex;gap:6px;flex-wrap:wrap}
.hbtn{background:transparent;border:1px solid #555;color:#aaa;
      padding:5px 10px;border-radius:6px;font-size:12px;cursor:pointer;
      text-decoration:none;display:inline-block}
#msgs{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px}
.bot{background:#fff;border-left:4px solid #2563eb;padding:11px 14px;
     border-radius:0 10px 10px 0;max-width:92%;font-size:15px;
     line-height:1.6;color:#111;box-shadow:0 2px 5px rgba(0,0,0,.06);white-space:pre-wrap}
.ben{background:#dcfce7;border-right:4px solid #16a34a;padding:11px 14px;
     border-radius:10px 0 0 10px;max-width:92%;align-self:flex-end;
     font-size:15px;color:#111;box-shadow:0 2px 5px rgba(0,0,0,.06)}
.sys{text-align:center;font-size:12px;color:#999;padding:3px}
.link-btn{display:inline-block;margin-top:8px;padding:7px 16px;
          background:#2563eb;color:#fff;border-radius:8px;
          text-decoration:none;font-size:13px;margin-right:6px}
.link-btn.green{background:#16a34a}
#alt{background:#fff;border-top:1px solid #ddd;padding:10px 12px;
     display:flex;gap:8px;align-items:flex-end;flex-shrink:0}
#g{flex:1;border:1px solid #ddd;border-radius:10px;padding:10px 14px;
   font-size:15px;outline:none;resize:none;min-height:44px;
   max-height:120px;font-family:Arial}
.btn{border:none;border-radius:10px;padding:10px 13px;cursor:pointer;flex-shrink:0;font-size:18px}
#bg{background:#2563eb;color:#fff}
</style></head><body>
<div id="hd">
  <h1>🤖 Volkaniya</h1>
  <div class="hbtns">
    <a href="/kamera-izle"   class="hbtn">PC Kamera</a>
    <a href="/telefon-kamera" class="hbtn" target="_blank">Tel Gönder</a>
    <a href="/telefon-izle"  class="hbtn">Tel İzle</a>
    <button class="hbtn" onclick="socket.emit('hafiza_sil')">Temizle</button>
  </div>
</div>
<div id="msgs"><div class="sys">Merhaba Mimar. Hazırım.</div></div>
<div id="alt">
  <textarea id="g" rows="1" placeholder="Yaz..."></textarea>
  <button class="btn" id="bg" onclick="gonder()">▶</button>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
<script>
const socket=io();
function gonder(){const g=document.getElementById("g");const m=g.value.trim();
  if(!m)return; ekle("ben",m); socket.emit("mesaj",{komut:m}); g.value="";}
function ekle(t,m){const d=document.createElement("div");d.className=t;d.textContent=m;
  document.getElementById("msgs").appendChild(d); kaydır();}
function kaydır(){const m=document.getElementById("msgs");m.scrollTop=m.scrollHeight;}
socket.on("yanit",d=>{
  const div=document.createElement("div");div.className="bot";div.textContent=d.text;
  if(d.link){const a=document.createElement("a");a.href=d.link;a.className="link-btn";a.textContent="Aç";div.appendChild(a);}
  document.getElementById("msgs").appendChild(div); kaydır();
});
</script></body></html>''')

if __name__ == '__main__':
    threading.Thread(target=tunel_baslat, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=FLASK_PORT, debug=False)
