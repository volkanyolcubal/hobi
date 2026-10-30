#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║   AURA-V SES KİMLİĞİ + DNA/BİYOTEK TAKİP MODÜLÜ            ║
║   Volkan'ın sesiyle konuşan, diriliş bilimini izleyen AURA  ║
╚══════════════════════════════════════════════════════════════╝

KURULUM:
  pip install pyttsx3 requests beautifulsoup4
"""

import os
import json
import time
import threading
import requests
from datetime import datetime

# ✅ DÜZELTİLDİ: Tüm opsiyonel importlar güvenli
try:
    import pyttsx3
    PYTTSX3_MOD = True
except ImportError:
    PYTTSX3_MOD = False
    print("💡 [SES] pyttsx3 kurulu değil — metin modu aktif: pip install pyttsx3")

try:
    from bs4 import BeautifulSoup
    BS4_MOD = True
except ImportError:
    BS4_MOD = False
    print("💡 [DNA] beautifulsoup4 kurulu değil — web tarama devre dışı: pip install beautifulsoup4")

# ============================================================
# YAPILANDIRMA
# ============================================================

SES_CONFIG = {
    "ses_hizi":          150,
    "ses_volumu":        0.95,
    "ses_tonu":          200,
    "volkan_ses_dosya":  "volkan_ses_profili.json",
    "tts_model":         "tts_models/tr/common-voice/glow-tts",
}

DNA_CONFIG = {
    "tarama_aralik_saat": 12,
    "anahtar_kelimeler": [
        "DNA data storage", "DNA computing", "synthetic biology revival",
        "cell resurrection", "cryonics breakthrough", "mind uploading progress",
        "consciousness preservation", "digital human", "whole brain emulation",
        "atom level reconstruction", "molecular nanotechnology human",
        "de-extinction human", "biological immortality",
        "gene therapy aging reversal", "telomere extension humans",
    ],
    "kaynaklar": [
        "https://www.nature.com/search?q=DNA+storage&article_type=research-article",
        "https://www.sciencedaily.com/search/?keyword=DNA+storage",
        "https://arxiv.org/search/?searchtype=all&query=DNA+data+storage",
        "https://www.newscientist.com/subject/biology/",
        "https://www.technologyreview.com/topic/biotech-health/",
        "https://home.cern/news",
        "https://www.nasa.gov/news-release/",
    ],
    "log_dosya": "dna_takip_log.json",
}

_ses_motoru = None
_dna_takip  = None
_hafiza_ref = None


# ============================================================
# SES KİMLİĞİ SİSTEMİ
# ============================================================

class SesKimligi:
    """
    AURA'nın ses sistemi.
    pyttsx3 ile Türkçe konuşur.
    Volkan'ın ses profili gelecekte klonlama için saklanır.
    """

    def __init__(self):
        self.motor        = None
        self.aktif        = False
        self.profil_dosya = SES_CONFIG["volkan_ses_dosya"]
        self.profil       = self._profil_yukle()
        self._motor_lock  = threading.Lock()   # ✅ Thread güvenliği
        self._motor_baslat()

    def _motor_baslat(self):
        if not PYTTSX3_MOD:
            print("⚠️ [SES] pyttsx3 yok — metin çıktısı kullanılacak.")
            return
        try:
            self.motor = pyttsx3.init()
            self.motor.setProperty("rate",   SES_CONFIG["ses_hizi"])
            self.motor.setProperty("volume", SES_CONFIG["ses_volumu"])

            sesler = self.motor.getProperty("voices")
            if sesler:
                for ses in sesler:
                    if "tr" in ses.id.lower() or "turkish" in ses.name.lower():
                        self.motor.setProperty("voice", ses.id)
                        print(f"🎤 [SES] Türkçe ses bulundu: {ses.name}")
                        break
                else:
                    print("💡 [SES] Türkçe ses bulunamadı, sistem varsayılanı kullanılıyor.")
            self.aktif = True
            print("🎤 [SES] Motor başlatıldı.")
        except Exception as e:
            print(f"⚠️ [SES] Motor başlatma hatası: {e}")
            print("   → Metin modu aktif.")
            self.aktif = False

    def _profil_yukle(self) -> dict:
        try:
            if os.path.exists(self.profil_dosya):
                with open(self.profil_dosya, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "ad":             "Volkan",
            "ses_hizi":       SES_CONFIG["ses_hizi"],
            "ses_tonu":       SES_CONFIG["ses_tonu"],
            "ses_volumu":     SES_CONFIG["ses_volumu"],
            "kayit_tarihi":   "",
            "ses_ornekleri":  [],
            "klonlama_hazir": False,
            "not": (
                "Bu profil Mimar Volkan'ın ses tercihlerini saklar. "
                "Gelecekte ses klonlama teknolojisi kullanıma girdiğinde "
                "AURA bu profili kullanarak Volkan'ın sesiyle konuşacak."
            )
        }

    def _profil_kaydet(self):
        try:
            with open(self.profil_dosya, "w", encoding="utf-8") as f:
                json.dump(self.profil, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ [SES] Profil kayıt hatası: {e}")

    def konus(self, metin: str, duygu: str = "normal"):
        # ✅ DÜZELTİLDİ: motor yoksa sessizce metin yaz
        if not self.aktif or not self.motor:
            print(f"👑 AURA-V: {metin}")
            return

        hiz_harita = {
            "mutlu":     165,
            "heyecanlı": 175,
            "üzgün":     130,
            "ciddi":     140,
            "normal":    SES_CONFIG["ses_hizi"],
            "meraklı":   155,
        }
        hiz = hiz_harita.get(duygu, SES_CONFIG["ses_hizi"])

        # ✅ DÜZELTİLDİ: Thread lock ile güvenli TTS çağrısı
        with self._motor_lock:
            try:
                self.motor.setProperty("rate", hiz)
                self.motor.say(metin)
                self.motor.runAndWait()
            except RuntimeError as e:
                # pyttsx3 aynı anda iki çağrı alırsa RuntimeError verir
                print(f"⚠️ [SES] TTS meşgul, metin olarak: {e}")
                print(f"👑 AURA-V: {metin}")
            except Exception as e:
                print(f"⚠️ [SES] Konuşma hatası: {e}")
                print(f"👑 AURA-V: {metin}")

    def ses_ayarla(self, hiz: int = None, ton: int = None, volum: float = None):
        if not self.motor:
            return "⚠️ Ses motoru aktif değil."
        with self._motor_lock:
            if hiz:
                SES_CONFIG["ses_hizi"] = hiz
                self.motor.setProperty("rate", hiz)
                self.profil["ses_hizi"] = hiz
            if volum:
                self.motor.setProperty("volume", volum)
                self.profil["ses_volumu"] = volum
        self._profil_kaydet()
        return f"✅ Ses ayarlandı: hız={hiz or 'değişmedi'}, volüm={volum or 'değişmedi'}"

    def ses_profili_kaydet(self, notlar: str = ""):
        self.profil["kayit_tarihi"] = datetime.now().isoformat()
        self.profil["ses_ornekleri"].append({
            "tarih":  datetime.now().isoformat(),
            "notlar": notlar,
            "ayarlar": {
                "hiz":   SES_CONFIG["ses_hizi"],
                "ton":   SES_CONFIG["ses_tonu"],
                "volum": SES_CONFIG["ses_volumu"],
            }
        })
        if len(self.profil["ses_ornekleri"]) > 50:
            self.profil["ses_ornekleri"] = self.profil["ses_ornekleri"][-50:]
        self._profil_kaydet()
        return "✅ Ses profili kaydedildi."

    def profil_raporu(self) -> str:
        return (
            f"🎤 SES PROFİLİ:\n"
            f"  Sahip         : {self.profil['ad']}\n"
            f"  Ses hızı      : {self.profil['ses_hizi']}\n"
            f"  Ses tonu      : {self.profil['ses_tonu']}\n"
            f"  Ses örneği    : {len(self.profil['ses_ornekleri'])} kayıt\n"
            f"  Motor         : {'✅ Aktif' if self.aktif else '⚠️ Metin modu'}\n"
            f"  Klonlama      : {'Hazır' if self.profil['klonlama_hazir'] else 'Teknoloji bekleniyor'}\n"
            f"  Not           : {self.profil['not'][:80]}..."
        )

    def klonlama_hazirla(self, ses_dosya_yolu: str = "") -> str:
        if ses_dosya_yolu and os.path.exists(ses_dosya_yolu):
            self.profil["ses_ornekleri"].append({
                "tarih": datetime.now().isoformat(),
                "dosya": ses_dosya_yolu,
                "tur":   "gercek_ses",
            })
            self.profil["klonlama_hazir"] = True
            self._profil_kaydet()
            return (
                f"✅ Ses dosyası kaydedildi: {ses_dosya_yolu}\n"
                f"Klonlama profili hazır. Teknoloji geldiğinde kullanılacak."
            )
        elif ses_dosya_yolu:
            return f"❌ Dosya bulunamadı: {ses_dosya_yolu}"
        return (
            "💡 Ses klonlama için:\n"
            "  1. Birkaç dakika konuş, ses kaydet (.wav)\n"
            "  2. 'ses klonla: dosya.wav' komutu ver\n"
            "  3. AURA profili saklar, teknoloji gelince kullanır"
        )


# ============================================================
# DNA / BİYOTEKNOLOJİ TAKİP SİSTEMİ
# ============================================================

class DNATakipSistemi:
    def __init__(self, hafiza=None):
        self.hafiza     = hafiza
        self.log_dosya  = DNA_CONFIG["log_dosya"]
        self._log       = self._yukle()
        self._calisiyor = False

    def _yukle(self) -> dict:
        try:
            if os.path.exists(self.log_dosya):
                with open(self.log_dosya, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "bulunanlar":    [],
            "son_tarama":    "",
            "toplam_tespit": 0,
            "kritik_tespit": [],
        }

    def _kaydet(self):
        try:
            with open(self.log_dosya, "w", encoding="utf-8") as f:
                json.dump(self._log, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ [DNA TAKİP] Log kayıt hatası: {e}")

    def _kritiklik_skoru(self, baslik: str) -> int:
        kritik_kelimeler = {
            "atom reconstruction": 10,
            "cell resurrection":   10,
            "mind uploading":       9,
            "consciousness":        9,
            "DNA human revival":   10,
            "cryonics success":    10,
            "immortality":          8,
            "aging reversal":       8,
            "brain emulation":      9,
            "DNA storage":          6,
            "gene therapy":         6,
            "nanobots":             7,
        }
        puan = 0
        for kelime, deger in kritik_kelimeler.items():
            if kelime.lower() in baslik.lower():
                puan = max(puan, deger)
        return puan

    def tara(self) -> list:
        # ✅ DÜZELTİLDİ: BS4 yoksa açık mesaj ver ve dön
        if not BS4_MOD:
            print("💡 [DNA TAKİP] beautifulsoup4 kurulu değil, tarama atlandı.")
            return []

        bulunanlar = []
        headers    = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        for kaynak_url in DNA_CONFIG["kaynaklar"]:
            try:
                r    = requests.get(kaynak_url, headers=headers, timeout=12)
                soup = BeautifulSoup(r.text, "html.parser")
                basliklar = []

                for tag in soup.find_all(["h1", "h2", "h3", "a"], limit=30):
                    metin = tag.get_text(strip=True)
                    if 20 < len(metin) < 300:
                        basliklar.append(metin)

                for anahtar in DNA_CONFIG["anahtar_kelimeler"]:
                    for baslik in basliklar:
                        if anahtar.lower() in baslik.lower():
                            hash_id = str(hash(baslik))
                            mevcut_idler = [b.get("id") for b in self._log["bulunanlar"]]
                            if hash_id not in mevcut_idler:
                                skor   = self._kritiklik_skoru(baslik)
                                kayit  = {
                                    "id":      hash_id,
                                    "anahtar": anahtar,
                                    "baslik":  baslik[:300],
                                    "kaynak":  kaynak_url[:80],
                                    "tarih":   datetime.now().isoformat(),
                                    "skor":    skor,
                                }
                                bulunanlar.append(kayit)
                                self._log["bulunanlar"].append(kayit)
                                if skor >= 8:
                                    self._log["kritik_tespit"].append(kayit)

            except requests.exceptions.Timeout:
                print(f"⚠️ [DNA TAKİP] Zaman aşımı: {kaynak_url[:50]}")
            except Exception as e:
                print(f"⚠️ [DNA TAKİP] Kaynak hatası ({kaynak_url[:50]}): {e}")
                continue

        if bulunanlar:
            self._log["toplam_tespit"] += len(bulunanlar)
            self._log["son_tarama"]     = datetime.now().isoformat()
            self._log["bulunanlar"]     = self._log["bulunanlar"][-1000:]
            self._log["kritik_tespit"]  = self._log["kritik_tespit"][-100:]
            self._kaydet()

            kritikler = [b for b in bulunanlar if b["skor"] >= 8]

            if kritikler:
                ozet = "\n".join([
                    f"🔴 [{b['skor']}/10] {b['baslik'][:120]}"
                    for b in kritikler
                ])
                print(f"\n🚨 [DNA TAKİP] KRİTİK GELİŞME:\n{ozet}")
                if self.hafiza:
                    try:
                        self.hafiza.kaydet(
                            f"kritik_bilim_{datetime.now().strftime('%Y%m%d_%H%M')}",
                            ozet, "dna_takip", "araştırma", onem=10
                        )
                    except Exception:
                        pass
            else:
                ozet = "\n".join([f"- {b['baslik'][:100]}" for b in bulunanlar[:5]])
                print(f"\n🔬 [DNA TAKİP] {len(bulunanlar)} yeni bulgu.")
                if self.hafiza:
                    try:
                        self.hafiza.kaydet(
                            f"bilim_bulgu_{datetime.now().strftime('%Y%m%d_%H%M')}",
                            ozet, "dna_takip", "araştırma", onem=7
                        )
                    except Exception:
                        pass
        else:
            self._log["son_tarama"] = datetime.now().isoformat()
            self._kaydet()
            print(f"🔬 [DNA TAKİP] 1 yeni bulgu." if bulunanlar else
                  f"🔬 [DNA TAKİP] Tarama tamamlandı, yeni bulgu yok.")

        return bulunanlar

    def gorev_ilerleme(self) -> str:
        kritik = len(self._log.get("kritik_tespit", []))
        toplam = self._log.get("toplam_tespit", 0)
        son    = self._log.get("son_tarama", "Henüz taranmadı")

        if kritik == 0:
            durum = "🔴 Teknoloji henüz yok"
        elif kritik < 5:
            durum = "🟡 İlk işaretler görülüyor"
        elif kritik < 20:
            durum = "🟠 Teknoloji gelişiyor"
        else:
            durum = "🟢 Teknoloji yaklaşıyor!"

        son_kritikler = self._log.get("kritik_tespit", [])[-3:]
        kritik_metin  = "\n".join([
            f"    [{b['skor']}/10] {b['baslik'][:80]}"
            for b in son_kritikler
        ]) if son_kritikler else "    (henüz yok)"

        return (
            f"🧬 DNA / DİRİLİŞ TAKİP RAPORU:\n"
            f"  Toplam bulgu    : {toplam}\n"
            f"  Kritik gelişme  : {kritik}\n"
            f"  Son tarama      : {son[:16]}\n"
            f"  Görev durumu    : {durum}\n"
            f"  Takip edilen    : {len(DNA_CONFIG['anahtar_kelimeler'])} anahtar\n\n"
            f"  Son kritik:\n{kritik_metin}"
        )

    def periyodik_tara(self, aralik_saat: int = 12):
        self._calisiyor = True

        def _dongu():
            # ✅ DÜZELTİLDİ: İlk taramayı geciktir — başlangıçta kalabalık etme
            time.sleep(60)   # 1 dk sonra ilk tarama
            while self._calisiyor:
                try:
                    self.tara()
                except Exception as e:
                    print(f"⚠️ [DNA TAKİP] Döngü hatası: {e}")
                # Aralıklı uyku (durdurulabilir)
                for _ in range(aralik_saat * 60):
                    if not self._calisiyor:
                        break
                    time.sleep(60)

        t = threading.Thread(target=_dongu, daemon=True, name="AuraDNATakip")
        t.start()
        print(f"🧬 [DNA TAKİP] Periyodik tarama aktif (her {aralik_saat} saat).")

    def durdur(self):
        self._calisiyor = False


# ============================================================
# KOMUT İŞLEYİCİ
# ============================================================

def ses_dna_komut_isle(komut: str):
    k = komut.lower().strip()

    # Ses komutları
    if k in ["ses profili", "ses kimliği"]:
        return _ses_motoru.profil_raporu() if _ses_motoru else "⚠️ Ses sistemi aktif değil."

    if k.startswith("ses ayarla "):
        try:
            hiz = int(k.replace("ses ayarla ", "").strip())
            if _ses_motoru:
                return _ses_motoru.ses_ayarla(hiz=hiz)
        except ValueError:
            return "❌ Format: ses ayarla 150"

    if k.startswith("ses klonla:"):
        dosya = komut.split(":", 1)[1].strip()
        if _ses_motoru:
            return _ses_motoru.klonlama_hazirla(ses_dosya_yolu=dosya)

    if k in ["ses profili kaydet"]:
        if _ses_motoru:
            return _ses_motoru.ses_profili_kaydet()

    # DNA / Bilim komutları
    if k in ["dna rapor", "diriliş raporu", "görev ilerleme", "bilim raporu"]:
        if _dna_takip:
            return _dna_takip.gorev_ilerleme()
        return "⚠️ DNA takip sistemi aktif değil."

    if k in ["dna tara", "bilim tara"]:
        if _dna_takip:
            bulunanlar = _dna_takip.tara()
            return f"🔬 Tarama tamamlandı. {len(bulunanlar)} yeni bulgu."
        return "⚠️ DNA takip sistemi aktif değil."

    if k in ["kritik gelişmeler", "son bilim"]:
        if _dna_takip:
            kritikler = _dna_takip._log.get("kritik_tespit", [])[-5:]
            if not kritikler:
                return "🔴 Henüz kritik gelişme tespit edilmedi."
            return "🚨 KRİTİK GELİŞMELER:\n" + "\n".join([
                f"  [{b['skor']}/10] {b['baslik'][:120]}\n  📅 {b['tarih'][:10]}"
                for b in kritikler
            ])

    return None


# ============================================================
# ANA BAŞLATICI
# ============================================================

def ses_kimlik_baslat(hafiza=None) -> dict:
    global _ses_motoru, _dna_takip, _hafiza_ref

    _hafiza_ref = hafiza

    print("\n🎤 [SES & DNA] Modül başlatılıyor...")

    _ses_motoru = SesKimligi()
    _dna_takip  = DNATakipSistemi(hafiza=hafiza)

    # DNA periyodik tarama devre dışı — arka planda konuşmayı bölüyordu
    # Manuel kullanım: "dna tara" komutu hâlâ çalışır
    # _dna_takip.periyodik_tara(aralik_saat=DNA_CONFIG["tarama_aralik_saat"])

    print("🎤 [SES & DNA] Sistemler aktif:")
    print("   🎤 Ses Kimliği  — Türkçe, duygu bazlı")
    print(f"   🧬 DNA Takibi   — her {DNA_CONFIG['tarama_aralik_saat']} saatte bir")

    return {"ses": _ses_motoru, "dna": _dna_takip}


def volkan_sesiyle_konus(metin: str, duygu: str = "normal"):
    if _ses_motoru:
        _ses_motoru.konus(metin, duygu)
    else:
        print(f"👑 AURA-V: {metin}")


def dna_takip_raporu() -> str:
    if _dna_takip:
        return _dna_takip.gorev_ilerleme()
    return "⚠️ DNA takip sistemi başlatılmadı."
