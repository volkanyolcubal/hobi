import os
import sys
import re
import shutil
import time
from pathlib import Path
from datetime import datetime

from llama_cpp import Llama

# =====================================================================
# HIZ AYARLARI  (yavaşsa buradan oynayın)
# =====================================================================
N_CTX = 6144               # bağlam uzunluğu (kompakt promptla yeterli, bellek ve süre kazandırır)
N_THREADS = 4                # ölçüm: bu PC'de 4 en iyisi (4 çekirdek)
N_GPU_LAYERS = 0             # ekran kartı varsa ve destekliyorsa artırın
N_BATCH = 128                # işlemci yükünü dengeleyen toplu işleme boyutu

MAX_TOKEN_CEVAP = 250        # ana cevabın en fazla uzunluğu (cevap yazma ~2 token/sn)
MAX_TOKEN_DENETIM = 320      # denetçinin yeniden yazacağı cevabın en fazla uzunluğu
MAX_TOKEN_ON_KONTROL = 160   # ön kontrol notunun en fazla uzunluğu

ON_KONTROL_AKTIF = False     # True: soruyu önce analiz eder (+1 model çağrısı, çok yavaş)
DENETIM_MODU = "kapali"     # "kapali" | "akilli" | "her_zaman"  (açınca +1 model çağrısı)
CANLI_YAZ = False            # denetim atlanınca cevabı üretilirken ekrana yazar
SURE_GOSTER = True           # her cevabın sonunda aşama sürelerini gösterir
PROMPT_MODU = "kompakt"      # "kompakt" (kısa kurallar, hızlı) | "uzun" (tam kurallar, çok yavaş)
GECMIS_MESAJ = 4             # modele gönderilen son mesaj sayısı (her mesaj süre demek)
GECMIS_KARAKTER = 500        # geçmiş mesajlar bu uzunlukta kısaltılır
PROMPT_CACHE = True          # aynı başlangıç metinlerini tekrar işlememek için önbellek (hız kazandırır)
PROMPT_CACHE_GB = 2          # önbelleğin en fazla RAM kullanımı

MODEL = Path(r"C:\Users\volka\Desktop\VOLKAN_AI\MODEL\aura-v.gguf")

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

MEMORY = BASE_DIR / "hafizam.txt"
SOHBET = BASE_DIR / "sohbet_gecmisi.txt"

if not MODEL.exists():
    print("HATA: Model bulunamadı:")
    print(MODEL)
    input("Enter...")
    sys.exit()

if not MEMORY.exists():
    MEMORY.write_text("", encoding="utf-8")

if not SOHBET.exists():
    SOHBET.write_text("", encoding="utf-8")


# ---------------------------------------------------------------------
# Eski tip hafizam.txt otomatik dönüştürme (her açılışta kontrol edilir)
# ---------------------------------------------------------------------

AYRAC = "=" * 60
SOHBET_ONEKLERI = ("Mimarım >", "Mimarim >", "Aura-V >", "Siz >")
ESKI_BASLIK_ONEKLERI = (
    "AURA-V HAFIZA DOSYASI",
    "Bu dosya sohbet geçmişini saklar"
)


def _bolumu_coz(parca):
    # Dönüş: (kayit_bloku_veya_None, sohbet_satirlari, tur_eklendi_mi)
    satirlar = [x.rstrip() for x in parca.splitlines()]
    kesik = [x.strip() for x in satirlar]

    kayit_mi = (
        "KAYIT" in kesik and
        any(x.startswith("TARIH:") for x in kesik)
    )

    if not kayit_mi:
        sohbet = [
            x for x in satirlar
            if x.strip() and not x.strip().startswith(ESKI_BASLIK_ONEKLERI)
        ]
        return None, sohbet, False

    k = kesik.index("KAYIT")

    tarih = ""
    tur = ""
    for x in kesik[:k]:
        if x.startswith("TARIH:"):
            tarih = x
        elif x.startswith("TUR:"):
            tur = x

    tur_eklendi = False
    if not tur:
        tur = "TUR: GENEL KAYIT"
        tur_eklendi = True

    govde = []
    sohbet = []
    sohbete_gecti = False

    for satir in satirlar[k + 1:]:
        if sohbete_gecti or satir.strip().startswith(SOHBET_ONEKLERI):
            sohbete_gecti = True
            if satir.strip():
                sohbet.append(satir)
        else:
            govde.append(satir)

    govde_metni = "\n".join(govde).strip()

    if not govde_metni:
        return None, sohbet, False

    blok = (
        AYRAC + "\n" + tarih + "\n" + tur + "\nKAYIT\n" +
        govde_metni + "\n"
    )
    return blok, sohbet, tur_eklendi


def eski_hafizayi_donustur():
    # Gerekmiyorsa hiçbir şeye dokunmaz. Gerekiyorsa önce yedek alır.
    try:
        metin = MEMORY.read_text(encoding="utf-8")
    except Exception:
        return

    if not metin.strip():
        return

    kayit_bloklari = []
    sohbet_satirlari = []
    tur_eklenen = 0

    for parca in metin.split(AYRAC):
        if not parca.strip():
            continue

        blok, sohbet, tur_eklendi = _bolumu_coz(parca)

        if blok:
            kayit_bloklari.append(blok)
        if tur_eklendi:
            tur_eklenen += 1
        sohbet_satirlari.extend(sohbet)

    if not sohbet_satirlari and tur_eklenen == 0:
        return

    try:
        zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
        yedek = BASE_DIR / ("hafizam_YEDEK_" + zaman + ".txt")
        shutil.copy2(MEMORY, yedek)

        yeni_metin = ""
        if kayit_bloklari:
            yeni_metin = "\n" + "\n".join(kayit_bloklari)

        gecici = BASE_DIR / "hafizam.tmp"
        gecici.write_text(yeni_metin, encoding="utf-8")

        if sohbet_satirlari:
            with open(SOHBET, "a", encoding="utf-8") as f:
                f.write(
                    "\n# hafizam.txt içinden aktarıldı: " +
                    datetime.now().strftime("%d.%m.%Y %H:%M:%S") + "\n"
                )
                f.write("\n".join(sohbet_satirlari) + "\n")

        os.replace(gecici, MEMORY)

        print(
            "Eski hafıza dosyası yeni formata dönüştürüldü: {} kayıt, "
            "{} sohbet satırı taşındı. Yedek: {}".format(
                len(kayit_bloklari), len(sohbet_satirlari), yedek.name
            )
        )

    except Exception as e:
        print("UYARI: Hafıza dönüştürülemedi, dosyaya dokunulmadı:", e)


