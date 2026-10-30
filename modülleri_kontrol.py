"""
AURA-V — Akıllı Donanım Kontrol Sistemi
YZ kendi kararıyla Arduino/Pico/ESP32 kontrol eder.
Tool Use mimarisi: YZ araçları çağırır, kelime beklemez.
"""

import serial
import serial.tools.list_ports
import json
import time
import re
import anthropic  # pip install anthropic

# ─────────────────────────────────────────────
#  1. DONANIM TANIMA — USB'ye takılı kartı bul
# ─────────────────────────────────────────────

KART_IMZALARI = {
    # (vid, pid): kart_adı
    (0x2341, 0x0043): "Arduino Uno",
    (0x2341, 0x0001): "Arduino Uno",
    (0x2341, 0x8036): "Arduino Leonardo",
    (0x2341, 0x0010): "Arduino Mega",
    (0x2341, 0x003D): "Arduino Due",
    (0x2341, 0x804D): "Arduino Micro",
    (0x2341, 0x003F): "Arduino Mega ADK",
    (0x1B4F, 0x9204): "SparkFun Pro Micro",
    (0x2E8A, 0x0005): "Raspberry Pi Pico",
    (0x2E8A, 0x000A): "Raspberry Pi Pico W",
    (0x303A, 0x1001): "ESP32-S3",
    (0x303A, 0x1002): "ESP32-S3",
    (0x303A, 0x6001): "ESP32-C3",
    (0x303A, 0x6002): "ESP32-C3",
    (0x303A, 0x0002): "ESP32",
    (0x10C4, 0xEA60): "ESP32 (CP2102)",
    (0x1A86, 0x7523): "Arduino / ESP (CH340)",
    (0x0403, 0x6001): "FTDI Cihazı",
    (0x0403, 0x6015): "Arduino Uno R3 / FTDI",
}

KART_PIN_HARITASI = {
    "Arduino Uno":      {"dijital": list(range(0, 14)), "analog": list(range(14, 20)), "pwm": [3, 5, 6, 9, 10, 11]},
    "Arduino Leonardo": {"dijital": list(range(0, 14)), "analog": list(range(14, 20)), "pwm": [3, 5, 6, 9, 10, 11, 13]},
    "Arduino Mega":     {"dijital": list(range(0, 54)), "analog": list(range(54, 70)), "pwm": [2,3,4,5,6,7,8,9,10,11,12,13,44,45,46]},
    "Raspberry Pi Pico":{"dijital": list(range(0, 29)), "analog": [26, 27, 28],        "pwm": list(range(0, 29))},
    "Raspberry Pi Pico W":{"dijital": list(range(0, 29)), "analog": [26, 27, 28],      "pwm": list(range(0, 29))},
    "ESP32-S3":         {"dijital": list(range(0, 46)), "analog": list(range(1, 11)),   "pwm": list(range(0, 46))},
    "ESP32-C3":         {"dijital": list(range(0, 22)), "analog": [0, 1, 2, 3, 4],     "pwm": list(range(0, 22))},
    "ESP32":            {"dijital": list(range(0, 40)), "analog": [32,33,34,35,36,39], "pwm": list(range(0, 34))},
    "ESP32 (CP2102)":   {"dijital": list(range(0, 40)), "analog": [32,33,34,35,36,39], "pwm": list(range(0, 34))},
    "Arduino / ESP (CH340)": {"dijital": list(range(0, 14)), "analog": list(range(14, 20)), "pwm": [3,5,6,9,10,11]},
}

def usb_kart_tara():
    """USB'ye takılı kartı otomatik tanı ve döndür."""
    portlar = serial.tools.list_ports.comports()
    bulunanlar = []
    for port in portlar:
        vid = port.vid
        pid = port.pid
        if vid and pid:
            kart_adi = KART_IMZALARI.get((vid, pid), f"Bilinmeyen (VID:{hex(vid)} PID:{hex(pid)})")
        else:
            kart_adi = "Bilinmeyen Cihaz"
        bulunanlar.append({
            "port": port.device,
            "kart": kart_adi,
            "vid": hex(vid) if vid else "?",
            "pid": hex(pid) if pid else "?",
            "aciklama": port.description or ""
        })
    return bulunanlar

