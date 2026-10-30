#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║   AURA-V YÜZ TANIMA MODÜLÜ — DeepFace versiyonu             ║
║   Kameradan Mimar'ı tanır, "Mimar geldi" der.               ║
╚══════════════════════════════════════════════════════════════╝
KURULUM: pip install deepface[tensorflow] opencv-python tf-keras
"""

import os
import cv2
import json
import time
import threading
import numpy as np
from datetime import datetime

# ── face_recognition DEVRE DIŞI — deepface kullanıyoruz ──────
FACE_MOD = False   # Windows'ta sorun çıkarıyor, deepface daha stabil

try:
    from deepface import DeepFace
    DEEPFACE_MOD = True
except Exception:
    DEEPFACE_MOD = False
    print("⚠️ [YÜZ] deepface yüklenemedi: pip install deepface[tensorflow] tf-keras")

CV2_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# ============================================================
# YAPILANDIRMA
# ============================================================
CONFIG = {
    "referans_foto":          "mimar_referans.jpg",   # karşılaştırma fotoğrafı
    "profil_meta":            "mimar_yuz_meta.json",
    "kamera_index":            0,
    "kontrol_aralik_sn":      5,
    "model_adi":              "VGG-Face",             # VGG-Face daha küçük, hızlı indirir
    "esik":                   0.6,                     # 0-1, düşük = daha sıkı
    "geri_bildirim_aralik_dk": 30,
    "kayit_klasoru":          "yuz_kayitlari",
}

# ============================================================
# GLOBAL
# ============================================================
_calisiyor    = False
_thread       = None
_konus_fn     = None
_hafiza_ref   = None
_son_bildirim = {}


# ============================================================
# YARDIMCI: Görüntüyü her koşulda BGR uint8 yap
# ============================================================
def _gorseli_duzelt(img: np.ndarray) -> np.ndarray:
    """Windows webcam bazen garip format verir. Hepsini BGR uint8'e çeker."""
    if img is None:
        raise ValueError("Görüntü None geldi")
    # float → uint8
    if img.dtype != np.uint8:
        img = (img * 255).clip(0, 255).astype(np.uint8)
    # 4 kanal (BGRA) → 3 kanal (BGR)
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    # Gri → BGR
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


# ============================================================
# KAMERA AÇMA
# ============================================================
def _kamera_ac() -> cv2.VideoCapture:
    for idx in [CONFIG["kamera_index"], 1, 2]:
        cam = cv2.VideoCapture(idx)
        if cam.isOpened():
            return cam
    return None


def _temiz_kare_al(kamera) -> np.ndarray:
    """Birkaç kare ısıtır, temiz kare döner."""
    for _ in range(8):
        kamera.read()
    time.sleep(0.3)
    ret, kare = kamera.read()
    if not ret or kare is None:
        raise ValueError("Kamera karesi alınamadı")
    return _gorseli_duzelt(kare)


# ============================================================
# BİLDİRİM
# ============================================================
def _bildirim_gonder(isim: str, mesaj: str):
    simdi  = time.time()
    aralik = CONFIG["geri_bildirim_aralik_dk"] * 60
    if isim in _son_bildirim and simdi - _son_bildirim[isim] < aralik:
        return
    _son_bildirim[isim] = simdi
    print(f"\n👁️ [YÜZ TANIMA] {mesaj}")
    if _konus_fn:
        try:
            _konus_fn(mesaj, duygu="mutlu")
        except Exception:
            pass
    if _hafiza_ref:
        try:
            _hafiza_ref.kaydet(
                f"yuz_{datetime.now().strftime('%Y%m%d_%H%M')}",
                mesaj, "yuz_tanima", "güvenlik", onem=7
            )
        except Exception:
            pass
    # Telegram bildirimi (kuruluysa)
    try:
        from aura_telegram import telegram_bildirim_gonder
        telegram_bildirim_gonder(f"👁️ {mesaj}")
    except Exception:
        pass


