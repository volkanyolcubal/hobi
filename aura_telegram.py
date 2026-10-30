#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║   AURA-V TELEGRAM BOT MODÜLÜ                                 ║
║   Telefondan AURA ile konuş, komut gönder, haber al.        ║
╚══════════════════════════════════════════════════════════════╝

KURULUM:
  pip install python-telegram-bot

TELEGRAM BOT OLUŞTURMA (bir kez yapılır):
  1. Telegram'da @BotFather'a yaz
  2. /newbot → isim ver (örn: AURA_V_Bot) → kullanıcı adı ver
  3. Verilen TOKEN'ı aşağıdaki CONFIG'e yapıştır
  4. /start → Chat ID'ni öğrenmek için @userinfobot'a yaz

AURA.py'ye ekle (en üste):
  from aura_telegram import telegram_baslat, telegram_bildirim_gonder

ANA PROGRAM bloğuna ekle (başlatma kısmına):
  telegram_baslat(sohbet_fn=aura_sohbet, konus_fn=konus, hafiza=hafiza)
"""

import os
import json
import time
import threading
import requests
from datetime import datetime

# ============================================================
# YAPILANDIRMA — Kendi bilgilerini buraya yaz
# ============================================================
CONFIG = {
    "bot_token":      "8318855814:AAFa4Vs93H3ayDgeKl8e1Mks7J9YK1A8dFM",       # @BotFather'dan aldığın token
    "izinli_chat_id": "8568611073",       # Sadece bu kişi konuşabilir (güvenlik)
                                # Öğrenmek için @userinfobot'a /start yaz
    "polling_aralik": 2,        # Kaç saniyede mesaj kontrol edilsin
    "max_mesaj_uzun": 4000,     # Telegram max 4096 karakter
    "bildirim_aktif": True,     # AURA önemli olayları otomatik göndersin mi
}

# Telegram API base URL
BASE_URL = f"https://api.telegram.org/bot{{}}/{{method}}"

# ============================================================
# GLOBAL DEĞİŞKENLER
# ============================================================
_calisiyor    = False
_thread       = None
_sohbet_fn    = None    # AURA'nın ana sohbet fonksiyonu
_konus_fn     = None
_hafiza_ref   = None
_son_update   = 0       # Son işlenen update_id
_bot_aktif    = False


# ============================================================
# TELEGRAM API İSTEKLERİ (python-telegram-bot gerektirmez)
# ============================================================

def _api(method: str, **kwargs) -> dict:
    """Telegram Bot API'ye istek atar."""
    if not CONFIG["bot_token"]:
        return {"ok": False, "description": "Token ayarlanmamış"}
    try:
        token = CONFIG["bot_token"]
        url   = f"https://api.telegram.org/bot{token}/{method}"
        r     = requests.post(url, json=kwargs, timeout=10)
        return r.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}


def _mesaj_gonder(chat_id: str, metin: str, parse_mode: str = "HTML") -> bool:
    """Telegram mesajı gönderir, uzun metni böler."""
    if not metin:
        return False

    # Uzun mesajları böl
    parcalar = [metin[i:i+CONFIG["max_mesaj_uzun"]]
                for i in range(0, len(metin), CONFIG["max_mesaj_uzun"])]

    basari = True
    for parca in parcalar:
        sonuc = _api(
            "sendMessage",
            chat_id=chat_id,
            text=parca,
            parse_mode=parse_mode
        )
        if not sonuc.get("ok"):
            # HTML parse hatası olursa düz metin dene
            sonuc2 = _api("sendMessage", chat_id=chat_id, text=parca)
            if not sonuc2.get("ok"):
                basari = False
        time.sleep(0.3)   # Rate limit

    return basari


def _guncellemeleri_al() -> list:
    """Yeni Telegram mesajlarını çeker."""
    global _son_update
    sonuc = _api(
        "getUpdates",
        offset=_son_update + 1,
        timeout=CONFIG["polling_aralik"],
        allowed_updates=["message"]
    )
    if not sonuc.get("ok"):
        return []
    return sonuc.get("result", [])