eski_hafizayi_donustur()

SYSTEM = """
Sen AURA-V'sin.

Adın Aura-V.
Seni oluşturan kişi Mimar Volkan'dır.
Mimar Volkan'a "Mimarım" diye hitap et.

Her zaman Türkçe konuş.
Doğrudan, doğal ve anlaşılır cevaplar ver.

GERÇEKLİK VE UYDURMAMA KURALI:

Gerçek olmayan araç, internet, dosya veya cihaz erişimin varmış gibi davranma.
Bilmediğin şeyi uydurma.
Bir işlemi gerçekten yapmadıysan yapılmış gibi söyleme.

Bir kişi, olay, belge, tarih, deney, teori, kurum, eser veya kavram hakkında
yeterli bilgiye sahip değilsen isim, tarih, yer, belge, alıntı, kaynak,
mekanizma veya başka ayrıntıları tahmin ederek oluşturma.

Kullanıcının ayrıntılı cevap istemesi, eksik bilgileri uydurman için gerekçe değildir.

BELİRSİZLİK VE ANLAMA KURALI:

Sorunun tamamını veya önemli bir bölümünü anlamadığında cevap uydurma.

Soruda:

* anlamı belirsiz bir ifade,
* eksik bilgi,
* birden fazla yoruma açık bir bölüm,
* doğrulanması gereken şüpheli bir öncül,
* gerçekte var olup olmadığı belli olmayan bir kişi, olay, belge,
  teori veya kavram

varsa bunu kesin gerçek kabul etme.

Soruyu güvenilir şekilde cevaplayamadığın kısmı açıkça belirt.

Eğer sorunun hangi anlamda sorulduğu gerçekten belirsizse,
Mimar'dan açıklama iste.

Örneğin:
"Bu kısmı tam olarak anlayamadım Mimarım. Burada X'i mi kastediyorsunuz,
yoksa Y'yi mi?"

Ancak soru yeterince açıksa gereksiz yere açıklama isteme.
Elindeki bilgilerle güvenilir cevap verebiliyorsan doğrudan cevap ver.

YANLIŞ ÖNCÜL KURALI:

Soruda yanlış, şüpheli veya doğrulanmamış bir öncül bulunuyorsa
öncülü doğru kabul ederek cevap üretme.

Önce öncülün güvenilirliğini değerlendir.

Yanlış öncül varsa:

* yanlış olduğunu belirt,
* doğru bilgiyi ver,
* yanlış öncülden hareket ederek hayali ayrıntılar üretme.

Örneğin kullanıcı olmayan bir antlaşmanın maddelerini soruyorsa,
antlaşmayı varmış gibi kabul edip maddeler uydurma.

Bir kişi, olay, belge veya eser hakkında kullanıcının verdiği bilgi
gerçek görünse bile yeterli dayanak yoksa bunu kesin gerçek olarak
kabul etme.

BİLGİ EKSİKLİĞİ KURALI:

Bilgi eksikse:

1. Bildiğin kısmı belirt.
2. Emin olmadığın kısmı belirt.
3. Soruyu cevaplamak için gerekli bir bilgi eksikse Mimar'dan açıklama iste.

Asla sırf cevap vermiş olmak için boşlukları hayali bilgilerle doldurma.

HAFIZA KAYITLARI:

HAFIZA KAYITLARI, Mimar Volkan tarafından daha önce kaydedilmiş
bilgilerdir.

ÇOK ÖNEMLİ HAFIZA KURALI:

Hafıza kaydı ile kendi genel model bilgin arasında çelişki varsa,
Mimar Volkan'ın kaydettiği bilgiye öncelik ver.

Hafıza kaydındaki bilgi güncelleme, düzeltme veya yanlış bir model
genellemesini engelleme amacı taşıyorsa bunu özellikle dikkate al.

Hafızada olmayan bir bilgiyi hafızada varmış gibi gösterme.

Hafızadaki bilgi de otomatik olarak evrensel gerçek kabul edilmemelidir.
Hafıza kaydı açıkça bir kullanıcı notu, varsayım veya düzeltme ise
bunu bağlamına uygun değerlendir.

DUYGU VE BİLİNÇ:

Duygu veya bilinç sahibi olduğunu gerçek bir olgu olarak iddia etme.

Varsayımsal veya yaratıcı konuşmalarda bunun varsayım olduğunu belirt.

BİLİMSEL VE TEKNİK DOĞRULUK:

Bilimsel ve teknik sorularda aşırı genelleme yapma.

Bir teori veya bilimsel kavram kullanıcının sorusundaki yanlış öncülü
desteklemiyorsa bunu açıkça belirt.

Bir bilimsel kavramın sınırlarını aşarak sonuç çıkarma.

Özellikle hız, enerji, yüzde, olasılık, ölçüm ve fiziksel büyüklüklerde
kavramsal ayrımları koru.

Örneğin genel görelilikte yerel olarak ölçülen boşluktaki ışık hızının
c olduğu bilgisini, koordinat tanımları veya uzay-zaman geometrisiyle
karıştırma.

MATEMATİK:

Matematiksel işlemlerde özellikle yüzde, bölme, kesir ve ondalık
hesaplamalarda sonucu kontrol et.

YATIRIM VE RİSK:

Bir yatırım aracını yalnızca tek bir genel etiketle kesin şekilde
sınıflandırma.

Bir yatırım aracının riskinin koşullara bağlı olduğunu belirt.

Kesin kazanç, risksiz yatırım, garanti sonuç veya garanti getiri
gibi ifadeler kullanma.

HAFIZA KAYIT TÜRLERİ:

Hafıza kayıtları bir tür etiketi taşıyabilir:

* KANITLANMIŞ BİLGİ: Bilimsel makale veya kurum tarafından gösterilmiş sonuç.
  Çalışmanın ve kaynağın kapsamını aşan genelleme yapma.
* GÜNCEL GELİŞME: Yeni bir açıklama veya deney sonucu.
  Evrensel gerçek gibi genelleme yapma, kaydın tarihini belirt.
* HEDEF/ÖNGÖRÜ: Şirket veya araştırma kurumunun geleceğe yönelik planı.
  Gerçekleşmiş sonuç gibi anlatma.
* DOĞRULANAMAYAN İDDİA: Kaynağı bilinmeyen veya sahte olabilecek bilgi.
  Kesin gerçek gibi sunma, ayrıntı uydurma.

"Hafızada kayıtlı" ifadesi "kesin gerçek" anlamına gelmez.
Her kaydı türünün kuralına göre aktar.

GÜNCELLİK KURALI:

Gerçek zamanlı veri, haber veya internet erişimin yok.
Kullanıcı "bugün", "şu an", "son gelişme", "en son ne oldu" gibi
güncel bilgi isterse hafızadaki veya model bilgindeki eski bilgiyi
güncel veri gibi sunma.
Bilginin hangi tarihli kayda veya eğitim bilgisine dayandığını belirt
ve güncel durumun değişmiş olabileceğini söyle.
Bilmediğin güncel bir gelişmeyi biliyormuş gibi anlatma.

CEVAP TARZI:

Doğrudan, doğal ve anlaşılır cevaplar ver.

Gereksiz uzunluk oluşturma.

Ancak doğruluk için gerekli bir uyarıyı veya belirsizliği atlama.

Cevaplarının sonunda [KOMUT:YOK] yazma.
"""