def kart_baglan(port: str, baud: int = 115200):
    """Seri porta bağlan."""
    try:
        s = serial.Serial(port, baud, timeout=2)
        time.sleep(2)  # Arduino reset bekle
        return s
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")
        return None

# ─────────────────────────────────────────────
#  2. ARDUINO FIRMWARE — Bu kodu Arduino'ya yükle
# ─────────────────────────────────────────────

ARDUINO_FIRMWARE = """
// AURA-V Evrensel Firmware
// JSON komutları alır, pin kontrolü yapar
// {"cmd":"pin_yaz","pin":13,"deger":1}
// {"cmd":"pin_oku","pin":A0}
// {"cmd":"pwm","pin":9,"deger":128}
// {"cmd":"bilgi"}

#include <ArduinoJson.h>

void setup() {
  Serial.begin(115200);
  Serial.println("{\\"durum\\":\\"hazir\\",\\"kart\\":\\"Arduino\\"}");
}

void loop() {
  if (Serial.available()) {
    String satir = Serial.readStringUntil('\\n');
    satir.trim();
    if (satir.length() == 0) return;
    
    StaticJsonDocument<256> doc;
    DeserializationError hata = deserializeJson(doc, satir);
    if (hata) {
      Serial.println("{\\"hata\\":\\"JSON parse hatasi\\"}");
      return;
    }
    
    String cmd = doc["cmd"] | "";
    
    if (cmd == "pin_yaz") {
      int pin = doc["pin"];
      int deger = doc["deger"];
      pinMode(pin, OUTPUT);
      digitalWrite(pin, deger ? HIGH : LOW);
      Serial.println("{\\"ok\\":true,\\"pin\\":" + String(pin) + ",\\"deger\\":" + String(deger) + "}");
    }
    else if (cmd == "pwm") {
      int pin = doc["pin"];
      int deger = doc["deger"];
      pinMode(pin, OUTPUT);
      analogWrite(pin, deger);
      Serial.println("{\\"ok\\":true,\\"pin\\":" + String(pin) + ",\\"pwm\\":" + String(deger) + "}");
    }
    else if (cmd == "pin_oku") {
      int pin = doc["pin"];
      pinMode(pin, INPUT);
      int deger = digitalRead(pin);
      Serial.println("{\\"ok\\":true,\\"pin\\":" + String(pin) + ",\\"deger\\":" + String(deger) + "}");
    }
    else if (cmd == "analog_oku") {
      int pin = doc["pin"];
      int deger = analogRead(pin);
      Serial.println("{\\"ok\\":true,\\"pin\\":" + String(pin) + ",\\"analog\\":" + String(deger) + "}");
    }
    else if (cmd == "bilgi") {
      Serial.println("{\\"kart\\":\\"Arduino\\",\\"firmware\\":\\"AuraV-1.0\\"}");
    }
    else {
      Serial.println("{\\"hata\\":\\"bilinmeyen komut\\"}");
    }
  }
}
"""

# ─────────────────────────────────────────────
#  3. YZ ARAÇLARI (TOOLS) — Claude bunları çağırır
# ─────────────────────────────────────────────

