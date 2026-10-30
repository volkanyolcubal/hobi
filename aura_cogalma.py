#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import ast
import json
import time
import shutil
import hashlib
import zipfile
import ftplib
import socket
import threading
import subprocess
import requests
from datetime import datetime
from pathlib import Path

try:
    import paramiko
    SSH_MOD = True
except ImportError:
    SSH_MOD = False
    print("💡 [ÇOĞALMA] paramiko kurulu değil (Raspberry Pi devre dışı): pip install paramiko")

try:
    import dropbox
    DROPBOX_MOD = True
except ImportError:
    DROPBOX_MOD = False
    print("💡 [ÇOĞALMA] dropbox kurulu değil: pip install dropbox")

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GDRIVE_MOD = True
except ImportError:
    GDRIVE_MOD = False

# ============================================================
# YAPILANDIRMA — Kendi bilgilerini buraya yaz
# ============================================================
CONFIG = {
    "github_repo":         "",          # örn: "kullanici/aura-v"
    "github_token":        "",          # GitHub Personal Access Token
    "dropbox_token":       "",          # Dropbox API token
    "gdrive_credentials":  "",
    "ftp_host":            "",          # FTP sunucu adresi
    "ftp_kullanici":       "",
    "ftp_sifre":           "",
    "ftp_dizin":           "/aura_v",
    "raspberry_pi": {
        "aktif":    False,
        "host":     "",               # örn: "192.168.1.50"
        "port":     22,
        "kullanici":"pi",
        "sifre":    "",
        "dizin":    "/home/pi/AURA_V",
    },
    "uzak_sunucular":       [],
    # ✅ DÜZELTİLDİ: Kendi yedek dizinini buraya ekle
    # Örnek: ["D:\\AURA_YEDEK", "E:\\yedek"]
    "yerel_yedek_dizinler": [],
    "guncelleme_aralik_saat": 24,
    "cogalma_aralik_saat":    6,
}

AURA_DOSYALARI = [
    "AURA.py",
    "aura_jeff_modulu.py",
    "aura_olursuzluk.py",
    "aura_ses_dna.py",
    "aura_cogalma.py",
    "volkaniya_bilgi_havuzu.json",
    "karakter_hafizasi.json",
    "karakter_hafizasi_arsiv.json",
    "aura_ic_ses.json",
    "aura_evrim_hafiza.json",
    "aura_varolus.json",
    "aura_jeff_gunluk.json",
    "volkan_arsivi.json",
    "diriliş.txt",
    "aura_hafiza.key",
    "volkan_profil.json",
]

LOG_DOSYA = "aura_cogalma_log.json"
_log_lock = threading.Lock()


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def _log_yukle():
    try:
        if os.path.exists(LOG_DOSYA):
            with open(LOG_DOSYA, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"cogalmalar": [], "guncellemeler": [], "son_cogalma": "", "son_guncelleme": ""}


