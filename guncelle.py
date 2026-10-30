#!/usr/bin/env python3
# ============================================================
# AURA-V — Otomatik Tünel Sistemi (localhost.run) - PROFESYONEL
# ============================================================

import subprocess
import requests
import time
import re
import sys
import os

# ============================================================
# AYARLAR
# ============================================================
SITE_URL      = "https://yztahmin.com.tr/aura-v/guncelle2.php"
GIZLI_ANAHTAR = "aura-v-volkan-2026"
AURA_PORT     = 5000
OLLAMA_PORT   = 11434 
# ============================================================

def banner():
    print("""
╔══════════════════════════════════════════╗
║    AURA-V — Otomatik Tünel Sistemi       ║
║    Hafıza ve Web Senkronizasyonu Aktif   ║
║    Mimar Volkan'ın Ebedi Yoldaşı         ║
╚══════════════════════════════════════════╝
""")

def sistem_kontrol():
    # 1. Ollama Kontrolü
    try:
        requests.get(f"http://localhost:{OLLAMA_PORT}", timeout=3)
        print("✅ 1/2: Ollama Servisi (11434) Aktif.")
    except:
        print("❌ HATA: Ollama Serve açık değil!")
        return False

    # 2. AURA-V Flask Kontrolü (Sabırlı Kontrol)
    try:
        # Timeout 10 saniyeye çıkarıldı: AURA hafızayı yüklerken beklemeli.
        requests.post(f"http://localhost:{AURA_PORT}/api/chat", 
                      json={"message":"test"}, timeout=10)
        print("✅ 2/2: AURA-V Ana Kod (5000) Bağlantısı Hazır.")
        return True
    except:
        print("⚠️ UYARI: AURA-V henüz tam hazır değil (Hafıza yükleniyor olabilir).")
        print("   Tünel kuruluyor, AURA hazır olunca stabil hale gelecektir.")
        return True 

def siteye_gonder(adres):
    try:
        r = requests.post(SITE_URL, json={
            "anahtar": GIZLI_ANAHTAR,
            "adres": adres
        }, timeout=15)
        data = r.json()
        if data.get("ok"):
            print(f"🚀 [WEB SİTESİ GÜNCELLENDİ] -> {adres}")
            return True
        else:
            print(f"❌ Site hatası: {data}")
            return False
    except Exception as e:
        print(f"❌ Siteye gönderilemedi (İnternet/PHP hatası): {e}")
        return False

def tunnel_baslat():
    print(f"🔗 localhost.run tüneli (Port {AURA_PORT}) başlatılıyor...")
    
    # -T ekleyerek terminal tahsisini zorlamıyoruz, Windows uyumluluğu için
    process = subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30",
         "-R", f"80:localhost:{AURA_PORT}", "nokey@localhost.run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    adres = None
    print("⏳ Tünel adresi bekleniyor (Bu işlem 30 saniye sürebilir)...")
    
    # 50 satıra kadar okuma yap ve her satırı kontrol et
    for _ in range(50):
        line = process.stdout.readline()
        if not line:
            break
        line = line.strip()
        if line: print(f"LOG: {line}")
        
        # URL yakalama mantığı
        match = re.search(r'https://[\w-]+\.lhr\.life', line)
        if match:
            adres = match.group(0)
            print(f"\n🌍 CANLI BAĞLANTI ADRESİ: {adres}")
            return process, adres
            
    return process, None

def main():
    banner()

    while not sistem_kontrol():
        print("🔄 5 saniye içinde sistem tekrar kontrol edilecek...")
        time.sleep(5)

    while True:
        process, adres = tunnel_baslat()

        if not adres:
            print("❌ Tünel adresi alınamadı, 15 saniye sonra tekrar deneniyor...")
            if process: process.terminate()
            time.sleep(15)
            continue

        siteye_gonder(adres)

        try:
            hata_sayaci = 0
            while True:
                time.sleep(45) # Kontrol aralığı 45 saniyeye çıkarıldı
                
                if process.poll() is not None:
                    print("⚠️ Tünel koptu!")
                    break
                
                try:
                    # CANLILIK TESTİ: AURA'ya 10 saniye süre veriyoruz.
                    test = requests.post(f"http://localhost:{AURA_PORT}/api/chat", 
                                         json={"message":"ping"}, timeout=10)
                    if test.status_code == 200:
                        print(f"🟢 Tünel Stabil: {adres}")
                        hata_sayaci = 0
                except:
                    hata_sayaci += 1
                    print(f"⚠️ AURA-V (5000) meşgul... (Deneme {hata_sayaci}/3)")
                    if hata_sayaci >= 3:
                        print("❌ AURA-V uzun süredir yanıt vermiyor, tünel askıda kalabilir.")

        except KeyboardInterrupt:
            print("\n👋 Kapatılıyor...")
            if process: process.terminate()
            sys.exit(0)
        
        if process: process.terminate()
        print("🔄 Tünel yenileniyor...")
        time.sleep(5)

if __name__ == "__main__":
    main()