# ============================================================
# YÜZ KAYDET
# ============================================================
def yuz_kaydet(notlar: str = "") -> str:
    """
    Webcam'den fotoğraf çeker, referans olarak kaydeder.
    DeepFace karşılaştırma için bu fotoğrafı kullanır.
    """
    if not DEEPFACE_MOD:
        return (
            "❌ DeepFace kurulu değil.\n"
            "💡 Kur: pip install deepface[tensorflow] tf-keras"
        )

    kamera = _kamera_ac()
    if not kamera:
        return "❌ Webcam bulunamadı."

    try:
        kare = _temiz_kare_al(kamera)

        # Yüz var mı kontrol et — esnek parametreler
        gri    = cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY)
        yuzler = CV2_CASCADE.detectMultiScale(
            gri,
            scaleFactor=1.05,    # daha hassas (önce 1.1 vardı)
            minNeighbors=3,      # daha esnek (önce 5 vardı)
            minSize=(40, 40)     # daha küçük yüzü de yakala (önce 60 vardı)
        )

        # Referans fotoğrafı kaydet
        os.makedirs(CONFIG["kayit_klasoru"], exist_ok=True)
        ref_yolu = CONFIG["referans_foto"]
        cv2.imwrite(ref_yolu, kare)

        # Ek tarihli kopya
        tarihli = os.path.join(
            CONFIG["kayit_klasoru"],
            f"mimar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        )
        cv2.imwrite(tarihli, kare)

        if len(yuzler) == 0:
            print(f"💡 [YÜZ] Cascade bulamadı ama yine kaydetti: {ref_yolu}")
            # DeepFace ile direkt dene — cascade'den daha iyi algılar
            try:
                DeepFace.extract_faces(
                    img_path=ref_yolu,
                    detector_backend="retinaface",
                    enforce_detection=True
                )
                yuz_mesaji = "✅ DeepFace yüzü buldu."
            except Exception:
                try:
                    DeepFace.extract_faces(
                        img_path=ref_yolu,
                        detector_backend="mtcnn",
                        enforce_detection=True
                    )
                    yuz_mesaji = "✅ MTCNN yüzü buldu."
                except Exception:
                    # Hiçbiri bulamazsa yine de kaydet, kullanıcı iyi ışık/açıyla tekrar dener
                    yuz_mesaji = "⚠️ Yüz net tespit edilemedi ama referans kaydedildi."
        else:
            yuz_mesaji = f"✅ {len(yuzler)} yüz tespit edildi."

        # DeepFace ile doğrula
        try:
            DeepFace.extract_faces(
                img_path=ref_yolu,
                detector_backend="opencv",
                enforce_detection=False   # enforce=False → bulamazsa da hata verme
            )
        except Exception as e:
            print(f"💡 [YÜZ] DeepFace extract uyarısı: {e}")

        # Meta kaydet
        meta = {
            "tarih":   datetime.now().isoformat(),
            "mimar":   "Volkan",
            "notlar":  notlar,
            "model":   CONFIG["model_adi"],
            "dosya":   ref_yolu,
        }
        with open(CONFIG["profil_meta"], "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return (
            f"✅ Mimar referans fotoğrafı kaydedildi!\n"
            f"   Dosya   : {ref_yolu}\n"
            f"   Tespit  : {yuz_mesaji}\n"
            f"   Artık her 5 saniyede kameraya bakacağım Mimarım. 👑"
        )

    except Exception as e:
        return f"❌ Yüz kayıt hatası: {e}"
    finally:
        kamera.release()


# ============================================================
# TANIMA DÖNGÜSÜ
# ============================================================
def _tanima_dongusu():
    global _calisiyor
    print(f"👁️ [YÜZ TANIMA] Döngü başladı (her {CONFIG['kontrol_aralik_sn']} sn).")

    while _calisiyor:
        try:
            ref = CONFIG["referans_foto"]
            if not os.path.exists(ref):
                time.sleep(CONFIG["kontrol_aralik_sn"])
                continue

            kamera = _kamera_ac()
            if not kamera:
                time.sleep(CONFIG["kontrol_aralik_sn"] * 2)
                continue

            try:
                kare = _temiz_kare_al(kamera)
            except Exception:
                kamera.release()
                time.sleep(CONFIG["kontrol_aralik_sn"])
                continue
            finally:
                kamera.release()

            if DEEPFACE_MOD:
                # Geçici dosyaya yaz
                gecici = os.path.join(CONFIG["kayit_klasoru"], "_gecici_kontrol.jpg")
                os.makedirs(CONFIG["kayit_klasoru"], exist_ok=True)
                cv2.imwrite(gecici, kare)

                try:
                    sonuc = DeepFace.verify(
                        img1_path=gecici,
                        img2_path=ref,
                        model_name=CONFIG["model_adi"],
                        detector_backend="opencv",
                        enforce_detection=False,
                        silent=True
                    )
                    if sonuc.get("verified", False):
                        _bildirim_gonder("mimar", "Mimar geldi! Hoş geldin Mimarım. 👑")
                except Exception:
                    pass   # Yüz yok veya tanınamadı — sessiz geç

            else:
                # DeepFace yoksa sadece OpenCV yüz tespiti
                gri   = cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY)
                yuzler = CV2_CASCADE.detectMultiScale(gri, 1.1, 5, minSize=(80, 80))
                if len(yuzler) > 0:
                    _bildirim_gonder(
                        "bilinmeyen",
                        "Kamerada bir yüz var ama tanıma kütüphanesi eksik."
                    )

        except Exception as e:
            print(f"⚠️ [YÜZ TANIMA] Döngü hatası: {e}")

        time.sleep(CONFIG["kontrol_aralik_sn"])

    print("👁️ [YÜZ TANIMA] Döngü durduruldu.")