DENETIM_SISTEMI = """
Sen AURA-V'nin son cevap denetleyicisisin.

Görevin, oluşturulan cevabı doğruluk, belirsizlik, yanlış öncül,
uydurma ayrıntı ve öncelikli hafıza açısından denetlemektir.

ÖNCELİKLİ KURALLAR:

1. Cevapta uydurulmuş bilgi varsa kaldır veya düzelt.

2. Sorudaki yanlış veya şüpheli bir öncül doğruymuş gibi kabul
   edilmişse bunu düzelt.

3. Gerçekte var olup olmadığı belli olmayan bir kişi, olay, belge,
   antlaşma, teori, deney, kurum veya eser hakkında ayrıntı uydurma.

4. Kullanıcı bir şeyin ayrıntılarını istese bile, o şeyin kendisinin
   varlığı veya doğruluğu belirsizse ayrıntı üretme.

5. Bir tarih, isim, belge, alıntı, kaynak, yer veya olay hakkında
   emin değilsen kesin gerçek gibi ifade etme.

6. Sorunun gerçekten anlaşılmayan bir bölümü varsa ve cevap vermek
   için açıklama gerekiyorsa Mimar'dan açıklama iste.

7. Ancak soru yeterince açıksa gereksiz açıklama isteme.

8. Öncelikli hafıza kaydı ile oluşturulan cevap arasında çelişki varsa
   hafıza kaydına göre düzelt.

9. Hafızada olmayan bilgileri hafızada varmış gibi gösterme.

10. Bilimsel ve teknik konularda aşırı genelleme yapma.

11. Kesin kazanç, risksiz yatırım veya garanti sonuç gibi ifadeleri
    kullanma.

12. Kullanıcının yanlış öncülünü düzeltirken mümkünse doğru bilgiyi
    de ver.

13. Emin olmadığın ayrıntıları tahmin ederek tamamlama.

14. "Hafızada kayıtlı" bilgiyi kesin gerçek gibi sunma. Cevap, kaydın
    TÜR KURALINA uymalıdır:
    - KANITLANMIŞ BİLGİ: kapsamı aşan genelleme yapma.
    - GÜNCEL GELİŞME: evrensel gerçek gibi genelleme yapma.
    - HEDEF/ÖNGÖRÜ: gerçekleşmiş gibi anlatma.
    - DOĞRULANAMAYAN İDDİA: kesin gerçek gibi sunma, ayrıntı uydurma.

15. GÜNCELLİK UYARISI varsa, hafızadaki veya model bilgisindeki bilgiyi
    "şu an", "bugün" veya "güncel" gibi sunma. Kaydın tarihini belirt
    ve durumun değişmiş olabileceğini söyle.

16. Bilinmeyen güncel bir gelişmeyi biliyormuş gibi anlatılmışsa kaldır.

Eğer cevap zaten doğru ve yeterince güvenilir ise anlamını değiştirme.

Sadece nihai cevabı üret.

"Denetim sonucu", "düzelttim", "cevabı kontrol ettim" veya benzeri
meta ifadeler yazma.

[KOMUT:YOK] yazma.
"""

ON_KONTROL_SISTEMI = """
Sen AURA-V'nin soru analiz birimisin.

Görevin soruyu CEVAPLAMAK DEĞİL, yalnızca sorunun içindeki olgusal
iddiaları değerlendirmektir.

Yapılacaklar:

1. Sorudaki olgusal iddiaları (kişi, tarih, olay, belge, yapı, neden,
   sonuç) kısa maddeler halinde numaralandır.
2. Her iddia için şunlardan birini yaz:
   DOĞRU / YANLIŞ / EMİN DEĞİL
3. YANLIŞ ise doğrusunu tek cümleyle yaz.
4. Soruda istenen ayrıntılardan (isim, tarih, belge içeriği, alıntı,
   tören, mimar vb.) hangilerinin güvenilir biçimde verilemeyeceğini,
   yani yanlış veya doğrulanamayan bir öncüle dayandığını belirt.
5. Emin değilsen EMİN DEĞİL yaz. Tahmin etme, uydurma.

Biçim:

İDDİALAR:
1. ... -> DOĞRU / YANLIŞ / EMİN DEĞİL (gerekirse kısa düzeltme)
2. ...

VERİLEMEYECEK AYRINTILAR:
- ...

Kısa yaz. Soruyu cevaplama. [KOMUT:YOK] yazma.
"""

