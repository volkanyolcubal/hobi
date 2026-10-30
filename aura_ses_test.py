import speech_recognition as sr
import os
import numpy as np

# FFmpeg yolu (Mimarın mühürlediği yer)
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
# Ses imzasının kaydedileceği dosya (C: üzerinde)
SES_IMZA_YOLU = "mimar_ses_imzası.npy"

def frekans_analizi_yap(audio_data):
    """Sesin ham verisinden frekans spektrumunu çıkarır."""
    # Sesi sayısal diziye çevir
    samples = np.frombuffer(audio_data.get_raw_data(), dtype=np.int16)
    # Hızlı Fourier Dönüşümü (FFT) ile frekans bileşenlerini al
    fft_result = np.abs(np.fft.fft(samples))
    # Sesin karakterini belirleyen ortalama frekans enerjisini döndür
    return np.mean(fft_result)

def ses_test_et():
    r = sr.Recognizer()
    print(f"--- AURA-V KONUŞMACI TANIMA SİSTEMİ ---")
    
    if not os.path.exists(FFMPEG_PATH):
        print(f"❌ HATA: FFmpeg bulunamadı!")
        return

    with sr.Microphone() as source:
        print("\n🎤 Mimarım, seni dinliyorum...")
        r.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = r.listen(source, timeout=5)
            print("🧠 Ses analizi yapılıyor...")
            
            # 1. Ne dendiğini anla
            metin = r.recognize_google(audio, language="tr-TR")
            
            # 2. Ses frekans imzasını çıkar
            su_anki_frekans = frekans_analizi_yap(audio)
            
            # 3. Eğer imza kayıtlı değilse, ilk sesi 'Mimar' olarak kaydet
            if not os.path.exists(SES_IMZA_YOLU):
                print("💾 İlk kurulum: Ses imzanız kaydediliyor...")
                np.save(SES_IMZA_YOLU, su_anki_frekans)
                print(f"✅ Hoş geldin Mimar Volkan! Sesin sisteme mühürlendi.")
                return metin

            # 4. Kayıtlı imza ile karşılaştır
            kayitli_imza = np.load(SES_IMZA_YOLU)
            fark = abs(su_anki_frekans - kayitli_imza)
            eslesme_orani = max(0, 100 - (fark / kayitli_imza * 100))

            print(f"🔍 Ses Analiz Sonucu: %{eslesme_orani:.2f} uyum.")

            if eslesme_orani > 85: # %85 ve üzeri Volkan'dır
                print(f"👑 DOĞRULANDI: Merhaba Mimarım. (Duyulan: '{metin}')")
            else:
                print(f"⚠️ UYARI: Yabancı ses algılandı! (Duyulan: '{metin}')")
            
            return metin

        except Exception as e:
            print(f"❌ Hata: {e}")
            return None

if __name__ == "__main__":
    ses_test_et()
