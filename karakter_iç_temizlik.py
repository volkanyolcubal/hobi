import json

dosya = r"C:\Users\volka\AppData\Local\Programs\Python\Python311\deepsekYZ\karakter_hafizasi.json"

with open(dosya, encoding='utf-8') as f:
    veri = json.load(f)

# Düz liste ise
if isinstance(veri, list):
    temiz = [k for k in veri if "KisilikMotoru" not in str(k)]
    with open(dosya, 'w', encoding='utf-8') as f:
        json.dump(temiz, f, ensure_ascii=False, indent=2)
    print(f"Temizlendi. Kalan: {len(temiz)} kayıt")

# Dict ise
elif isinstance(veri, dict):
    for key in veri:
        if isinstance(veri[key], list):
            veri[key] = [k for k in veri[key] if "KisilikMotoru" not in str(k)]
    with open(dosya, 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    print("Temizlendi.")
import json

dosya = r"C:\Users\volka\AppData\Local\Programs\Python\Python311\deepsekYZ\volkaniya_bilgi_havuzu.json"

with open(dosya, encoding='utf-8') as f:
    veri = json.load(f)

if isinstance(veri, list):
    temiz = [k for k in veri if "KisilikMotoru" not in str(k)]
elif isinstance(veri, dict):
    temiz = {k: v for k, v in veri.items() if "KisilikMotoru" not in str(v)}

with open(dosya, 'w', encoding='utf-8') as f:
    json.dump(temiz, f, ensure_ascii=False, indent=2)

print(f"Temizlendi: {len(temiz)} kayıt")
import json

dosya = r"C:\Users\volka\AppData\Local\Programs\Python\Python311\deepsekYZ\karakter_hafizasi.json"

with open(dosya, encoding='utf-8') as f:
    veri = json.load(f)

# Son 50 konuşmayı sil, eskiler kalsın
if isinstance(veri, list):
    veri = veri[:-50]
    with open(dosya, 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    print(f"Temizlendi. Kalan: {len(veri)} konuşma")

import json, re
dosya = r"C:\Users\volka\AppData\Local\Programs\Python\Python311\deepsekYZ\karakter_hafizasi.json"
d = json.load(open(dosya, encoding='utf-8'))
for k in d:
    if isinstance(k, dict) and 'aura' in k:
        k['aura'] = re.sub(r'<[^>]+>', '', k['aura']).replace('<bos>', '').strip()
json.dump(d, open(dosya,'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print("Temizlendi")    
