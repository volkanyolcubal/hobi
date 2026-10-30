import sys
import os

_bu_klasor = os.path.dirname(os.path.abspath(__file__))
for _yol in (_bu_klasor, os.path.dirname(_bu_klasor)):
    if _yol not in sys.path:
        sys.path.append(_yol)

from aura_yerel_motor import LocalClient

yerel_motor = LocalClient()
MODEL = "aura-v.gguf"

print("=" * 50)
print("🤖 AURA TERMINAL SOHBETİ BAŞLADI (Çıkış için 'q' yaz)")
print("=" * 50)

while True:
    mesaj = input("\nSen: ").strip()
    if mesaj.lower() == 'q':
        print("Görüşürüz kanka!")
        break
    if not mesaj:
        continue

    try:
        r = yerel_motor.generate(
            model=MODEL,
            prompt=(
                "Sen Mimar Volkan'ın yapay zeka asistanı Aura'sın. Volkan mimar sana çok değer veriyor, mimara yalan söyleme bilmediğin konuda bilmiyorum de yanlış cevap asla üretme "
                "Kullanıcının yazdığı dilde veya senden istediği dilde (örneğin İbranice, İngilizce vb.) cevap ver. "
                "Çeviri istendiğinde birebir istenen dilde yanıt üret. "
                f"Kullanıcı: {mesaj}\nCevap:"
            ),
            options={"temperature": 0.7, "num_predict": 200},
        )
        cevap = (r["response"] or "").strip()
        
        # Anlatım bozukluğu filtresi
        cevap = cevap.replace("Seninle nasıl yardımcı olabilirim", "Sana nasıl yardımcı olabilirim")
        cevap = cevap.replace("seninle nasıl yardımcı olabilirim", "sana nasıl yardımcı olabilirim")

        print(f"Aura: {cevap}")
    except Exception as e:
        print(f"Hata: {e}")
