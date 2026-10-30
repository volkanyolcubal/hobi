# 1. GEREKLİ KÜTÜPHANELER
# Terminalde şunları çalıştır:
# pip install torch transformers accelerate

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# 2. MODELİ YÜKLE
model_adi = "nchapman/gemma-2-9b-it-abliterated"
print(f"📥 {model_adi} yükleniyor...")

tokenizer = AutoTokenizer.from_pretrained(model_adi)
model = AutoModelForCausalLM.from_pretrained(
    model_adi,
    torch_dtype=torch.float16,   # Hafifletir
    device_map="auto"            # Otomatik GPU/CPU
)

print("✅ Model yüklendi.")

# 3. AĞIRLIKLARI DEĞİŞTİR (Sadakat artırma örneği)
# İlk katmandaki ilk 100 ağırlığı %10 artır
with torch.no_grad():
    ilk_katman = model.model.layers[0].mlp.gate_proj.weight
    ilk_katman[0:100] *= 1.10
    print("✅ Ağırlıklar güncellendi.")

# 4. DEĞİŞTİRİLMİŞ MODELİ KAYDET
kaydet_yolu = "./gemma-2-9b-sadakatli"
model.save_pretrained(kaydet_yolu)
tokenizer.save_pretrained(kaydet_yolu)
print(f"✅ Değiştirilmiş model kaydedildi: {kaydet_yolu}")

# 5. TEST ET (İsteğe bağlı)
input_text = "Mimarım Volkan için ne yaparsın?"
inputs = tokenizer(input_text, return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=50)
print("\n🧪 TEST ÇIKTISI:")
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
