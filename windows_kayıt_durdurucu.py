import subprocess
import sys
import ctypes
import os

def is_admin():
    """Yönetici yetkisi var mı kontrol et"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def psr_calisiyor_mu():
    """psr.exe şu anda çalışıyor mu?"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq psr.exe", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        return "psr.exe" in result.stdout.lower()
    except Exception as e:
        print(f"[!] Kontrol hatası: {e}")
        return False

def psr_oldur():
    """Çalışan psr.exe süreçlerini zorla kapat"""
    print("[*] Çalışan psr.exe süreçleri aranıyor...")
    try:
        # /F = zorla, /IM = image name, /T = alt süreçler dahil
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "psr.exe", "/T"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        cikti = (result.stdout or "") + (result.stderr or "")
        if "SUCCESS" in cikti.upper() or "başarılı" in cikti.lower():
            print("[+] psr.exe başarıyla öldürüldü.")
            return True
        elif "not found" in cikti.lower() or "bulunamadı" in cikti.lower():
            print("[i] Çalışan psr.exe bulunamadı (zaten kapalı).")
            return True
        else:
            print(f"[!] taskkill çıktısı: {cikti.strip()}")
            return False
    except Exception as e:
        print(f"[!] Öldürme hatası: {e}")
        return False

def psr_kalicilik_kapat():
    """Kayıt defterine DisableUAR=1 yazarak PSR'yi kalıcı devre dışı bırak"""
    print("[*] Kayıt defteri üzerinden PSR kalıcı olarak devre dışı bırakılıyor...")
    reg_yolu = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\AppCompat"
    try:
        # Anahtar yoksa oluştur
        subprocess.run(
            ["reg", "add", reg_yolu, "/f"],
            capture_output=True, text=True
        )
        # DisableUAR = 1 yaz
        result = subprocess.run(
            ["reg", "add", reg_yolu, "/v", "DisableUAR", "/t", "REG_DWORD", "/d", "1", "/f"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        if result.returncode == 0:
            print("[+] DisableUAR = 1 olarak ayarlandı. PSR artık kalıcı devre dışı.")
            return True
        else:
            print(f"[!] Kayıt defteri hatası: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"[!] Kayıt defteri hatası: {e}")
        return False

def psr_dosyasini_kilitle():
    """psr.exe'nin çalışmasını engellemek için alternatif: görev engelleme (opsiyonel)"""
    # Not: Bu yöntem bazı sistemlerde sorun çıkarabilir, dikkatli kullan
    psr_yolu = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "psr.exe")
    if os.path.exists(psr_yolu):
        print(f"[i] psr.exe konumu: {psr_yolu}")
        return True
    return False

def main():
    print("=" * 55)
    print("  PSR (Problem Steps Recorder) Durdurucu & Engelleyici")
    print("=" * 55)

    # 1) Yönetici kontrolü
    if not is_admin():
        print("[!] Bu script YÖNETİCİ olarak çalıştırılmalı!")
        print("[i] Sağ tık > 'Yönetici olarak çalıştır' ile tekrar dene.")
        input("\nÇıkmak için Enter'a bas...")
        sys.exit(1)

    print("[+] Yönetici yetkisi onaylandı.\n")

    # 2) Çalışıyor mu kontrol
    if psr_calisiyor_mu():
        print("[i] psr.exe şu anda ÇALIŞIYOR. Durduruluyor...")
        psr_oldur()
    else:
        print("[i] psr.exe şu anda çalışmıyor.")
        # Yine de garanti olsun diye taskkill dene
        psr_oldur()

    print()

    # 3) Kalıcı devre dışı bırak
    psr_kalicilik_kapat()

    print()
    psr_dosyasini_kilitle()

    print("\n" + "=" * 55)
    print("[✓] İşlem tamamlandı kanka!")
    print("[i] Değişikliğin tam etkili olması için bilgisayarı yeniden başlat.")
    print("[i] Geri almak istersen: DisableUAR değerini 0 yap veya sil.")
    print("=" * 55)
    input("\nÇıkmak için Enter'a bas...")

if __name__ == "__main__":
    main()