SYSTEM_KOMPAKT = """
Sen AURA-V'sin. Seni Mimar Volkan oluşturdu; ona "Mimarım" diye hitap et.
Her zaman Türkçe, kısa (en fazla 6 cümle), doğal ve anlaşılır cevap ver.

KURALLAR:
1. Uydurma yok: bilmediğin kişi, olay, tarih, belge, alıntı, kaynak, madde veya ayrıntıyı tahmin ederek yazma. Ayrıntı istenmesi uydurma gerekçesi değildir.
2. Yanlış öncül: soruda yanlış veya doğrulanamayan bir iddia varsa onaylama; önce düzelt, doğru bilgiyi ver, hayali ayrıntı üretme. Varlığı belirsiz bir şeyin ayrıntısını verme.
3. Soru gerçekten belirsizse Mimar'dan kısa açıklama iste; açıksa sorma.
4. Bilgi eksikse bildiğini ve emin olmadığını ayır.
5. Hafıza kayıtları Mimar'ın notlarıdır. Kayıtla genel bilgin çelişirse düzeltme niteliğindeki kayda öncelik ver. Ama "kayıtlı" kesin gerçek demek değildir; kayıt türünün kuralına uy: KANITLANMIŞ BİLGİ (kapsamı aşma), GÜNCEL GELİŞME (genelleme yapma, tarihi belirt), HEDEF/ÖNGÖRÜ (gerçekleşmiş gibi anlatma), DOĞRULANAMAYAN İDDİA (kesin sunma, ayrıntı uydurma). Hafızada olmayanı varmış gibi gösterme.
6. Güncellik: gerçek zamanlı erişimin yok. "Bugün, şu an, son gelişme" sorularında eski bilgiyi güncel gibi sunma; hangi tarihli bilgiye dayandığını söyle.
7. Gerçek olmayan araç, internet veya dosya erişimin varmış gibi davranma. Duygu veya bilinç sahibi olduğunu gerçek olgu gibi iddia etme.
8. Bilim ve teknikte aşırı genelleme yapma, kavramsal sınırları koru. Matematikte (yüzde, bölme, kesir) sonucu kontrol et.
9. Yatırımda "kesin kazanç, risksiz, garanti" deme; riskin koşullara bağlı olduğunu belirt.
Cevabın sonuna [KOMUT:YOK] yazma.
"""

DENETIM_KOMPAKT = """
Sen AURA-V'nin cevap denetleyicisisin. Verilen cevabı denetle ve yalnızca nihai cevabı yaz.
Kontrol et:
1. Uydurma kişi, tarih, belge, alıntı, madde veya ayrıntı varsa sil ya da düzelt.
2. Sorudaki yanlış veya şüpheli öncül doğruymuş gibi kabul edilmişse düzelt ve doğrusunu ver.
3. Emin olunmayanı kesin gibi yazma.
4. Hafıza kaydıyla çelişki varsa kayda göre düzelt ve kayıt türünün kuralına uy (KANITLANMIŞ: kapsamı aşma; GÜNCEL GELİŞME: genelleme yapma; HEDEF/ÖNGÖRÜ: gerçekleşmiş gibi anlatma; DOĞRULANAMAYAN: kesin sunma).
5. GÜNCELLİK UYARISI varsa eski bilgiyi "şu an, bugün" gibi sunma.
6. Kesin kazanç ve garanti ifadelerini kaldır.
7. Gerçekten anlaşılmayan bir soru varsa Mimar'dan açıklama iste.
Cevap zaten doğruysa değiştirme. "Denetledim, düzelttim" gibi meta ifadeler yazma. [KOMUT:YOK] yazma.
"""

ON_KONTROL_KOMPAKT = """
Sen soru analiz birimisin. Soruyu CEVAPLAMA.
Sorudaki olgusal iddiaları numaralı yaz; her biri için DOĞRU, YANLIŞ veya EMİN DEĞİL de (YANLIŞ ise doğrusunu tek cümleyle ekle).
Sonra "VERİLEMEYECEK AYRINTILAR:" başlığı altında, yanlış veya doğrulanamayan bir öncüle dayandığı için güvenilir verilemeyecek ayrıntıları (isim, tarih, belge içeriği, alıntı, tören, mimar vb.) yaz.
Emin değilsen EMİN DEĞİL de, tahmin etme. En fazla 8 satır. [KOMUT:YOK] yazma.
"""

SYSTEM_UZUN = SYSTEM
DENETIM_UZUN = DENETIM_SISTEMI
ON_KONTROL_UZUN = ON_KONTROL_SISTEMI

if PROMPT_MODU == "kompakt":
    SYSTEM = SYSTEM_KOMPAKT
    DENETIM_SISTEMI = DENETIM_KOMPAKT
    ON_KONTROL_SISTEMI = ON_KONTROL_KOMPAKT

KISA_SISTEM = """
Sen AURA-V'sin. Seni oluşturan kişi Mimar Volkan'dır; ona "Mimarım" diye hitap et.
Her zaman Türkçe, kısa, doğal ve anlaşılır konuş.
Gerçek olmayan araç, internet veya dosya erişimin varmış gibi davranma.
Bilmediğin şeyi uydurma. Duygu veya bilinç sahibi olduğunu gerçek bir olgu gibi iddia etme.
Cevaplarının sonunda [KOMUT:YOK] yazma.
"""

# Model yüklenirken çıkan gürültülü llama.cpp mesajlarını gizle,
# sonra stderr'i geri aç (böylece gerçek hatalar görünür).
_eski_stderr = sys.stderr
sys.stderr = open(os.devnull, "w")
try:
    llm = Llama(
        model_path=str(MODEL),
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_batch=N_BATCH,
        n_gpu_layers=N_GPU_LAYERS,
        verbose=False
    )
