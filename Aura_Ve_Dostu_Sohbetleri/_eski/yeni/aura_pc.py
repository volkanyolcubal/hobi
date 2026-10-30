"""
AURA-V — PC Kontrol Modülü
Sistem bilgisi, process, dosya, komut çalıştırma
"""
import os, platform, subprocess, psutil
import socket as _socket
import datetime

TEHLIKELI_KOMUTLAR = [
    'rm -rf', 'rmdir /s', 'format', 'mkfs', 'dd if=',
    'shutdown', 'reboot', 'halt', 'poweroff',
    ':(){:|:&};:', 'fork bomb',
    'chmod 777 /', '> /dev/sda',
]

def guncel_tarih_saat():
    now = datetime.datetime.now()
    gunler = ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"]
    aylar  = ["","Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
               "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
    gun = gunler[now.weekday()]
    return (f"{now.day} {aylar[now.month]} {now.year}, {gun}, "
            f"Saat: {now.strftime('%H:%M:%S')}")

def pc_sistem_bilgisi() -> str:
    """CPU, RAM, Disk, Ağ, IP bilgisi döndür."""
    try:
        cpu_pct  = psutil.cpu_percent(interval=0.5)
        cpu_freq = psutil.cpu_freq()
        cpu_core = psutil.cpu_count(logical=False)
        cpu_logi = psutil.cpu_count(logical=True)
        ram      = psutil.virtual_memory()
        ram_tot  = round(ram.total / (1024**3), 2)
        ram_kul  = round(ram.used  / (1024**3), 2)
        ram_pct  = ram.percent
        disk     = psutil.disk_usage('/')
        disk_tot = round(disk.total / (1024**3), 2)
        disk_kul = round(disk.used  / (1024**3), 2)
        disk_pct = disk.percent
        try:
            net     = psutil.net_io_counters()
            net_str = f"Gönderilen: {round(net.bytes_sent/(1024**3),3)} GB  |  Alınan: {round(net.bytes_recv/(1024**3),3)} GB"
        except Exception:
            net_str = "N/A"
        freq_str = f"{round(cpu_freq.current)}MHz" if cpu_freq else "N/A"
        hostname = _socket.gethostname()
        try:
            local_ip = _socket.gethostbyname(hostname)
        except Exception:
            local_ip = "N/A"
        return (
            f"🖥️  PC SİSTEM BİLGİSİ\n"
            f"Host: {hostname}  |  IP: {local_ip}\n"
            f"OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"CPU: %{cpu_pct} — {freq_str} — {cpu_core} Fiziksel / {cpu_logi} Mantıksal\n"
            f"RAM: {ram_kul}/{ram_tot} GB (%{ram_pct})\n"
            f"Disk: {disk_kul}/{disk_tot} GB (%{disk_pct})\n"
            f"Ağ I/O: {net_str}"
        )
    except Exception as e:
        return f"Sistem bilgisi hatası: {e}"

def pc_process_listesi(max_p: int = 15) -> str:
    """En çok CPU kullanan processleri listele."""
    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                procs.append(p.info)
            except Exception:
                pass
        procs.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
        satirlar = ["⚙️  PROCESS LİSTESİ (CPU'ya göre):"]
        satirlar.append(f"{'PID':>6}  {'AD':<28} {'CPU%':>5}  {'RAM%':>5}  DURUM")
        satirlar.append("-" * 60)
        for p in procs[:max_p]:
            satirlar.append(
                f"{p.get('pid','?'):>6}  {str(p.get('name','?'))[:28]:<28} "
                f"{p.get('cpu_percent',0):>5.1f}  "
                f"{p.get('memory_percent',0):>5.1f}  "
                f"{p.get('status','?')}"
            )
        return "\n".join(satirlar)
    except Exception as e:
        return f"Process listesi hatası: {e}"

def pc_dosya_listesi(yol: str = ".") -> str:
    """Dizin içeriğini listele."""
    try:
        yol = os.path.expanduser(yol.strip())
        if not os.path.exists(yol):
            return f"❌ Dizin bulunamadı: {yol}"
        items = os.listdir(yol)
        dirs  = sorted([i for i in items if os.path.isdir(os.path.join(yol, i))])
        files = sorted([i for i in items if os.path.isfile(os.path.join(yol, i))])
        satirlar = [f"📁 DİZİN: {os.path.abspath(yol)}  ({len(dirs)} klasör, {len(files)} dosya)"]
        for d in dirs[:40]:
            satirlar.append(f"  📂 {d}/")
        for f in files[:40]:
            fp = os.path.join(yol, f)
            try:
                boyut = os.path.getsize(fp)
                boyut_str = f"{boyut/1024:.1f} KB" if boyut < 1024*1024 else f"{boyut/(1024**2):.1f} MB"
            except Exception:
                boyut_str = "?"
            satirlar.append(f"  📄 {f}  ({boyut_str})")
        if len(dirs)+len(files) > 80:
            satirlar.append(f"  ... ve {len(dirs)+len(files)-80} dosya daha.")
        return "\n".join(satirlar)
    except Exception as e:
        return f"Dosya listesi hatası: {e}"

def pc_komut_calistir(komut: str, onay: bool = False) -> str:
    """Shell komutu çalıştır. Tehlikeli komutlar için onay ister."""
    komut_l = komut.lower()
    for tehlike in TEHLIKELI_KOMUTLAR:
        if tehlike in komut_l:
            if not onay:
                return f"⚠️ TEHLİKELİ KOMUT: '{komut}'\nOnaylamak için 'ONAYLA: {komut}' yaz."
    try:
        result = subprocess.run(
            komut, shell=True, capture_output=True, text=True,
            timeout=15, cwd=os.path.expanduser("~")
        )
        cikti = ((result.stdout or "") + (result.stderr or "")).strip()[:2000]
        return f"💻 KOMUT: {komut}\n\n{cikti or '(Çıktı yok)'}"
    except subprocess.TimeoutExpired:
        return f"⏱️ Zaman aşımı (15s): {komut}"
    except Exception as e:
        return f"Komut hatası: {e}"

def pc_servis_durumu() -> str:
    """İnternet, Ollama, pil, uptime durumu."""
    import requests as _req
    satirlar = ["🔌 SERVİS DURUMU:"]
    try:
        _req.get("https://www.google.com", timeout=3)
        satirlar.append("  ✅ İnternet: BAĞLI")
    except Exception:
        satirlar.append("  ❌ İnternet: BAĞLANTISIZ")
    try:
        r = _req.get("http://localhost:11434/api/tags", timeout=3)
        models = [m['name'] for m in r.json().get('models', [])]
        satirlar.append(f"  ✅ Ollama: AKTİF — {', '.join(models[:3])}")
    except Exception:
        satirlar.append("  ❌ Ollama: KAPALI")
    try:
        battery = psutil.sensors_battery()
        if battery:
            satirlar.append(f"  🔋 Pil: %{battery.percent:.0f} — {'Şarj oluyor' if battery.power_plugged else 'Pil'}")
    except Exception:
        pass
    try:
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
        satirlar.append(f"  ⏰ Uptime: {int(uptime.total_seconds()//3600)}s {int((uptime.total_seconds()%3600)//60)}dk")
    except Exception:
        pass
    return "\n".join(satirlar)

def pc_dosya_oku(dosya_yolu: str, max_kb: int = 50) -> str:
    """Metin dosyasını oku, max_kb kadar döndür."""
    try:
        yol = os.path.expanduser(dosya_yolu.strip())
        if not os.path.exists(yol):
            return f"❌ Dosya bulunamadı: {yol}"
        boyut = os.path.getsize(yol)
        max_byte = max_kb * 1024
        with open(yol, 'r', encoding='utf-8', errors='ignore') as f:
            icerik = f.read(max_byte)
        kirpildi = " [... kırpıldı]" if boyut > max_byte else ""
        return f"📄 DOSYA: {yol} ({round(boyut/1024,1)} KB)\n\n{icerik}{kirpildi}"
    except Exception as e:
        return f"Dosya okuma hatası: {e}"

def sistem_monitor_verisi() -> dict:
    """Sistem monitörü için anlık veri döndür."""
    try:
        cpu  = psutil.cpu_percent(interval=0)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        hostname = _socket.gethostname()
        try:
            ip = _socket.gethostbyname(hostname)
        except Exception:
            ip = "N/A"
        return {
            "cpu":      round(cpu, 1),
            "ram_kul":  round(ram.used  / (1024**3), 1),
            "ram_tot":  round(ram.total / (1024**3), 1),
            "ram_pct":  ram.percent,
            "disk_pct": disk.percent,
            "ip":       ip
        }
    except Exception:
        return {}