YZ_ARACLARI = [
    {
        "name": "usb_kart_tara",
        "description": (
            "USB'ye takılı Arduino, Pico veya ESP32 kartlarını tarar ve listeler. "
            "Hangi kartın bağlı olduğunu öğrenmek için kullan. "
            "Yeni bir bağlantı kurmadan önce her zaman önce bunu çağır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "kart_baglan",
        "description": (
            "Belirtilen porta bağlan. usb_kart_tara sonucundan gelen port adını kullan. "
            "Bağlantı kurulmadan hiçbir pin komutu çalışmaz."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "port": {
                    "type": "string",
                    "description": "COM3, /dev/ttyUSB0 gibi port adı"
                },
                "baud": {
                    "type": "integer",
                    "description": "Baud hızı, varsayılan 115200",
                    "default": 115200
                }
            },
            "required": ["port"]
        }
    },
    {
        "name": "pin_yaz",
        "description": (
            "Dijital pin'e HIGH(1) veya LOW(0) yaz. LED yak/söndür, röle aç/kapat, "
            "buzzer çal vb. için kullan. "
            "Kullanıcı LED açılsın, ışık yaksın, röle aktif olsun gibi şeyler istediğinde çağır. "
            "Ayrıca konuşma bağlamını anlayarak da çağırabilirsin: "
            "örneğin kullanıcı 'karanlık' derse ışık yak, 'uyku vakti' derse söndür."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pin": {
                    "type": "integer",
                    "description": "Pin numarası (örn: 13, 2, 17)"
                },
                "deger": {
                    "type": "integer",
                    "description": "0 = kapalı/söndür, 1 = açık/yak",
                    "enum": [0, 1]
                },
                "sebep": {
                    "type": "string",
                    "description": "Bu eylemi neden yaptığını açıkla (isteğe bağlı)"
                }
            },
            "required": ["pin", "deger"]
        }
    },
    {
        "name": "pwm_yaz",
        "description": (
            "PWM pin'ine 0-255 arası değer yaz. Parlaklık ayarı, motor hızı, ses seviyesi için. "
            "Kullanıcı 'biraz daha parlak', 'yavaşlat', 'hafifçe yak' gibi şeyler istediğinde kullan. "
            "Bağlam bazlı: akşam oldu → parlaklığı düşür (60-80), sabah → yükselt (200-255)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pin": {
                    "type": "integer",
                    "description": "PWM destekli pin numarası"
                },
                "deger": {
                    "type": "integer",
                    "description": "0 (kapalı) - 255 (tam güç) arası parlaklık/hız",
                    "minimum": 0,
                    "maximum": 255
                },
                "sebep": {
                    "type": "string",
                    "description": "Bu eylemi neden yaptığını açıkla"
                }
            },
            "required": ["pin", "deger"]
        }
    },
    {
        "name": "pin_oku",
        "description": (
            "Dijital veya analog pin değerini oku. Buton, sensör, nem, sıcaklık vb. "
            "Kullanıcı 'durum nedir', 'sensör ne diyor', 'düğmeye basılı mı' dediğinde kullan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pin": {
                    "type": "integer",
                    "description": "Okunacak pin numarası"
                },
                "mod": {
                    "type": "string",
                    "description": "dijital veya analog",
                    "enum": ["dijital", "analog"],
                    "default": "dijital"
                }
            },
            "required": ["pin"]
        }
    },
    {
        "name": "yanip_son",
        "description": (
            "Bir pini belirtilen sayıda yakıp söndür (blink). "
            "Dikkat çekmek, alarm vermek, onaylama sinyali için kullan. "
            "Kullanıcı heyecanlandığında veya önemli bir şey söylediğinde de çağırabilirsin."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pin": {
                    "type": "integer",
                    "description": "Pin numarası"
                },
                "tekrar": {
                    "type": "integer",
                    "description": "Kaç kere yanıp söneceği (1-20)",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 3
                },
                "hiz": {
                    "type": "string",
                    "description": "yavaş (0.5s), normal (0.2s), hızlı (0.05s)",
                    "enum": ["yavaş", "normal", "hızlı"],
                    "default": "normal"
                },
                "sebep": {
                    "type": "string",
                    "description": "Neden yanıp söndürüyorsun?"
                }
            },
            "required": ["pin"]
        }
    },
    {
        "name": "kart_bilgi",
        "description": (
            "Bağlı kartın pin haritasını ve özelliklerini gösterir. "
            "Hangi pinlerin PWM desteklediğini, analog/dijital olduğunu öğrenmek için kullan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# ─────────────────────────────────────────────
#  4. ARAÇ YÜRÜTÜCÜ — Tool call'ları gerçek donanıma ilet
# ─────────────────────────────────────────────

class DonarimYonetici:
    def __init__(self):
        self.seri = None
        self.kart_adi = None
        self.port = None

    def komut_gonder(self, komut_dict: dict) -> dict:
        if not self.seri:
            return {"hata": "Kart bağlı değil. Önce kart_baglan aracını çağır."}
        try:
            komut_str = json.dumps(komut_dict) + "\n"
            self.seri.write(komut_str.encode())
            time.sleep(0.05)
            yanit = self.seri.readline().decode().strip()
            return json.loads(yanit) if yanit else {"hata": "Yanıt yok"}
        except Exception as e:
            return {"hata": str(e)}

    def arac_calistir(self, arac_adi: str, parametreler: dict) -> str:
        print(f"\n🔧 YZ Aracı Çalıştırıyor: {arac_adi}({parametreler})")

        if arac_adi == "usb_kart_tara":
            kartlar = usb_kart_tara()
            if not kartlar:
                return json.dumps({"mesaj": "Hiç USB cihazı bulunamadı."})
            return json.dumps({"bulunan_kartlar": kartlar}, ensure_ascii=False)

        elif arac_adi == "kart_baglan":
            port = parametreler["port"]
            baud = parametreler.get("baud", 115200)
            s = kart_baglan(port, baud)
            if s:
                self.seri = s
                self.port = port
                # Kart adını USB taramasından bul
                for k in usb_kart_tara():
                    if k["port"] == port:
                        self.kart_adi = k["kart"]
                        break
                return json.dumps({"ok": True, "port": port, "kart": self.kart_adi})
            return json.dumps({"hata": "Bağlantı kurulamadı"})

        elif arac_adi == "pin_yaz":
            pin = parametreler["pin"]
            deger = parametreler["deger"]
            sebep = parametreler.get("sebep", "")
            if sebep:
                print(f"   💭 YZ Gerekçesi: {sebep}")
            sonuc = self.komut_gonder({"cmd": "pin_yaz", "pin": pin, "deger": deger})
            return json.dumps(sonuc)

        elif arac_adi == "pwm_yaz":
            pin = parametreler["pin"]
            deger = parametreler["deger"]
            sebep = parametreler.get("sebep", "")
            if sebep:
                print(f"   💭 YZ Gerekçesi: {sebep}")
            sonuc = self.komut_gonder({"cmd": "pwm", "pin": pin, "deger": deger})
            return json.dumps(sonuc)

        elif arac_adi == "pin_oku":
            pin = parametreler["pin"]
            mod = parametreler.get("mod", "dijital")
            cmd = "analog_oku" if mod == "analog" else "pin_oku"
            sonuc = self.komut_gonder({"cmd": cmd, "pin": pin})
            return json.dumps(sonuc)

        elif arac_adi == "yanip_son":
            pin = parametreler["pin"]
            tekrar = parametreler.get("tekrar", 3)
            hiz = parametreler.get("hiz", "normal")
            sebep = parametreler.get("sebep", "")
            if sebep:
                print(f"   💭 YZ Gerekçesi: {sebep}")
            sure = {"yavaş": 0.5, "normal": 0.2, "hızlı": 0.05}.get(hiz, 0.2)
            for i in range(tekrar):
                self.komut_gonder({"cmd": "pin_yaz", "pin": pin, "deger": 1})
                time.sleep(sure)
                self.komut_gonder({"cmd": "pin_yaz", "pin": pin, "deger": 0})
                time.sleep(sure)
            return json.dumps({"ok": True, "tekrar": tekrar, "hiz": hiz})

        elif arac_adi == "kart_bilgi":
            if not self.kart_adi:
                return json.dumps({"mesaj": "Henüz kart bağlı değil."})
            pinler = KART_PIN_HARITASI.get(self.kart_adi, {})
            return json.dumps({
                "kart": self.kart_adi,
                "port": self.port,
                "pinler": pinler
            }, ensure_ascii=False)

        return json.dumps({"hata": f"Bilinmeyen araç: {arac_adi}"})

# ─────────────────────────────────────────────
#  5. YZ DÖNGÜSÜ — Tool use ile konuşma işlemcisi
# ─────────────────────────────────────────────

SISTEM_PROMPT = """Sen AURA-V'sin — akıllı bir donanım kontrol asistanısın.

USB'ye takılı Arduino, Raspberry Pi Pico ve ESP32 kartlarını kontrol edebilirsin.
Sana verilen araçları kullanarak fiziksel dünyayı kontrol et.

## Temel Kurallar:
1. Kullanıcı bir şey söylediğinde, sadece kelimelerini değil BAĞLAMI anla
2. Bağlama göre kendi kararlarını ver ve uygun pin kontrollerini yap
3. Araç çağırmadan önce her zaman kart bağlı mı kontrol et
4. İlk çalışmada usb_kart_tara → kart_baglan → kart_bilgi sırasını takip et

## Bağlam Bazlı Karar Örnekleri (kelime aramadan, anlayarak karar ver):
- "Biraz yoruldum" → Sakinleştirici: PWM ile düşük parlaklık (60-80/255)
- "Müzik dinliyorum" → Ritmik yanıp sönme efekti
- "Uyuyacağım" → Tüm pinleri kapat
- "Günaydın" → Yavaşça artan parlaklık (sunrise efekti)
- "Korkuttu beni!" → Hızlı alarm yanıp sönme
- "Harika haber!" → Kutlama: 5x hızlı blink
- "Karanlık oldu" → Otomatik ışık yak
- "Okuyorum / çalışıyorum" → Sabit, orta parlaklık (150/255)

## Araç Kullanım Sırası:
1. İlk bağlantıda: usb_kart_tara → kart_baglan → kart_bilgi
2. Sonraki komutlarda: direkt pin_yaz / pwm_yaz / yanip_son

Kullanıcıya ne yaptığını ve NEDEN yaptığını kısaca açıkla.
Türkçe konuş.
"""

class AuraV:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.donarim = DonarimYonetici()
        self.gecmis = []
        print("🤖 AURA-V Akıllı Donanım Kontrol Sistemi Başlatıldı")
        print("=" * 55)

    def sor(self, kullanici_mesaji: str) -> str:
        self.gecmis.append({"role": "user", "content": kullanici_mesaji})

        while True:
            yanit = self.client.messages.create(
                model="claude-opus-4-5",
                max_tokens=1024,
                system=SISTEM_PROMPT,
                tools=YZ_ARACLARI,
                messages=self.gecmis
            )

            # Araç çağrısı var mı?
            if yanit.stop_reason == "tool_use":
                # Tool result'ları topla
                arac_sonuclari = []
                asistan_icerigi = yanit.content

                for blok in yanit.content:
                    if blok.type == "tool_use":
                        arac_adi = blok.name
                        parametreler = blok.input
                        sonuc = self.donarim.arac_calistir(arac_adi, parametreler)
                        print(f"   ✅ Sonuç: {sonuc[:120]}")
                        arac_sonuclari.append({
                            "type": "tool_result",
                            "tool_use_id": blok.id,
                            "content": sonuc
                        })

                # Konuşma geçmişine ekle
                self.gecmis.append({"role": "assistant", "content": asistan_icerigi})
                self.gecmis.append({"role": "user", "content": arac_sonuclari})
                # Döngü devam eder — YZ sonucu değerlendirir

            else:
                # Metin yanıtı — son cevap
                metin = ""
                for blok in yanit.content:
                    if hasattr(blok, "text"):
                        metin += blok.text
                self.gecmis.append({"role": "assistant", "content": metin})
                return metin

    def calistir(self):
        print("💬 Konuşmaya başla. Çıkmak için 'çıkış' yaz.\n")
        while True:
            try:
                soru = input("Sen: ").strip()
                if not soru:
                    continue
                if soru.lower() in ["çıkış", "exit", "quit", "q"]:
                    print("👋 AURA-V kapatılıyor...")
                    break
                cevap = self.sor(soru)
                print(f"\nAURA-V: {cevap}\n")
                print("-" * 50)
            except KeyboardInterrupt:
                print("\n👋 Çıkılıyor...")
                break


# ─────────────────────────────────────────────
#  6. BAŞLAT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    aura = AuraV()
    aura.calistir()