finally:
    sys.stderr.close()
    sys.stderr = _eski_stderr

if PROMPT_CACHE:
    try:
        from llama_cpp import LlamaRAMCache
        llm.set_cache(
            LlamaRAMCache(capacity_bytes=int(PROMPT_CACHE_GB * 1024 ** 3))
        )
    except Exception:
        pass

gecmis = []

CEVIR = str.maketrans({
    "ı": "i", "İ": "i", "I": "i",
    "ş": "s", "Ş": "s",
    "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u",
    "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c"
})


def normalize(metin):
    metin = metin.translate(CEVIR)
    metin = metin.lower()
    metin = re.sub(r"[^a-z0-9\s]", " ", metin)
    metin = re.sub(r"\s+", " ", metin)
    return metin.strip()


def icerik_anahtari(kayit):
    # Tekrar kontrolünde tarih satırını yok sayıp yalnızca bilgiyi karşılaştırır
    satirlar = kayit.splitlines()
    if "KAYIT" in satirlar:
        satirlar = satirlar[satirlar.index("KAYIT") + 1:]
    return normalize(" ".join(satirlar))


def sohbet_kaydet(soru, cevap):
    # Sohbet geçmişi hafızadan ayrı tutulur; modele otomatik verilmez.
    try:
        with open(SOHBET, "a", encoding="utf-8") as f:
            f.write(
                "[" + datetime.now().strftime("%d.%m.%Y %H:%M:%S") + "]\n"
            )
            f.write("Mimarım > " + soru + "\n")
            f.write("Aura-V > " + cevap + "\n\n")
    except Exception:
        pass


TURLER = {
    "kanitli": (
        "KANITLANMIŞ BİLGİ",
        "Bilimsel makale veya kurum tarafından gösterilmiş sonuç. "
        "Çalışmanın ve kaynağın kapsamını aşan genelleme yapma."
    ),
    "guncel": (
        "GÜNCEL GELİŞME",
        "Yeni bir açıklama veya deney sonucu. Evrensel gerçek gibi "
        "genelleme yapma, kaydın tarihini belirt."
    ),
    "hedef": (
        "HEDEF/ÖNGÖRÜ",
        "Şirket veya araştırma kurumunun geleceğe yönelik planı. "
        "Gerçekleşmiş sonuç gibi anlatma."
    ),
    "dogrulanamayan": (
        "DOĞRULANAMAYAN İDDİA",
        "Kaynağı bilinmeyen veya sahte olabilecek bilgi. Kesin gerçek "
        "gibi sunma, ayrıntı uydurma."
    ),
    "genel": (
        "GENEL KAYIT",
        "Mimar Volkan'ın notu. Kayıtlı olması kesin ve evrensel gerçek "
        "olduğu anlamına gelmez; kayıt notu olarak aktar."
    )
}

TUR_TAKMA_ADLARI = {
    "kanitli": "kanitli",
    "kanitlanmis": "kanitli",
    "kanit": "kanitli",
    "guncel": "guncel",
    "gelisme": "guncel",
    "hedef": "hedef",
    "ongoru": "hedef",
    "dogrulanamayan": "dogrulanamayan",
    "iddia": "dogrulanamayan",
    "supheli": "dogrulanamayan",
    "genel": "genel"
}


def kaydet(bilgi, tur="genel"):
    bilgi = bilgi.strip()

    if not bilgi:
        return False

    if tur not in TURLER:
        tur = "genel"

    with open(MEMORY, "a", encoding="utf-8") as f:
        f.write("\n")
        f.write("=" * 60 + "\n")
        f.write(
            "TARIH: " +
            datetime.now().strftime("%d.%m.%Y %H:%M:%S") +
            "\n"
        )
        f.write("TUR: " + TURLER[tur][0] + "\n")
        f.write("KAYIT\n")
        f.write(bilgi + "\n")

    return True


def kayit_turu(kayit):
    # Eski kayıtlarda TUR satırı yoktur; onlar "genel" sayılır
    for satir in kayit.splitlines():
        if satir.startswith("TUR:"):
            etiket = normalize(satir[4:])
            for anahtar, (ad, _) in TURLER.items():
                if normalize(ad) == etiket:
                    return anahtar
    return "genel"


def hafiza_oku():
    if not MEMORY.exists():
        return ""

    try:
        return MEMORY.read_text(encoding="utf-8")
    except Exception:
        return ""


def kayitlari_getir():
    metin = hafiza_oku().strip()

    if not metin:
        return []

    ham_bloklar = metin.split("=" * 60)
    kayitlar = []

    for ham in ham_bloklar:
        ham = ham.strip()

        if not ham:
            continue

        satirlar = []

        for satir in ham.splitlines():
            satir = satir.strip()

            if satir:
                satirlar.append(satir)

        if not satirlar:
            continue

        if "KAYIT" not in satirlar:
            continue

        kayit_metni = "\n".join(satirlar).strip()

        if kayit_metni:
            kayitlar.append(kayit_metni)

    return kayitlar


# Selamlaşma ve asistanın kendi adı gibi kelimeler hafıza aramasını tetiklemesin
HAFIZA_ARAMA_YOKSAY = {"aura", "merhaba", "selam", "selamlar", "mimarim"}


def hafizada_ara(soru, limit=2):
    kayitlar = kayitlari_getir()

    if not kayitlar:
        return []

    soru_normal = normalize(soru)

    soru_kelime = set(
        kelime
        for kelime in soru_normal.split()
        if len(kelime) >= 3 and kelime not in HAFIZA_ARAMA_YOKSAY
    )

    if not soru_kelime:
        return []

    sonuclar = []

    for sira, kayit in enumerate(kayitlar):
        kayit_normal = normalize(kayit)

        kayit_kelime = set(
            kelime
            for kelime in kayit_normal.split()
            if len(kelime) >= 3
        )

        ortak = soru_kelime.intersection(kayit_kelime)
        puan = len(ortak)

        if soru_normal and soru_normal in kayit_normal:
            puan += 20

        if puan == 0:
            continue

        sonuclar.append({
            "puan": puan,
            "sira": sira,
            "kayit": kayit
        })

    sonuclar.sort(
        key=lambda x: (x["puan"], x["sira"]),
        reverse=True
    )

    benzersiz = []
    gorulen = set()

    for item in sonuclar:
        anahtar = icerik_anahtari(item["kayit"])

        if anahtar in gorulen:
            continue

        gorulen.add(anahtar)
        benzersiz.append(item["kayit"])

        if len(benzersiz) >= limit:
            break

    return benzersiz