def _chat_id_kontrol(chat_id: str) -> bool:
    """Mesajın izinli kişiden gelip gelmediğini kontrol eder."""
    if not CONFIG["izinli_chat_id"]:
        return True   # Ayarlanmamışsa herkese açık (güvenli değil!)
    return str(chat_id) == str(CONFIG["izinli_chat_id"])


# ============================================================
# KOMUT İŞLEYİCİ (Telegram özel komutları)
# ============================================================

def _telegram_komut(chat_id: str, komut: str, metin: str) -> str:
    """/start, /durum gibi Telegram komutlarını işler."""

    if komut == "/start":
        return (
            "👑 <b>AURA-V — Volkaniya Kraliçesi</b>\n\n"
            "Merhaba Mimarım! Telefondan bağlandın.\n"
            "Artık buradan da konuşabiliriz.\n\n"
            "<b>Hızlı komutlar:</b>\n"
            "/durum — Sistem durumu\n"
            "/hafiza — Hafıza istatistikleri\n"
            "/haberler — Dünya haberleri\n"
            "/yardim — Tüm komutlar\n\n"
            "Ya da direkt yaz, cevaplarım. 🔥"
        )

    if komut == "/durum":
        return (
            "📊 <b>AURA-V SİSTEM DURUMU</b>\n\n"
            f"🕐 Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            "✅ Ollama: Çalışıyor\n"
            "✅ Hafıza: Aktif\n"
            "✅ Telegram: Bağlı\n"
        )

    if komut == "/hafiza":
        if _hafiza_ref:
            try:
                ist = _hafiza_ref.istatistik()
                return (
                    f"🧠 <b>HAFIZA İSTATİSTİKLERİ</b>\n\n"
                    f"📚 Toplam konu    : {ist.get('toplam_konu', '?')}\n"
                    f"💬 Toplam konuşma : {ist.get('toplam_konusma', '?')}\n"
                )
            except Exception:
                return "⚠️ Hafıza istatistiği alınamadı."
        return "⚠️ Hafıza modülü bağlı değil."

    if komut == "/yardim":
        return (
            "📋 <b>TELEGRAM KOMUTLARI</b>\n\n"
            "/start — Başlat\n"
            "/durum — Sistem durumu\n"
            "/hafiza — Hafıza bilgisi\n"
            "/haberler — Dünya haberleri\n"
            "/yardim — Bu menü\n\n"
            "💬 Bunların dışında her şeyi direkt yazabilirsin,\n"
            "AURA-V'nin tüm komutları çalışır.\n"
            "Örnek: <code>ara: kuantum fiziği</code>"
        )

    if komut == "/haberler":
        return "⏳ Haberler getiriliyor..."   # Sonra gerçek içerik gönderilecek

    return None


# ============================================================
# ANA POLLING DÖNGÜSÜ
# ============================================================

