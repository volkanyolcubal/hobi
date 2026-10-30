@echo off
echo ========================================
echo   AURA-V KURULUM BAŞLIYOR
echo ========================================
echo Python kontrol ediliyor...
python --version
echo Gerekli kütüphaneler kuruluyor...
pip install ollama pyserial psutil requests beautifulsoup4 pyttsx3 SpeechRecognition pyautogui opencv-python
echo Ollama indiriliyor...
echo ollama.com adresinden Ollama'yı indirin ve kurun
echo Sonra: ollama pull llama3.1:8b
echo ========================================
echo KURULUM TAMAMLANDI
echo aura_v.py dosyasını çalıştırın
pause