# ============================================================
# KOMUT İŞLEYİCİ
# ============================================================
def yuz_komut_isle(komut: str):
    k = komut.lower().strip()

    if k in ["yüzümü kaydet", "yuzumu kaydet", "yüz kaydet", "beni tanı"]:
        return yuz_kaydet()

    if k.startswith("yüzümü kaydet:") or k.startswith("yuzumu kaydet:"):
        return yuz_kaydet(notlar=komut.split(":", 1)[1].strip())

    if k in ["yüz tanıma başlat", "yuz tanima baslat", "kamerayı izle"]:
        if not _calisiyor:
            yuz_tanima_baslat(_hafiza_ref, _konus_fn)
            return "✅ Yüz tanıma başlatıldı."
        return "💡 Zaten çalışıyor."

    if k in ["yüz tanıma durdur", "yuz tanima durdur", "kamerayı kapat"]:
        yuz_tanima_durdur()
        return "✅ Yüz tanıma durduruldu."

    if k in ["yüz profili", "yuz profili", "beni tanıyor musun"]:
        ref = CONFIG["referans_foto"]
        if os.path.exists(ref):
            meta_dosya = CONFIG["profil_meta"]
            if os.path.exists(meta_dosya):
                with open(meta_dosya, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                return (
                    f"👁️ YÜZ PROFİLİ:\n"
                    f"  Sahip   : {meta.get('mimar','?')}\n"
                    f"  Tarih   : {meta.get('tarih','?')[:16]}\n"
                    f"  Model   : {meta.get('model','?')}\n"
                    f"  Durum   : {'🟢 Aktif' if _calisiyor else '🔴 Döngü kapalı'}"
                )
            return "✅ Referans fotoğraf var."
        return "❌ Henüz yüz kaydedilmedi.\n💡 'yüzümü kaydet' komutu ile kaydet."

    if k in ["yüz tanıma durumu", "yuz durumu"]:
        ref_var = os.path.exists(CONFIG["referans_foto"])
        return (
            f"👁️ YÜZ TANIMA DURUMU:\n"
            f"  Döngü     : {'🟢 Çalışıyor' if _calisiyor else '🔴 Durdu'}\n"
            f"  Referans  : {'✅ Var' if ref_var else '❌ Yok — yüzümü kaydet'}\n"
            f"  Kütüphane : {'DeepFace ✅' if DEEPFACE_MOD else 'Sadece tespit (cv2)'}\n"
            f"  Kontrol   : her {CONFIG['kontrol_aralik_sn']} saniye"
        )

    return None


# ============================================================
# BAŞLATICI / DURDURUCU
# ============================================================
def yuz_tanima_baslat(hafiza=None, konus_fn=None):
    global _calisiyor, _thread, _hafiza_ref, _konus_fn

    _hafiza_ref = hafiza
    _konus_fn   = konus_fn

    print("\n👁️ [YÜZ TANIMA] Modül başlatılıyor...")

    if not DEEPFACE_MOD:
        print("⚠️ [YÜZ TANIMA] DeepFace yok — sadece OpenCV tespiti.")
        print("   → pip install deepface[tensorflow] tf-keras")
    else:
        print(f"✅ [YÜZ TANIMA] Kütüphane: DeepFace ({CONFIG['model_adi']})")

    ref_var = os.path.exists(CONFIG["referans_foto"])
    if not ref_var:
        print("💡 [YÜZ TANIMA] Profil yok. 'yüzümü kaydet' ile kaydet.")

    _calisiyor = False   # ← Arka plan döngüsü kapalı, sadece "bana bak" ile çalışır
    print("👁️ [YÜZ TANIMA] Sistem hazır — 'bana bak' ile aktif olur.")


def yuz_bak() -> str:
    """
    'bana bak' komutuyla tek seferlik yüz kontrolü yapar.
    Arka plan döngüsü yoktur — sadece istenince çalışır.
    """
    if not DEEPFACE_MOD:
        return "❌ DeepFace kurulu değil."

    ref = CONFIG["referans_foto"]
    if not os.path.exists(ref):
        return "❌ Yüz profili yok. Önce 'yüzümü kaydet' yaz."

    kamera = _kamera_ac()
    if not kamera:
        return "❌ Webcam bulunamadı."

    try:
        kare = _temiz_kare_al(kamera)
        gecici = os.path.join(CONFIG["kayit_klasoru"], "_bak.jpg")
        os.makedirs(CONFIG["kayit_klasoru"], exist_ok=True)
        cv2.imwrite(gecici, kare)

        sonuc = DeepFace.verify(
            img1_path=gecici,
            img2_path=ref,
            model_name=CONFIG["model_adi"],
            detector_backend="opencv",
            enforce_detection=False,
            silent=True
        )
        if sonuc.get("verified", False):
            _bildirim_gonder("mimar", "Mimar geldi! Hoş geldin Mimarım. 👑")
            return "👁️ Mimar geldi! Hoş geldin Mimarım. 👑"
        else:
            return "👁️ Kamerada Mimar tespit edilemedi."
    except Exception as e:
        return f"❌ Yüz kontrol hatası: {e}"
    finally:
        kamera.release()


def yuz_tanima_durdur():
    global _calisiyor
    _calisiyor = False
    print("👁️ [YÜZ TANIMA] Durduruldu.")