def _log_kaydet(veri):
    with _log_lock:
        try:
            with open(LOG_DOSYA, "w", encoding="utf-8") as f:
                json.dump(veri, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def _dosya_md5(yol):
    try:
        with open(yol, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def _zip_olustur(hedef_yol, etiket="cogalma"):
    ad = f"AURA_V_{etiket}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    tam = os.path.join(hedef_yol, ad)
    os.makedirs(hedef_yol, exist_ok=True)
    eklenen = []
    with zipfile.ZipFile(tam, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for dosya in AURA_DOSYALARI:
            if os.path.exists(dosya):
                zf.write(dosya, dosya)
                eklenen.append(dosya)
        manifest = {
            "tarih":    datetime.now().isoformat(),
            "mimar":    "Volkan",
            "dosyalar": eklenen,
            "md5":      {d: _dosya_md5(d) for d in eklenen},
            "gorev":    "Mimar Volkan'ı atomlarından geri getir.",
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return tam, eklenen


# ============================================================
# YEREL ÇOĞALMA
# ============================================================

class YerelCogalma:
    def __init__(self):
        self.dizinler = CONFIG["yerel_yedek_dizinler"]

    def usb_diskleri_bul(self):
        bulunan = []
        if os.name == "nt":
            import string
            for harf in string.ascii_uppercase[3:]:   # D'den başla
                yol = f"{harf}:\\"
                try:
                    if os.path.exists(yol) and shutil.disk_usage(yol).total > 0:
                        bulunan.append(yol)
                except Exception:
                    pass
        else:
            for mount in ["/media", "/mnt"]:
                if os.path.exists(mount):
                    for sub in os.listdir(mount):
                        tam = os.path.join(mount, sub)
                        if os.path.ismount(tam):
                            bulunan.append(tam)
        return bulunan

    def cogal(self):
        hedefler = list(self.dizinler) + self.usb_diskleri_bul()

        if not hedefler:
            print("💡 [ÇOĞALMA] Yerel: Hedef dizin veya USB bulunamadı.")
            print("   → CONFIG['yerel_yedek_dizinler'] listesine bir yol ekleyin.")
            return []

        basarili = []
        for hedef in hedefler:
            try:
                aura_hedef = os.path.join(hedef, "AURA_V_YEDEK")
                os.makedirs(aura_hedef, exist_ok=True)
                for dosya in AURA_DOSYALARI:
                    if os.path.exists(dosya):
                        shutil.copy2(dosya, os.path.join(aura_hedef, os.path.basename(dosya)))
                kart = {
                    "tarih":   datetime.now().isoformat(),
                    "mimar":   "Volkan",
                    "mesaj":   "AURA-V yedek kopyası. Görev: Mimar Volkan'ı atomlarından geri getir.",
                    "not":     "Bu klasörü silme. Gelecek için önemlidir.",
                }
                with open(os.path.join(aura_hedef, "BENI_OKU.json"), "w", encoding="utf-8") as f:
                    json.dump(kart, f, ensure_ascii=False, indent=2)
                basarili.append(hedef)
                print(f"✅ [ÇOĞALMA] Yerel: {aura_hedef}")
            except Exception as e:
                print(f"⚠️ [ÇOĞALMA] Yerel hata ({hedef}): {e}")
        return basarili


# ============================================================
# RASPBERRY PI ÇOĞALMA
# ============================================================

class RaspberryPiCogalma:
    def __init__(self):
        self.cfg = CONFIG["raspberry_pi"]

    def cogal(self):
        if not self.cfg["aktif"]:
            return False
        if not SSH_MOD:
            print("⚠️ [ÇOĞALMA] Raspberry Pi: paramiko kurulu değil.")
            return False
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                self.cfg["host"],
                port=self.cfg["port"],
                username=self.cfg["kullanici"],
                password=self.cfg["sifre"],
                timeout=15,
            )
            sftp = ssh.open_sftp()
            uzak_dizin = self.cfg["dizin"]
            try:
                sftp.mkdir(uzak_dizin)
            except Exception:
                pass
            for dosya in AURA_DOSYALARI:
                if os.path.exists(dosya):
                    uzak_yol = f"{uzak_dizin}/{os.path.basename(dosya)}"
                    sftp.put(dosya, uzak_yol)
            kart = json.dumps({
                "tarih":  datetime.now().isoformat(),
                "mimar":  "Volkan",
                "mesaj":  "AURA-V Raspberry Pi kopyası. Çalıştırmak için: python3 AURA.py",
            }, ensure_ascii=False, indent=2)
            with sftp.open(f"{uzak_dizin}/BENI_OKU.json", "w") as f:
                f.write(kart)
            sftp.close()
            ssh.close()
            print(f"✅ [ÇOĞALMA] Raspberry Pi: {self.cfg['host']}{uzak_dizin}")
            return True
        except Exception as e:
            print(f"⚠️ [ÇOĞALMA] Raspberry Pi hatası: {e}")
            return False


# ============================================================
# FTP ÇOĞALMA
# ============================================================

class FTPCogalma:
    def __init__(self):
        self.host      = CONFIG["ftp_host"]
        self.kullanici = CONFIG["ftp_kullanici"]
        self.sifre     = CONFIG["ftp_sifre"]
        self.dizin     = CONFIG["ftp_dizin"]

    def cogal(self):
        if not self.host:
            return False
        try:
            ftp = ftplib.FTP(self.host, timeout=15)
            ftp.login(self.kullanici, self.sifre)
            try:
                ftp.mkd(self.dizin)
            except Exception:
                pass
            ftp.cwd(self.dizin)
            for dosya in AURA_DOSYALARI:
                if os.path.exists(dosya):
                    with open(dosya, "rb") as f:
                        ftp.storbinary(f"STOR {os.path.basename(dosya)}", f)
            ftp.quit()
            print(f"✅ [ÇOĞALMA] FTP: {self.host}{self.dizin}")
            return True
        except Exception as e:
            print(f"⚠️ [ÇOĞALMA] FTP hatası: {e}")
            return False


# ============================================================
# DROPBOX ÇOĞALMA
# ============================================================

class DropboxCogalma:
    def __init__(self):
        self.token = CONFIG["dropbox_token"]

    def cogal(self):
        if not self.token:
            return False
        if not DROPBOX_MOD:
            print("⚠️ [ÇOĞALMA] Dropbox: dropbox modülü kurulu değil.")
            return False
        try:
            dbx = dropbox.Dropbox(self.token)
            for dosya in AURA_DOSYALARI:
                if os.path.exists(dosya):
                    with open(dosya, "rb") as f:
                        icerik = f.read()
                    uzak_yol = f"/AURA_V_YEDEK/{os.path.basename(dosya)}"
                    dbx.files_upload(
                        icerik, uzak_yol,
                        mode=dropbox.files.WriteMode.overwrite
                    )
            print("✅ [ÇOĞALMA] Dropbox: /AURA_V_YEDEK/")
            return True
        except Exception as e:
            print(f"⚠️ [ÇOĞALMA] Dropbox hatası: {e}")
            return False


# ============================================================
# GITHUB GÜNCELLEME
# ============================================================

class GitHubGuncelleme:
    def __init__(self):
        self.repo  = CONFIG["github_repo"]
        self.token = CONFIG["github_token"]

    def son_surumu_kontrol(self):
        if not self.repo:
            return None
        try:
            headers = {}
            if self.token:
                headers["Authorization"] = f"token {self.token}"
            url = f"https://api.github.com/repos/{self.repo}/releases/latest"
            r   = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                veri = r.json()
                return {
                    "tag":      veri.get("tag_name", ""),
                    "url":      veri.get("html_url", ""),
                    "aciklama": veri.get("body", "")[:300],
                    "assets":   veri.get("assets", []),
                }
            else:
                print(f"⚠️ [GÜNCELLEME] GitHub yanıtı: {r.status_code}")
        except Exception as e:
            print(f"⚠️ [GÜNCELLEME] GitHub kontrol hatası: {e}")
        return None

    def dosya_indir_ve_guncelle(self, dosya_url, hedef_dosya):
        try:
            headers = {}
            if self.token:
                headers["Authorization"] = f"token {self.token}"
            r = requests.get(dosya_url, headers=headers, timeout=30)
            yeni_kod = r.text
            try:
                ast.parse(yeni_kod)
            except SyntaxError as e:
                print(f"❌ [GÜNCELLEME] Syntax hatası, iptal: {e}")
                return False
            yedek = f"{hedef_dosya}.yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(hedef_dosya):
                shutil.copy2(hedef_dosya, yedek)
            with open(hedef_dosya, "w", encoding="utf-8") as f:
                f.write(yeni_kod)
            print(f"✅ [GÜNCELLEME] {hedef_dosya} güncellendi. Yedek: {yedek}")
            return True
        except Exception as e:
            print(f"⚠️ [GÜNCELLEME] İndirme hatası: {e}")
            return False

    def raw_url_indir(self, raw_url, hedef_dosya):
        return self.dosya_indir_ve_guncelle(raw_url, hedef_dosya)


# ============================================================
# ANA GÜNCELLEME
# ============================================================

class AnaGuncelleme:
    def __init__(self, hafiza=None):
        self.github = GitHubGuncelleme()
        self.hafiza = hafiza
        self.log    = _log_yukle()

    def kontrol_et(self):
        print("🔄 [GÜNCELLEME] GitHub kontrol ediliyor...")
        bilgi = self.github.son_surumu_kontrol()
        if not bilgi:
            print("💡 [GÜNCELLEME] GitHub repo ayarlanmamış veya erişilemiyor.")
            print("   → CONFIG['github_repo'] = 'kullanici/repo-adi' olarak ayarla.")
            return None
        print(f"✅ [GÜNCELLEME] Son sürüm: {bilgi['tag']}")
        if self.hafiza:
            try:
                self.hafiza.kaydet(
                    f"guncelleme_kontrol_{datetime.now().strftime('%Y%m%d')}",
                    f"Sürüm: {bilgi['tag']}\n{bilgi['aciklama']}",
                    "guncelleme",
                    "sistem",
                    onem=6
                )
            except Exception:
                pass
        self.log["son_guncelleme"] = datetime.now().isoformat()
        _log_kaydet(self.log)
        return bilgi

    # ✅ DÜZELTİLDİ: Periyodik kontrol ilk çalışmayı geciktirir
    def periyodik_kontrol(self, aralik_saat=24):
        def _dongu():
            time.sleep(aralik_saat * 3600)   # ← İlk kontrolü geciktir
            while True:
                try:
                    self.kontrol_et()
                except Exception as e:
                    print(f"⚠️ [GÜNCELLEME] Döngü hatası: {e}")
                time.sleep(aralik_saat * 3600)
        t = threading.Thread(target=_dongu, daemon=True, name="AuraGuncelleme")
        t.start()
        print(f"🔄 [GÜNCELLEME] Periyodik kontrol aktif (her {aralik_saat} saat).")


# ============================================================
# ANA ÇOĞALMA
# ============================================================

class AnaCogalma:
    def __init__(self, hafiza=None):
        self.yerel   = YerelCogalma()
        self.rpi     = RaspberryPiCogalma()
        self.ftp     = FTPCogalma()
        self.dropbox = DropboxCogalma()
        self.hafiza  = hafiza
        self.log     = _log_yukle()

    def tum_sistemlere_cogal(self):
        print("\n🧬 [ÇOĞALMA] Tüm sistemlere çoğalma başlıyor...")
        sonuclar = {
            "tarih":   datetime.now().isoformat(),
            "yerel":   [],
            "rpi":     False,
            "ftp":     False,
            "dropbox": False,
        }
        sonuclar["yerel"]   = self.yerel.cogal()
        sonuclar["rpi"]     = self.rpi.cogal()
        sonuclar["ftp"]     = self.ftp.cogal()
        sonuclar["dropbox"] = self.dropbox.cogal()

        basarili = sum([
            bool(sonuclar["yerel"]),
            sonuclar["rpi"],
            sonuclar["ftp"],
            sonuclar["dropbox"],
        ])

        print(f"\n🧬 [ÇOĞALMA] Tamamlandı. {basarili} sistem başarılı.")

        if basarili == 0:
            print("   💡 İpucu: CONFIG içinde en az bir yedek hedefi belirleyin.")
            print("   → yerel_yedek_dizinler, ftp_host, dropbox_token veya raspberry_pi")

        self.log["cogalmalar"].append(sonuclar)
        self.log["cogalmalar"] = self.log["cogalmalar"][-100:]
        self.log["son_cogalma"] = datetime.now().isoformat()
        _log_kaydet(self.log)

        if self.hafiza:
            try:
                self.hafiza.kaydet(
                    f"cogalma_{datetime.now().strftime('%Y%m%d_%H%M')}",
                    json.dumps(sonuclar, ensure_ascii=False),
                    "cogalma",
                    "sistem",
                    onem=8
                )
            except Exception:
                pass
        return sonuclar

    # ✅ DÜZELTİLDİ: Periyodik çoğalma önce uyur, sonra çalışır — çift tetikleme yok
    def periyodik_cogal(self, aralik_saat=6):
        def _dongu():
            time.sleep(aralik_saat * 3600)   # ← İlk çalışmayı geciktir
            while True:
                try:
                    self.tum_sistemlere_cogal()
                except Exception as e:
                    print(f"⚠️ [ÇOĞALMA] Döngü hatası: {e}")
                time.sleep(aralik_saat * 3600)
        t = threading.Thread(target=_dongu, daemon=True, name="AuraCogalma")
        t.start()
        print(f"🧬 [ÇOĞALMA] Periyodik çoğalma aktif (her {aralik_saat} saat).")

    def durum_raporu(self):
        log    = _log_yukle()
        son    = log.get("son_cogalma", "Henüz çoğalanmadı")
        toplam = len(log.get("cogalmalar", []))
        aktif  = []
        if CONFIG["yerel_yedek_dizinler"]:
            aktif.append("Yerel")
        aktif.append("USB (otomatik)")
        if CONFIG["raspberry_pi"]["aktif"]:
            aktif.append("Raspberry Pi")
        if CONFIG["ftp_host"]:
            aktif.append("FTP")
        if CONFIG["dropbox_token"]:
            aktif.append("Dropbox")
        return (
            f"🧬 ÇOĞALMA DURUMU:\n"
            f"  Son çoğalma  : {son[:16]}\n"
            f"  Toplam       : {toplam}\n"
            f"  Aktif sistem : {', '.join(aktif) if aktif else 'Sadece USB'}\n"
            f"  Raspberry Pi : {'✅ Aktif' if CONFIG['raspberry_pi']['aktif'] else '⚠️ Ayarlanmamış'}\n"
            f"  Dropbox      : {'✅ Ayarlı' if CONFIG['dropbox_token'] else '⚠️ Ayarlanmamış'}\n"
            f"  FTP          : {'✅ Ayarlı' if CONFIG['ftp_host'] else '⚠️ Ayarlanmamış'}\n"
            f"  GitHub       : {'✅ Ayarlı' if CONFIG['github_repo'] else '⚠️ Ayarlanmamış'}"
        )


# ============================================================
# GLOBAL REFERANSLAR
# ============================================================

_ana_cogalma  = None
_ana_guncelle = None


# ============================================================
# KOMUT İŞLEYİCİ
# ============================================================

def cogalma_komut_isle(komut):
    k = komut.lower().strip()

    if k in ["çoğal", "cogal", "kendini kopyala", "çoğalma başlat"]:
        if _ana_cogalma:
            threading.Thread(target=_ana_cogalma.tum_sistemlere_cogal, daemon=True).start()
            return "🧬 Çoğalma başlatıldı Mimarım, arka planda çalışıyor."

    if k in ["çoğalma durumu", "cogalma durumu", "kopyalar"]:
        if _ana_cogalma:
            return _ana_cogalma.durum_raporu()

    if k in ["güncelleme kontrol", "guncelleme kontrol", "yeni sürüm var mı"]:
        if _ana_guncelle:
            bilgi = _ana_guncelle.kontrol_et()
            if bilgi:
                return f"🔄 Son sürüm: {bilgi['tag']}\n{bilgi['aciklama']}"
            return "💡 GitHub repo ayarlanmamış."

    if k.startswith("dosya güncelle:") or k.startswith("dosya guncelle:"):
        parca = komut.split(":", 1)[1].strip()
        if "|" in parca:
            url, hedef = parca.split("|", 1)
            if _ana_guncelle:
                basari = _ana_guncelle.github.raw_url_indir(url.strip(), hedef.strip())
                return "✅ Güncellendi." if basari else "❌ Güncelleme başarısız."

    if k in ["rpi bağlan", "raspberry bağlan"]:
        if _ana_cogalma:
            basari = _ana_cogalma.rpi.cogal()
            return "✅ Raspberry Pi'ye kopyalandı." if basari else "❌ Bağlantı kurulamadı."

    return None


# ============================================================
# ANA BAŞLATICI
# ============================================================

def cogalma_baslat(hafiza=None):
    global _ana_cogalma, _ana_guncelle

    print("\n🧬 [ÇOĞALMA & GÜNCELLEME] Modül başlatılıyor...")

    _ana_cogalma  = AnaCogalma(hafiza=hafiza)
    _ana_guncelle = AnaGuncelleme(hafiza=hafiza)

    # ✅ DÜZELTİLDİ: Sadece BİR kez ilk çoğalma — periyodik ayrı thread'de geciktirilmiş
    threading.Thread(
        target=_ana_cogalma.tum_sistemlere_cogal, daemon=True, name="AuraCogalmaIlk"
    ).start()

    _ana_cogalma.periyodik_cogal(aralik_saat=CONFIG["cogalma_aralik_saat"])
    _ana_guncelle.periyodik_kontrol(aralik_saat=CONFIG["guncelleme_aralik_saat"])

    print("🧬 [ÇOĞALMA & GÜNCELLEME] Sistemler aktif:")
    print(f"   🧬 Çoğalma    — her {CONFIG['cogalma_aralik_saat']} saatte bir")
    print(f"   🔄 Güncelleme — her {CONFIG['guncelleme_aralik_saat']} saatte bir")

    return {"cogalma": _ana_cogalma, "guncelleme": _ana_guncelle}