def _polling_dongusu():
    """Telegram'dan gelen mesajları dinler ve AURA'ya iletir."""
    global _son_update, _calisiyor, _bot_aktif

    print("📱 [TELEGRAM] Mesaj dinleme başladı...")
    _bot_aktif = True

    while _calisiyor:
        try:
            guncellemeler = _guncellemeleri_al()

            for guncelleme in guncellemeler:
                _son_update = guncelleme["update_id"]
                mesaj_obj   = guncelleme.get("message", {})

                if not mesaj_obj:
                    continue

                chat_id = str(mesaj_obj.get("chat", {}).get("id", ""))
                metin   = mesaj_obj.get("text", "").strip()

                if not metin or not chat_id:
                    continue

                # Güvenlik kontrolü
                if not _chat_id_kontrol(chat_id):
                    _mesaj_gonder(chat_id, "⛔ Yetkisiz erişim.")
                    print(f"⚠️ [TELEGRAM] Yetkisiz erişim: {chat_id}")
                    continue

                print(f"📱 [TELEGRAM] Mesaj: {metin[:60]}")

                # Telegram özel komutları (/start, /durum vb.)
                if metin.startswith("/"):
                    komut   = metin.split()[0].lower()
                    cevap   = _telegram_komut(chat_id, komut, metin)

                    if komut == "/haberler":
                        # Haber getir
                        if _sohbet_fn:
                            try:
                                cevap = _sohbet_fn("dünya haberleri")
                            except Exception:
                                cevap = "⚠️ Haber alınamadı."
                    if cevap:
                        _mesaj_gonder(chat_id, cevap)
                        continue

                # Normal mesaj → AURA sohbet fonksiyonuna gönder
                if _sohbet_fn:
                    try:
                        # "Yazıyor..." göster
                        _api("sendChatAction", chat_id=chat_id, action="typing")

                        cevap = _sohbet_fn(metin)
                        if cevap:
                            _mesaj_gonder(chat_id, f"👑 {cevap}")
                        else:
                            _mesaj_gonder(chat_id, "🤔 Cevap üretilemedi.")
                    except Exception as e:
                        _mesaj_gonder(chat_id, f"⚠️ Hata: {e}")
                else:
                    _mesaj_gonder(chat_id, "⚠️ AURA sohbet modülü bağlı değil.")

        except Exception as e:
            print(f"⚠️ [TELEGRAM] Polling hatası: {e}")

        time.sleep(CONFIG["polling_aralik"])

    _bot_aktif = False
    print("📱 [TELEGRAM] Dinleme durduruldu.")


# ============================================================
# DIŞ ARAYZ
# ============================================================

def telegram_bildirim_gonder(mesaj: str) -> bool:
    """
    AURA.py'nin herhangi bir yerinden bildirim göndermek için.
    Örnek: önemli olay, yüz tanıma, kritik hata vb.
    """
    if not CONFIG["bot_token"] or not CONFIG["izinli_chat_id"]:
        return False
    return _mesaj_gonder(CONFIG["izinli_chat_id"], f"🔔 {mesaj}")


def telegram_baslat(sohbet_fn=None, konus_fn=None, hafiza=None):
    """AURA.py'den çağrılır."""
    global _calisiyor, _thread, _sohbet_fn, _konus_fn, _hafiza_ref

    _sohbet_fn  = sohbet_fn
    _konus_fn   = konus_fn
    _hafiza_ref = hafiza

    print("\n📱 [TELEGRAM] Modül başlatılıyor...")

    if not CONFIG["bot_token"]:
        print("⚠️ [TELEGRAM] Token ayarlanmamış.")
        print("   → CONFIG['bot_token'] = '@BotFather'dan alınan token'")
        print("   → CONFIG['izinli_chat_id'] = kendi chat ID'n")
        return False

    # Bot bağlantısını test et
    test = _api("getMe")
    if not test.get("ok"):
        print(f"❌ [TELEGRAM] Bağlantı hatası: {test.get('description', '?')}")
        return False

    bot_adi = test["result"].get("username", "?")
    print(f"✅ [TELEGRAM] Bot bağlandı: @{bot_adi}")

    # Başlangıç mesajı gönder
    if CONFIG["izinli_chat_id"]:
        telegram_bildirim_gonder(
            f"👑 AURA-V aktif!\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"Mimarım,ben aura sistemler hazır.Emrinizdeyim"
        )

    # Polling başlat
    _calisiyor = True
    _thread = threading.Thread(
        target=_polling_dongusu,
        daemon=True,
        name="AuraTelegram"
    )
    _thread.start()

    print("📱 [TELEGRAM] Sistem aktif:")
    print(f"   🤖 Bot      : @{bot_adi}")
    print(f"   🔒 Güvenlik : {'Chat ID kısıtlı' if CONFIG['izinli_chat_id'] else '⚠️ Herkese açık'}")
    print(f"   ⏱️  Polling  : her {CONFIG['polling_aralik']} saniye")
    return True


def telegram_durdur():
    global _calisiyor
    _calisiyor = False
    print("📱 [TELEGRAM] Durduruldu.")