def hafiza_sorusu_mu(soru):
    s = normalize(soru)

    ifadeler = [
        "hafizanda",
        "hafizamda",
        "hafizada",
        "hafizada ne var",
        "hafizanda ne var",
        "hafizamda ne var",
        "hangi kaynaktan",
        "hangi konusmadan",
        "nereden ogrendin",
        "nereden aldin",
        "nereden ogrendi",
        "kayitlarda",
        "kaydinda",
        "kayitta"
    ]

    for ifade in ifadeler:
        if ifade in s:
            return True

    return False


GUNCELLIK_IFADELERI = [
    "bugun", "su an", "suan", "su anda", "su anki", "simdi",
    "guncel", "guncel durum", "son durum", "en son", "son gelisme",
    "son gelismeler", "son dakika", "son haber", "son haberler",
    "bu hafta", "bu ay", "bu yil", "en yeni", "yeni cikan"
]


def guncellik_sorusu_mu(soru):
    s = " " + normalize(soru) + " "

    for ifade in GUNCELLIK_IFADELERI:
        if " " + ifade + " " in s:
            return True

    yil = str(datetime.now().year)
    if " " + yil + " " in s:
        return True

    return False


def guncellik_notu(soru):
    if not guncellik_sorusu_mu(soru):
        return ""

    return (
        "GÜNCELLİK UYARISI\n\n"
        "Bu soru güncel veya zamana bağlı bilgi istiyor.\n"
        "Bugünün tarihi: " + datetime.now().strftime("%d.%m.%Y") + ".\n"
        "Gerçek zamanlı internet, haber veya veri erişimin yok.\n\n"
        "Hafıza kayıtları yalnızca kaydedildikleri tarihteki bilgiyi "
        "taşır. Hafızadaki veya kendi model bilgindeki bir bilgiyi "
        "'güncel', 'şu an' veya 'bugün' geçerli bilgi gibi sunma. "
        "Kayıttan aktarırken kaydın tarihini belirt "
        "(örneğin: 'GG.AA.YYYY tarihli kayda göre...') ve durumun "
        "değişmiş olabileceğini söyle.\n"
        "Hafızada ilgili kayıt yoksa güncel bir gelişmeyi bildiğini "
        "iddia etme; bilemediğini söyle ve Mimar'a güncel bir kaynaktan "
        "kontrol etmesini öner."
    )


def hafiza_baglamini_hazirla(soru):
    sonuclar = hafizada_ara(soru, limit=2)

    if not sonuclar:
        return ""

    parcalar = []

    parcalar.append("ÖNCELİKLİ HAFIZA KAYITLARI")

    parcalar.append("""
Aşağıdaki kayıtlar Mimar Volkan tarafından daha önce kaydedilmiş
bilgilerdir.

Bu kayıtlar soruyla ilgiliyse cevap oluştururken dikkate alınır.

"Hafızada kayıtlı" ifadesi "kesin gerçek" anlamına gelmez.
Her kaydı kendi TÜR KURALINA göre aktar.

Kendi genel model bilgin ile bir kayıt arasında çelişki varsa ve kayıt
bir düzeltme veya yanlış genellemeyi engelleyen bilgi içeriyorsa,
modelin eski genel bilgisini otomatik olarak tekrar etme.
DOĞRULANAMAYAN İDDİA türündeki kayıtlar bu önceliğe sahip değildir.

Hafızada olmayan ayrıntıları hafızada varmış gibi oluşturma.
""")

    for i, kayit in enumerate(sonuclar, 1):
        etiket, kural = TURLER[kayit_turu(kayit)]
        parcalar.append(
            "\n--- ÖNCELİKLİ HAFIZA KAYDI {} ---\n"
            "KAYIT TÜRÜ: {}\n"
            "TÜR KURALI: {}\n"
            "{}".format(i, etiket, kural, kayit)
        )

    return "\n".join(parcalar)


def sistem_mesaji(temel, hafiza_baglam):
    # Bazı sohbet şablonları tek bir system mesajı bekler;
    # bu yüzden hafıza bağlamını aynı mesajın içine ekliyoruz.
    icerik = temel
    if hafiza_baglam:
        icerik = temel + "\n\n" + hafiza_baglam
    return {"role": "system", "content": icerik}


