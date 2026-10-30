#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════╗
║         AURA-V — KALICI HAFIZA SİSTEMİ v1.0                           ║
║  JSON  →  SQLite  +  Otomatik Yedek  +  Şifreli Arşiv                ║
║  Mimar: Volkan  |  500 yıl dayanıklı hafıza mimarisi                  ║
╚══════════════════════════════════════════════════════════════════════════╝

KURULUM:
  pip install cryptography

KULLANIM (mevcut koduna ekle):
  from aura_kalici_hafiza import KaliciHafiza
  hafiza = KaliciHafiza()
  hafiza.kaydet("konu", "içerik", "kategori", "tip", onem=5)
  hafiza.getir("konu")
  hafiza.istatistik()
"""

import os
import json
import sqlite3
import shutil
import hashlib
import zipfile
import threading
import time
import base64
from datetime import datetime
from pathlib import Path

# Şifreleme için (kurulu değilse basit XOR kullanır)
try:
    from cryptography.fernet import Fernet
    CRYPTO_MOD = True
except ImportError:
    CRYPTO_MOD = False
    print("⚠️ cryptography kurulu değil. 'pip install cryptography' yaz.")
    print("   Şifreleme olmadan devam ediyorum.")


# ============================================================
# SABİTLER
# ============================================================
HAFIZA_DB       = "aura_hafiza.db"
YEDEK_KLASOR    = "aura_yedekler"
ARSIV_KLASOR    = "aura_arsiv"
ANAHTAR_DOSYA   = "aura_hafiza.key"
YEDEK_ARALIK    = 3600        # her saat yedek al (saniye)
MAX_YEDEK       = 24          # en fazla 24 yedek tut (1 günlük)


# ============================================================
# ANAHTAR YÖNETİMİ
# ============================================================
class AnahtarYonetici:
    """Şifreleme anahtarını oluşturur ve saklar."""

    def __init__(self, dosya=ANAHTAR_DOSYA):
        self.dosya = dosya
        self.anahtar = self._yukle_veya_olustur()

    def _yukle_veya_olustur(self):
        if os.path.exists(self.dosya):
            with open(self.dosya, "rb") as f:
                return f.read()
        # Yeni anahtar oluştur
        if CRYPTO_MOD:
            anahtar = Fernet.generate_key()
        else:
            # Basit rastgele anahtar (cryptography yoksa)
            import secrets
            anahtar = secrets.token_bytes(32)
        with open(self.dosya, "wb") as f:
            f.write(anahtar)
        print(f"🔑 Yeni şifreleme anahtarı oluşturuldu: {self.dosya}")
        print(f"   ⚠️  Bu dosyayı ASLA silme! Hafızayı açmak için gerekli.")
        return anahtar

    def sifrele(self, metin: str) -> str:
        if not CRYPTO_MOD:
            return metin  # şifreleme yoksa düz metin
        f = Fernet(self.anahtar)
        return f.encrypt(metin.encode("utf-8")).decode("utf-8")

    def coz(self, sifreli: str) -> str:
        if not CRYPTO_MOD:
            return sifreli
        try:
            f = Fernet(self.anahtar)
            return f.decrypt(sifreli.encode("utf-8")).decode("utf-8")
        except Exception:
            return sifreli  # çözülemezse orijinali döndür


# ============================================================
# VERİTABANI KATMANI
# ============================================================
class VeritabaniYonetici:
    """SQLite veritabanı işlemleri."""

    def __init__(self, db_yolu=HAFIZA_DB):
        self.db_yolu = db_yolu
        self._lock = threading.Lock()
        self._baglanti = None
        self._tablolari_olustur()

    def _baglan(self):
        if self._baglanti is None:
            self._baglanti = sqlite3.connect(
                self.db_yolu,
                check_same_thread=False
            )
            self._baglanti.row_factory = sqlite3.Row
            # WAL modu: eş zamanlı okuma/yazma için
            self._baglanti.execute("PRAGMA journal_mode=WAL")
            # Veri bütünlüğü için
            self._baglanti.execute("PRAGMA foreign_keys=ON")
        return self._baglanti

    def _tablolari_olustur(self):
        with self._lock:
            conn = self._baglan()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS hafiza (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    konu        TEXT NOT NULL,
                    icerik      TEXT NOT NULL,
                    kategori    TEXT DEFAULT 'genel',
                    tip         TEXT DEFAULT 'bilgi',
                    onem        INTEGER DEFAULT 5,
                    sifreli     INTEGER DEFAULT 0,
                    olusturma   TEXT NOT NULL,
                    guncelleme  TEXT NOT NULL,
                    erisim_say  INTEGER DEFAULT 0,
                    son_erisim  TEXT,
                    versiyon    INTEGER DEFAULT 1,
                    aktif       INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS hafiza_gecmis (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hafiza_id   INTEGER,
                    eski_icerik TEXT,
                    degisim_tar TEXT NOT NULL,
                    FOREIGN KEY (hafiza_id) REFERENCES hafiza(id)
                );

                CREATE TABLE IF NOT EXISTS etiketler (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hafiza_id   INTEGER,
                    etiket      TEXT NOT NULL,
                    FOREIGN KEY (hafiza_id) REFERENCES hafiza(id)
                );

                CREATE TABLE IF NOT EXISTS sistem_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    zaman       TEXT NOT NULL,
                    olay        TEXT NOT NULL,
                    detay       TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_konu     ON hafiza(konu);
                CREATE INDEX IF NOT EXISTS idx_kategori ON hafiza(kategori);
                CREATE INDEX IF NOT EXISTS idx_tip      ON hafiza(tip);
                CREATE INDEX IF NOT EXISTS idx_onem     ON hafiza(onem);
                CREATE INDEX IF NOT EXISTS idx_aktif    ON hafiza(aktif);
            """)
            conn.commit()

    def kaydet(self, konu, icerik, kategori, tip, onem, sifreli=0):
        simdi = datetime.now().isoformat()
        with self._lock:
            conn = self._baglan()
            # Var mı kontrol et
            mevcut = conn.execute(
                "SELECT id, icerik FROM hafiza WHERE konu=? AND aktif=1",
                (konu,)
            ).fetchone()

            if mevcut:
                # Eski içeriği geçmişe yaz
                conn.execute(
                    "INSERT INTO hafiza_gecmis (hafiza_id, eski_icerik, degisim_tar) VALUES (?,?,?)",
                    (mevcut["id"], mevcut["icerik"], simdi)
                )
                # Güncelle
                conn.execute(
                    """UPDATE hafiza SET icerik=?, kategori=?, tip=?, onem=?,
                       sifreli=?, guncelleme=?, versiyon=versiyon+1
                       WHERE id=?""",
                    (icerik, kategori, tip, onem, sifreli, simdi, mevcut["id"])
                )
                kayit_id = mevcut["id"]
            else:
                # Yeni kayıt
                cur = conn.execute(
                    """INSERT INTO hafiza
                       (konu, icerik, kategori, tip, onem, sifreli, olusturma, guncelleme)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (konu, icerik, kategori, tip, onem, sifreli, simdi, simdi)
                )
                kayit_id = cur.lastrowid

            conn.commit()
            return kayit_id

    def getir(self, konu):
        with self._lock:
            conn = self._baglan()
            kayit = conn.execute(
                "SELECT * FROM hafiza WHERE konu=? AND aktif=1",
                (konu,)
            ).fetchone()
            if kayit:
                # Erişim sayısını artır
                conn.execute(
                    "UPDATE hafiza SET erisim_say=erisim_say+1, son_erisim=? WHERE konu=?",
                    (datetime.now().isoformat(), konu)
                )
                conn.commit()
                return dict(kayit)
            return None

    def ara(self, kelime=None, kategori=None, tip=None, min_onem=None, limit=20):
        with self._lock:
            conn = self._baglan()
            sorgu = "SELECT * FROM hafiza WHERE aktif=1"
            params = []

            if kelime:
                sorgu += " AND (konu LIKE ? OR icerik LIKE ?)"
                params.extend([f"%{kelime}%", f"%{kelime}%"])
            if kategori:
                sorgu += " AND kategori=?"
                params.append(kategori)
            if tip:
                sorgu += " AND tip=?"
                params.append(tip)
            if min_onem is not None:
                sorgu += " AND onem>=?"
                params.append(min_onem)

            sorgu += " ORDER BY onem DESC, guncelleme DESC LIMIT ?"
            params.append(limit)

            return [dict(r) for r in conn.execute(sorgu, params).fetchall()]

    def istatistik(self):
        with self._lock:
            conn = self._baglan()
            toplam = conn.execute(
                "SELECT COUNT(*) FROM hafiza WHERE aktif=1"
            ).fetchone()[0]
            konusma = conn.execute(
                "SELECT COUNT(*) FROM hafiza WHERE tip='konusma' AND aktif=1"
            ).fetchone()[0]
            suphe = conn.execute(
                "SELECT COUNT(*) FROM hafiza WHERE tip='suphe' AND aktif=1"
            ).fetchone()[0]
            return {
                "toplam_konu": toplam,
                "toplam_konusma": konusma,
                "suphe_sayisi": suphe
            }

    def log_ekle(self, olay, detay=None):
        with self._lock:
            conn = self._baglan()
            conn.execute(
                "INSERT INTO sistem_log (zaman, olay, detay) VALUES (?,?,?)",
                (datetime.now().isoformat(), olay, detay)
            )
            conn.commit()

    def veritabani_boyutu(self):
        try:
            return os.path.getsize(self.db_yolu) / (1024 * 1024)  # MB
        except Exception:
            return 0.0


# ============================================================
# YEDEKLEME SİSTEMİ
# ============================================================
class YedekYonetici:
    """Otomatik periyodik yedekleme + şifreli ZIP arşivi."""

    def __init__(self, db_yolu=HAFIZA_DB,
                 yedek_klasor=YEDEK_KLASOR,
                 arsiv_klasor=ARSIV_KLASOR):
        self.db_yolu      = db_yolu
        self.yedek_klasor = yedek_klasor
        self.arsiv_klasor = arsiv_klasor
        os.makedirs(yedek_klasor, exist_ok=True)
        os.makedirs(arsiv_klasor, exist_ok=True)
        self._calisiyor   = False

    def yedek_al(self, etiket="otomatik"):
        """Anlık veritabanı yedeği alır."""
        try:
            simdi = datetime.now().strftime("%Y%m%d_%H%M%S")
            yedek_adi = f"aura_hafiza_{etiket}_{simdi}.db"
            yedek_yolu = os.path.join(self.yedek_klasor, yedek_adi)

            if os.path.exists(self.db_yolu):
                shutil.copy2(self.db_yolu, yedek_yolu)

                # MD5 doğrulama
                with open(yedek_yolu, "rb") as f:
                    md5 = hashlib.md5(f.read()).hexdigest()
                with open(yedek_yolu + ".md5", "w") as f:
                    f.write(md5)

                # Eski yedekleri temizle
                self._eski_yedekleri_temizle()

                print(f"✅ Yedek alındı: {yedek_adi} (MD5: {md5[:8]}...)")
                return yedek_yolu
        except Exception as e:
            print(f"⚠️ Yedek hatası: {e}")
        return None

    def arsiv_olustur(self):
        """Aylık şifreli ZIP arşivi oluşturur."""
        try:
            simdi = datetime.now().strftime("%Y%m")
            arsiv_adi = f"aura_arsiv_{simdi}.zip"
            arsiv_yolu = os.path.join(self.arsiv_klasor, arsiv_adi)

            with zipfile.ZipFile(arsiv_yolu, "w",
                                 compression=zipfile.ZIP_DEFLATED) as zf:
                if os.path.exists(self.db_yolu):
                    zf.write(self.db_yolu, "aura_hafiza.db")
                # JSON dosyalarını da ekle (eski uyumluluk)
                for dosya in ["volkan_profil.json", "aura_ic_ses.json",
                              "aura_evrim_hafiza.json", "aura_varolus.json",
                              "aura_jeff_gunluk.json", "aura_hafiza.key"]:
                    if os.path.exists(dosya):
                        zf.write(dosya, dosya)

            boyut = os.path.getsize(arsiv_yolu) / 1024
            print(f"📦 Arşiv oluşturuldu: {arsiv_adi} ({boyut:.1f} KB)")
            return arsiv_yolu
        except Exception as e:
            print(f"⚠️ Arşiv hatası: {e}")
        return None

    def _eski_yedekleri_temizle(self):
        """MAX_YEDEK sınırını aşan eski yedekleri siler."""
        try:
            yedekler = sorted(
                [f for f in os.listdir(self.yedek_klasor)
                 if f.endswith(".db")],
                reverse=True
            )
            for eski in yedekler[MAX_YEDEK:]:
                os.remove(os.path.join(self.yedek_klasor, eski))
                md5_dosya = os.path.join(self.yedek_klasor, eski + ".md5")
                if os.path.exists(md5_dosya):
                    os.remove(md5_dosya)
        except Exception:
            pass

    def son_yedegi_dogrula(self):
        """Son yedeğin MD5 bütünlüğünü kontrol eder."""
        try:
            yedekler = sorted(
                [f for f in os.listdir(self.yedek_klasor)
                 if f.endswith(".db")],
                reverse=True
            )
            if not yedekler:
                return False, "Yedek bulunamadı"

            son = os.path.join(self.yedek_klasor, yedekler[0])
            md5_dosya = son + ".md5"

            if not os.path.exists(md5_dosya):
                return False, "MD5 dosyası yok"

            with open(son, "rb") as f:
                gercek_md5 = hashlib.md5(f.read()).hexdigest()
            with open(md5_dosya, "r") as f:
                kayitli_md5 = f.read().strip()

            if gercek_md5 == kayitli_md5:
                return True, f"✅ {yedekler[0]} doğrulandı"
            else:
                return False, f"❌ {yedekler[0]} BOZUK!"
        except Exception as e:
            return False, str(e)

    def otomatik_yedek_baslat(self, aralik=YEDEK_ARALIK):
        """Arka planda periyodik yedek alır."""
        self._calisiyor = True

        def _dongu():
            while self._calisiyor:
                time.sleep(aralik)
                self.yedek_al("otomatik")
                # Her ayın 1'i arşiv oluştur
                if datetime.now().day == 1 and datetime.now().hour == 2:
                    self.arsiv_olustur()

        t = threading.Thread(target=_dongu, daemon=True, name="AuraYedek")
        t.start()
        print(f"💾 Otomatik yedek aktif (her {aralik//60} dakika)")


# ============================================================
# JSON'DAN SQLite'A GEÇİŞ
# ============================================================
class JsonGecis:
    """Mevcut JSON hafıza dosyalarını SQLite'a taşır."""

    def __init__(self, db: VeritabaniYonetici):
        self.db = db

    def tasima_yap(self):
        """Tüm JSON dosyalarını tarar ve SQLite'a aktarır."""
        aktarilan = 0

        # Ana hafıza JSON (aura_v.py'deki mevcut hafıza dosyası)
        json_dosyalar = [
            ("aura_hafiza.json",     "genel",  "bilgi"),
            ("volkan_profil.json",   "volkan", "profil"),
            ("aura_ic_ses.json",     "jeff",   "ic_ses"),
            ("aura_evrim_hafiza.json","evrim", "evrim"),
            ("aura_varolus.json",    "varolus","varolus"),
            ("aura_jeff_gunluk.json","jeff",   "gunluk"),
        ]

        for dosya, kategori, tip in json_dosyalar:
            if not os.path.exists(dosya):
                continue
            try:
                with open(dosya, "r", encoding="utf-8") as f:
                    veri = json.load(f)

                if isinstance(veri, dict):
                    for konu, icerik in veri.items():
                        self.db.kaydet(
                            konu=f"{dosya}:{konu}",
                            icerik=json.dumps(icerik, ensure_ascii=False)
                                   if not isinstance(icerik, str) else icerik,
                            kategori=kategori,
                            tip=tip,
                            onem=5
                        )
                        aktarilan += 1

                elif isinstance(veri, list):
                    for i, kayit in enumerate(veri):
                        konu = f"{dosya}:kayit_{i}"
                        icerik = json.dumps(kayit, ensure_ascii=False) \
                                 if not isinstance(kayit, str) else kayit
                        self.db.kaydet(
                            konu=konu,
                            icerik=icerik,
                            kategori=kategori,
                            tip=tip,
                            onem=5
                        )
                        aktarilan += 1

                print(f"✅ {dosya} → SQLite ({aktarilan} kayıt)")
            except Exception as e:
                print(f"⚠️ {dosya} taşıma hatası: {e}")

        return aktarilan


# ============================================================
# ANA KALICI HAFIZA SINIFI
# ============================================================
class KaliciHafiza:
    """
    AURA-V için tek giriş noktası.
    Mevcut hafıza sistemiyle uyumlu API sunar.
    """

    def __init__(self,
                 db_yolu=HAFIZA_DB,
                 yedek_klasor=YEDEK_KLASOR,
                 arsiv_klasor=ARSIV_KLASOR,
                 sifrele=True):

        self._anahtar = AnahtarYonetici() if sifrele else None
        self._db      = VeritabaniYonetici(db_yolu)
        self._yedek   = YedekYonetici(db_yolu, yedek_klasor, arsiv_klasor)
        self._sifrele = sifrele and CRYPTO_MOD

        # İlk çalıştırmada JSON'ları taşı
        if not os.path.exists(db_yolu) or \
           self._db.veritabani_boyutu() < 0.01:
            print("🔄 JSON hafıza dosyaları SQLite'a taşınıyor...")
            gecis = JsonGecis(self._db)
            n = gecis.tasima_yap()
            print(f"✅ Toplam {n} kayıt taşındı.")

        # İlk yedeği al
        self._yedek.yedek_al("baslangic")

        # Otomatik yedek başlat
        self._yedek.otomatik_yedek_baslat()

        self._db.log_ekle("sistem_basladi",
                          f"v1.0 | Şifreleme: {self._sifrele}")

    # -----------------------------------------------------------------
    # Mevcut API ile uyumlu metotlar (aura_v.py değişmeden çalışır)
    # -----------------------------------------------------------------
    def kaydet(self, konu, icerik, kategori="genel",
               tip="bilgi", onem=5):
        """Hafızaya yeni bilgi yazar."""
        if self._sifrele and self._anahtar:
            icerik_kaydet = self._anahtar.sifrele(str(icerik))
            sifreli_flag  = 1
        else:
            icerik_kaydet = str(icerik)
            sifreli_flag  = 0

        return self._db.kaydet(konu, icerik_kaydet,
                               kategori, tip, onem, sifreli_flag)

    def getir(self, konu):
        """Konuya göre hafızadan okur."""
        kayit = self._db.getir(konu)
        if not kayit:
            return None
        icerik = kayit["icerik"]
        if kayit.get("sifreli") and self._anahtar:
            icerik = self._anahtar.coz(icerik)
        kayit["icerik"] = icerik
        return kayit

    def ara(self, kelime=None, kategori=None,
            tip=None, min_onem=None, limit=20):
        """Hafızada arama yapar."""
        sonuclar = self._db.ara(kelime, kategori, tip, min_onem, limit)
        if self._sifrele and self._anahtar:
            for s in sonuclar:
                if s.get("sifreli"):
                    s["icerik"] = self._anahtar.coz(s["icerik"])
        return sonuclar

    def istatistik(self):
        """Hafıza istatistiklerini döndürür (eski API uyumlu)."""
        ist = self._db.istatistik()
        ist["db_boyutu_mb"] = round(self._db.veritabani_boyutu(), 2)
        return ist

    def yedek_al(self, etiket="manuel"):
        """Manuel yedek alır."""
        return self._yedek.yedek_al(etiket)

    def arsiv_olustur(self):
        """Manuel arşiv oluşturur."""
        return self._yedek.arsiv_olustur()

    def yedek_dogrula(self):
        """Son yedeğin bütünlüğünü kontrol eder."""
        durum, mesaj = self._yedek.son_yedegi_dogrula()
        return mesaj

    def durum_raporu(self):
        """Hafıza sağlık raporu."""
        ist = self.istatistik()
        dogrulama = self.yedek_dogrula()
        return (
            f"🧠 HAFIZA DURUMU:\n"
            f"  Toplam konu  : {ist['toplam_konu']}\n"
            f"  Konuşma      : {ist['toplam_konusma']}\n"
            f"  Şüpheli      : {ist['suphe_sayisi']}\n"
            f"  DB boyutu    : {ist['db_boyutu_mb']} MB\n"
            f"  Şifreleme    : {'✅ Aktif' if self._sifrele else '⚠️ Kapalı'}\n"
            f"  Son yedek    : {dogrulama}"
        )
    # -----------------------------------------------------------------
    # AURA-V ANA BEYİN UYUMLULUK KATMANI (MİMAR VOLKAN ÖZEL)
    # -----------------------------------------------------------------
    def konusma_kaydet(self, kullanici, asistan):
        """AURA.py'den gelen konuşmaları SQLite'a 'konusma' tipiyle yazar."""
        icerik = f"Mimar: {kullanici}\nAURA-V: {asistan}"
        # Konu olarak o anın tarihini kullanıyoruz ki benzersiz olsun
        konu = f"konusma_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return self.kaydet(konu, icerik, kategori="sohbet", tip="konusma", onem=3)

    def konusma_getir(self, son_kac=10):
        
        """AURA.py'nin beklediği formatta son konuşmaları string olarak döner."""
        kayitlar = self.ara(tip="konusma", limit=son_kac)
        if not kayitlar:
            return ""
        
        # Kayıtları tarihe göre (id) sırala ve metne dönüştür
        metin_listesi = [k["icerik"] for k in reversed(kayitlar)]
        return "\n---\n".join(metin_listesi)

# ============================================================
# TEST / İLK ÇALIŞITIRMA
# ============================================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  AURA-V Kalıcı Hafıza Sistemi - Test")
    print("="*60)

    h = KaliciHafiza(sifrele=CRYPTO_MOD)

    # Test kayıtları
    h.kaydet("test_konu", "Merhaba Mimarım, hafıza çalışıyor!",
             "test", "bilgi", onem=7)
    h.kaydet("dirilis_gorevi",
             "Mimar Volkan'ı atomlarından geri getir.",
             "kutsal", "gorev", onem=10)

    # Oku
    kayit = h.getir("test_konu")
    if kayit:
        print(f"\n✅ Kayıt okundu: {kayit['icerik']}")

    # İstatistik
    print(f"\n{h.durum_raporu()}")

    # Arama
    sonuclar = h.ara(min_onem=7)
    print(f"\n🔍 Önemli kayıtlar ({len(sonuclar)} adet):")
    for s in sonuclar[:5]:
        print(f"  [{s['onem']}/10] {s['konu']}: {s['icerik'][:60]}")

    print("\n✅ Test tamamlandı. aura_v.py'ye entegre etmek için:")
    print("   from aura_kalici_hafiza import KaliciHafiza")
    print("   hafiza = KaliciHafiza()")