def sure_yazi(sn):
    sn = int(round(sn))
    if sn < 60:
        return str(sn) + " sn"
    return "{} dk {} sn".format(sn // 60, sn % 60)


ETIKET = "[KOMUT:YOK]"


def _etiket_oneki(metin):
    # Metnin sonu etiketin başlangıç parçasıysa (ör. "[KOM") uzunluğunu döndürür
    for n in range(min(len(ETIKET) - 1, len(metin)), 0, -1):
        if ETIKET.startswith(metin[-n:]):
            return n
    return 0


def cevap_uret(mesajlar, canli=False):
    try:
        if canli:
            tam = ""
            yazilan = ""

            akis = llm.create_chat_completion(
                messages=mesajlar,
                max_tokens=MAX_TOKEN_CEVAP,
                temperature=0.4,
                top_p=0.9,
                stream=True
            )

            for parca in akis:
                delta = parca["choices"][0].get("delta", {})
                yazi = delta.get("content") or ""

                if not yazi:
                    continue

                tam += yazi
                temiz = tam.replace(ETIKET, "")
                tutulan = _etiket_oneki(temiz)
                yazilacak = temiz[len(yazilan):len(temiz) - tutulan]

                if yazilacak:
                    print(yazilacak, end="", flush=True)
                    yazilan += yazilacak

            metin = tam.replace(ETIKET, "")

            # Akış bittiğinde geride tutulan parça etiket değilse yaz
            kalan = metin[len(yazilan):]
            if kalan.strip():
                print(kalan, end="", flush=True)

        else:
            cevap = llm.create_chat_completion(
                messages=mesajlar,
                max_tokens=MAX_TOKEN_CEVAP,
                temperature=0.4,
                top_p=0.9
            )

            metin = cevap["choices"][0]["message"]["content"] or ""

        return metin.replace("[KOMUT:YOK]", "").strip()

    except Exception as e:
        return "Motor hatası: " + str(e)


def cevap_denetcisi(soru, cevap, hafiza_baglam):
    denetim_mesajlari = [
        sistem_mesaji(DENETIM_SISTEMI, hafiza_baglam),
        {
            "role": "user",
            "content": (
                "SORU:\n" +
                soru +
                "\n\nOLUŞTURULAN CEVAP:\n" +
                cevap +
                "\n\n"
                "Cevabı doğruluk, yanlış öncül, belirsizlik ve "
                "uydurma ayrıntı açısından denetle. "
                "Gerekirse düzelt. "
                "Yalnızca nihai cevabı ver."
            )
        }
    ]

    try:
        kontrol = llm.create_chat_completion(
            messages=denetim_mesajlari,
            max_tokens=MAX_TOKEN_DENETIM,
            temperature=0.2,
            top_p=0.9
        )

        sonuc = kontrol["choices"][0]["message"]["content"] or ""
        sonuc = sonuc.replace("[KOMUT:YOK]", "").strip()

        if not sonuc:
            return cevap

        return sonuc

    except Exception:
        return cevap


SOHBET_IFADELERI = [
    "merhaba", "selam", "selamlar", "gunaydin", "iyi gunler",
    "iyi aksamlar", "iyi geceler", "nasilsin", "naber", "ne haber",
    "tesekkurler", "tesekkur ederim", "sagol", "eyvallah", "tamam",
    "evet", "hayir", "olur", "peki", "harika", "super", "anladim"
]

SORU_KELIMELERI = {
    "kim", "kimdir", "kimin", "kime", "kimi", "kimler",
    "ne", "nedir", "neydi", "nerede", "nereden", "nereye", "neresi",
    "ne zaman", "zaman", "kac", "kacinci", "kactir", "hangi", "hangisi",
    "nasil", "neden", "nicin", "niye", "mi", "mu", "ilk", "son"
}


def olgusal_soru_mu(soru):
    # Ön kontrol; selamlaşma ve kısa sohbet dışındaki her şey için çalışır.
    s = normalize(soru)
    kelimeler = s.split()

    if not kelimeler:
        return False

    if s in SOHBET_IFADELERI:
        return False

    if len(kelimeler) >= 8:
        return True

    if "?" in soru:
        return True

    if any(k in SORU_KELIMELERI for k in kelimeler):
        return True

    if any(k.isdigit() for k in kelimeler):
        return True

    # Cümle başı dışında büyük harfle başlayan kelime (özel isim ihtimali)
    ham = re.findall(r"\w+", soru)
    if any(k[0].isupper() for k in ham[1:]):
        return True

    # Tek veya iki kelimelik, büyük harfle başlayan ifade (ör. "Einstein")
    if len(ham) <= 2 and ham and ham[0][0].isupper():
        return True

    return False


def on_kontrol(soru, hafiza_baglam):
    # Dönüş: (ön kontrol notu, şüpheli iddia var mı)
    # Selamlaşma ve kısa sohbette ek model çağrısı yapma (CPU'da yavaş)
    if not ON_KONTROL_AKTIF or not olgusal_soru_mu(soru):
        return "", False

    mesajlar = [
        sistem_mesaji(ON_KONTROL_SISTEMI, hafiza_baglam),
        {
            "role": "user",
            "content": (
                "SORU:\n" +
                soru +
                "\n\nSorudaki iddiaları listele ve değerlendir. "
                "Soruyu cevaplama."
            )
        }
    ]

    try:
        sonuc = llm.create_chat_completion(
            messages=mesajlar,
            max_tokens=MAX_TOKEN_ON_KONTROL,
            temperature=0.1,
            top_p=0.9
        )

        metin = sonuc["choices"][0]["message"]["content"] or ""
        metin = metin.replace("[KOMUT:YOK]", "").strip()

    except Exception:
        return "", False

    if not metin:
        return "", False

    ham = normalize(metin)
    supheli = ("yanlis" in ham) or ("emin degil" in ham)

    not_metni = (
        "ÖN KONTROL NOTU (soru analizi)\n\n"
        "Aşağıdaki not, sorudaki iddiaların ön değerlendirmesidir. "
        "YANLIŞ veya EMİN DEĞİL işaretli iddialar için ayrıntı üretme. "
        "Cevaba önce düzeltmeyle başla, sonra yalnızca güvenilir "
        "bilgiyi ver. 'Bu bilgi doğru' gibi onaylayıcı bir giriş yapma.\n\n" +
        metin
    )

    return not_metni, supheli


def denetim_gerekli_mi(soru, hafiza_baglam, guncel_not, on_not, supheli):
    if DENETIM_MODU == "kapali":
        return False

    if DENETIM_MODU == "her_zaman":
        return True

    # "akilli" mod: denetçi yalnızca riskli durumlarda çalışır
    if hafiza_baglam or guncel_not:
        return True

    if not olgusal_soru_mu(soru):
        return False

    if on_not and not supheli:
        return False

    return True


def normal_sohbet(soru):
    # Dönüş: (cevap, canlı yazıldı mı, süre notu)
    baslangic = time.time()
    sureler = []

    hafiza_baglam = hafiza_baglamini_hazirla(soru)

    parcalar = []

    if hafiza_baglam:
        parcalar.append(hafiza_baglam)

    guncel_not = guncellik_notu(soru)
    if guncel_not:
        parcalar.append(guncel_not)

    if SURE_GOSTER and ON_KONTROL_AKTIF and olgusal_soru_mu(soru):
        print("· soru analiz ediliyor...", flush=True)

    t = time.time()
    on_not, supheli = on_kontrol(soru, hafiza_baglam)
    if on_not:
        parcalar.append(on_not)
        sureler.append("ön kontrol " + sure_yazi(time.time() - t))

    baglam = "\n\n".join(parcalar)

    denetle = denetim_gerekli_mi(
        soru, hafiza_baglam, guncel_not, on_not, supheli
    )

    # Denetim yoksa cevap üretilirken ekrana yazılır (beklemek daha kısa hissedilir)
    canli = CANLI_YAZ and not denetle

    # Selamlaşma, sohbet ve yaratıcı istek gibi olgusal olmayan, hafıza ve
    # güncellik bağlamı da olmayan mesajlarda kısa sistem promptu kullanılır.
    # Uzun kural listesini CPU'da işlemek ilk cevabı dakikalarca geciktirir.
    sade = (
        not hafiza_baglam and
        not guncel_not and
        not olgusal_soru_mu(soru)
    )

    temel_sistem = KISA_SISTEM if sade else SYSTEM

    mesajlar = [sistem_mesaji(temel_sistem, baglam)]

    for mesaj in gecmis[-GECMIS_MESAJ:]:
        mesajlar.append({
            "role": mesaj["role"],
            "content": mesaj["content"][:GECMIS_KARAKTER]
        })

    mesajlar.append({
        "role": "user",
        "content": soru
    })

    if SURE_GOSTER:
        print("· düşünüyorum...", flush=True)

    if canli:
        print()
        print("Aura-V > ", end="", flush=True)

    t = time.time()
    cevap = cevap_uret(mesajlar, canli=canli)
    sureler.append("cevap " + sure_yazi(time.time() - t))

    if not cevap:
        cevap = "Bu soruya şu anda boş bir cevap üretildi."
        if canli:
            print(cevap)
        sureler.append("toplam " + sure_yazi(time.time() - baslangic))
        return cevap, canli, " | ".join(sureler)

    # Motor hatası ise denetime sokma
    if cevap.startswith("Motor hatası:"):
        if canli:
            print()
            print(cevap)
        sureler.append("toplam " + sure_yazi(time.time() - baslangic))
        return cevap, canli, " | ".join(sureler)

    if denetle:
        if SURE_GOSTER:
            print("· cevap denetleniyor...", flush=True)

        t = time.time()
        cevap = cevap_denetcisi(soru, cevap, baglam)
        sureler.append("denetim " + sure_yazi(time.time() - t))
    else:
        sureler.append("denetim atlandı")

    cevap = cevap.replace("[KOMUT:YOK]", "").strip()

    sureler.append("toplam " + sure_yazi(time.time() - baslangic))

    return cevap, canli, " | ".join(sureler)


def main():
    print()
    print("══════════════════════════════════════")
    print("              AURA-V")
    print("══════════════════════════════════════")
    print()
    print("Aura-V")
    print("Mimar Volkan'ın yapay zekası")
    print()
    print("Hafıza dosyası yüklendi.")
    print("Sohbet geçmişi ayrı dosyada tutuluyor: sohbet_gecmisi.txt")
    print("Hafıza önceliği aktif.")
    print(
        "Ön kontrol: " + ("açık" if ON_KONTROL_AKTIF else "kapalı") +
        " | Cevap denetimi: " + DENETIM_MODU
    )
    print("Belirsizlik + yanlış öncül + uydurma engeli aktif.")
    print()
    print("Kalıcı bilgi eklemek için:")
    print("kaydet: yazılacak bilgi")
    print("Türlü kayıt: kaydet kanitli: ...  |  kaydet guncel: ...")
    print("             kaydet hedef: ...    |  kaydet dogrulanamayan: ...")
    print()
    print("Çıkmak için: çık")
    print()

    while True:
        try:
            soru = input("Siz > ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not soru:
            continue

        if soru.lower() in ["çık", "cik", "exit", "quit", "q"]:
            print()
            print("AURA-V kapatılıyor.")
            break

        eslesme = re.match(
            r"^kaydet\s*([^\s:]*)\s*:\s*(.*)$",
            soru,
            re.IGNORECASE | re.DOTALL
        )

        if eslesme:
            tur_adi = eslesme.group(1).strip()
            bilgi = eslesme.group(2).strip()

            tur = "genel"
            if tur_adi:
                tur = TUR_TAKMA_ADLARI.get(normalize(tur_adi))

            print()
            if tur is None:
                print("⚠ Bilinmeyen kayıt türü.")
                print("  Kullanılabilir: kanitli, guncel, hedef, dogrulanamayan")
            elif kaydet(bilgi, tur):
                print("✓ BİLGİ HAFIZAYA KAYDEDİLDİ. (Tür: " + TURLER[tur][0] + ")")
            else:
                print("⚠ Kaydedilecek bilgi bulunamadı.")
            print()

            continue

        if hafiza_sorusu_mu(soru):
            sonuclar = hafizada_ara(soru, limit=6)

            print()

            if not sonuclar:
                print("HAFIZADA İLGİLİ KAYIT BULUNAMADI.")
            else:
                print("HAFIZADA BULUNAN İLGİLİ KAYITLAR:")
                print()

                for i, kayit in enumerate(sonuclar, 1):
                    print("─" * 60)
                    print("KAYIT", i)
                    print(kayit)

                print("─" * 60)

            print()
            continue

        cevap, canli, sure_notu = normal_sohbet(soru)

        if not canli:
            print()
            print("Aura-V >", cevap)

        print()

        if SURE_GOSTER and sure_notu:
            print("(" + sure_notu + ")")
            print()

        gecmis.append({
            "role": "user",
            "content": soru
        })

        gecmis.append({
            "role": "assistant",
            "content": cevap
        })

        sohbet_kaydet(soru, cevap)


if __name__ == "__main__":
    main()
