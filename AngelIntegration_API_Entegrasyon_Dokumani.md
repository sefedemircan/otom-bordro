# **AngelIntegration API Entegrasyon Dokümanı** 

Entegrasyon Dokümanı 

## **AngelIntegration API** 

Meyer Angel Sistemleri için Web Servis Entegrasyon Rehberi 

**API Sürümü:** v2 

**Belge Türü:** Kullanıcı ve Yazılım Geliştirici Rehberi 

**Kimlik Doğrulama:** Bearer Token (HTTP Header) 

**Veri Formatı:** JSON 

**Tarih:** 22 Temmuz 2026 

## **İçindekiler** 

1. Genel Bakış 

2. Kimlik Doğrulama (Authentication) 

3. Genel Kurallar ve Yanıt Formatı 

5. Token Servisi (Kimlik Doğrulama) 

6. Sicil Servisi (Personel Kayıtları) 

7. İzin Servisi 

8. İzin Onay Servisi 

9. Fazla Mesai Servisi 

10. Hareket Servisi (Giriş-Çıkış Kayıtları) 

11. Vardiya Servisi 

12. Puantaj Servisi 

13. Geçiş Yetki Servisi 

14. Kapı Açma Servisi 

15. Terminal Servisi 

16. Fotoğraf Servisi 

17. Ziyaretçi Servisi 

#### 18. Doküman Servisi 

### **1. Genel Bakış** 

**AngelIntegration API** , Meyer Angel geçiş kontrol, personel takip (PDKS), izin, fazla mesai, vardiya ve ziyaretçi yönetimi sistemleri ile üçüncü parti yazılımlar (İK sistemleri, bordro programları, ERP çözümleri vb.) arasında veri alışverişi yapılmasını sağlayan bir web servisidir. 

Bu doküman iki farklı okuyucu kitlesi için hazırlanmıştır: 

- **Müşteri / iş birimi tarafı:** API'nin hangi iş süreçlerine hizmet ettiğini, hangi bilgilerin karşılıklı olarak paylaşıldığını ve entegrasyonun genel işleyişini anlamak isteyenler için. 

- **Yazılım geliştirici tarafı:** Entegrasyonu teknik olarak kodlayacak, her bir servis metodunun istek/yanıt yapısını, alan tiplerini ve örnek JSON gövdelerini görmek isteyenler için. 

API, standart HTTP protokolü üzerinden **JSON** formatında çalışır. Servisler, iş fonksiyonlarına göre aşağıdaki başlıklar altında gruplanmıştır: Token (kimlik doğrulama), Sicil (personel kaydı), İzin, İzin Onay, Fazla Mesai, Hareket (geçiş kayıtları), Vardiya, Puantaj, Geçiş Yetki, Kapı Açma, Terminal, Fotoğraf, Ziyaretçi ve Doküman servisleri. 

Entegrasyonu gerçekleştirecek yazılım ekibinin, aşağıdaki "Kimlik Doğrulama" ve "Genel Kurallar" bölümlerini ilk olarak incelemesi, ardından ihtiyaç duyulan servis grubuna ait bölümden ilerlemesi önerilir. 

### **2. Kimlik Doğrulama (Authentication)** 

API üzerindeki tüm servislere erişim **Bearer Token** yöntemi ile korunmaktadır. Bu nedenle entegrasyon akışının ilk adımı her zaman **Token Servisi** üzerinden bir erişim jetonu (token) almaktır. 

#### **Adım Adım Kimlik Doğrulama Akışı** 

- **1. Adım —** Meyer tarafından size özel tanımlanan username, password ve varsa pin bilgileri ile POST /API/TokenServisi/Token adresine istek gönderilir. 

- **2. Adım —** Servis, başarılı bir doğrulama sonrasında data alanında bir token metni döner. 

- **3. Adım —** Alınan bu token, sonraki tüm isteklerin HTTP header bölümüne aşağıdaki formatta eklenir: 

Authorization: Bearer {token} 

**Önemli:** Token süresi dolduğunda ya da servislerden _401/403_ benzeri bir yetkisiz erişim yanıtı alındığında, Token Servisi'nden yeni bir token talep edilmelidir. Kullanıcı adı, şifre ve PIN bilgileri üçüncü kişilerle paylaşılmamalı, uygulama tarafında güvenli şekilde saklanmalıdır (ör. ortam değişkeni, şifrelenmiş konfigürasyon). 

### **3. Genel Kurallar ve Yanıt Formatı** 

Aşağıdaki kurallar, API'nin tamamı için geçerli genel prensipleri özetlemektedir. 

İstek Formatı Tüm istekler application/json (bazı metotlarda ayrıca text/json ve application/*+json) içerik tipiyle, HTTP POST veya GET metodu ile gönderilir. Kimlik Token Servisi hariç tüm servislerde Authorization: Bearer {token} header Doğrulama alanı zorunludur. Tarih Tarih/saat alanları ISO 8601 formatındadır (ör. 2026-07-22T09:15:00). Sadece Formatı tarih içeren alanlarda YYYY-MM-DD formatı kullanılır. İşlem Tipi Kayıt oluşturma/güncelleme/iptal işlemi yapan servislerde islemTipi alanı ile Alanı işlem yönü belirtilir: "i" = yeni kayıt (insert), "u" = güncelleme (update), "d" = iptal/silme (delete). Liste Toplu kayıt gönderilebilen servislerde (Sicil, İzin, Vardiya, Fazla Mesai, Gönderimi Fotoğraf) istek gövdesindeki data alanı bir dizi olup, birden fazla kayıt aynı anda gönderilebilir. Standart Servislerin büyük bölümü StringApiResponse yapısında yanıt döner: success Yanıt Zarfı (işlem sonucu), message (açıklama), correlationId (takip numarası), timestampUtc (yanıt zamanı) ve data (varsa dönen veri). Hata Kodları 400 Bad Request: İstek gövdesi hatalı veya eksik. 401/403: Token geçersiz veya süresi dolmuş. 500 Internal Server Error: Sunucu tarafında beklenmeyen bir hata oluşmuştur; correlationId değeri destek talebinde belirtilmelidir. 

**Öneri:** Tüm entegrasyon isteklerinde dönen correlationId değerinin loglanması, olası bir sorunda Meyer teknik destek ekibi ile hızlı iletişim kurulmasını sağlar. 

### **5. Token Servisi (Kimlik Doğrulama)** 

Diğer tüm servislere istek atabilmek için önce bu servisten bir erişim jetonu (token) alınması gerekir. Alınan token, sonraki tüm isteklerin header bölümüne eklenir. 

POST /API/TokenServisi/Token 

Tanımlanan kullanıcı bilgileri ile token üretmek için kullanılır. Üretilen token diğer metot header alanlarına eklenerek istek atılır. 

İstek Gövdesi (Request Body) — RequestToken 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|username|Metin|Evet<br>(zorunlu)|Meyer tarafından tanımlanan entegrasyon<br>kullanıcı adı.|
|password|Metin|Evet<br>(zorunlu)|Kullanıcıya ait şifre.|
|pin|Sayı (Tam<br>Sayı)|Evet (Zorunl)|Kullanıcıya özel ek güvenlik PIN kodu.|



#### Örnek İstek (JSON) 

{ 

"username": "entegrasyon_kullanicisi", "password": "********", "pin": 1234 } 

#### Başarılı Yanıt (200 OK) — StringApiResponse 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|success|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|İsteğin başarılı olup olmadığı (true/false).|
|message|Metin|Hayır<br>(opsiyonel)|İşlem sonucuna dair açıklayıcı mesaj (hata<br>veya bilgi metni).|
|correlationId|Metin|Hayır<br>(opsiyonel)|İsteği izlemek için kullanılan benzersiz<br>referans numarası; destek taleplerinde<br>paylaşılması önerilir.|
|timestampUtc|Tarih/Saat (ISO<br>8601)|Evet<br>(zorunlu)|Yanıtın üretildiği UTC tarih/saat bilgisi.|
|data|Metin|Hayır<br>(opsiyonel)|Aşağıda açıklanan alt nesne listesini içeren<br>dizi alanı.|



#### Örnek Yanıt (JSON) 

{ 

"success": true, "message": "İşlem başarıyla tamamlandı.", "correlationId": "3f2c1a9e-7b4d-4e2a-9c3e-1a2b3c4d5e6f", "timestampUtc": "2026-07-22T10:30:00Z", "data": null } 

### **6. Sicil Servisi (Personel Kayıtları)** 

Personel (sicil) kayıtlarının Meyer sistemine aktarılması ve mevcut kayıtların sorgulanması için kullanılır. Genellikle İK/bordro sistemleri ile personel bilgisi senkronizasyonunda kullanılır. 

POST /API/SicilServisi/setSicil 

Meyer de bir sicil oluşturmak için kullanılır. 

İstek Gövdesi (Request Body) — RequestSicil 

Alan 

|Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|data|Liste|Evet|Aşağıda açıklanan alt nesne listesini içeren dizi|
||<DatumSicil>|(zorunlu)|alanı.|



#### ↳ **DatumSicil** nesnesinin alanları: 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|ad|Metin|Evet<br>(zorunlu)|Kişinin adı.|
|adres|Metin|Hayır<br>(opsiyonel)|Personelin ikamet adresi.|
|altFirma|Metin|Hayır<br>(opsiyonel)|Bağlı olduğu alt firma/şirket bilgisi.|
|bolum|Metin|Hayır<br>(opsiyonel)|Personelin çalıştığı bölüm.|
|cepTelefonu|Metin|Hayır<br>(opsiyonel)|Personelin cep telefonu numarası.|
|cikisTarih|Tarih<br>(YYYY-MM-<br>DD)|Evet<br>(zorunlu)|Personelin işten çıkış tarihi.|
|cinsiyet|Metin|Hayır<br>(opsiyonel)|Personelin cinsiyeti.|
|direktorluk|Metin|Hayır<br>(opsiyonel)|Personelin bağlı olduğu direktörlük bilgisi.|
|dogumTarihi|Tarih<br>(YYYY-MM-<br>DD)|Evet<br>(zorunlu)|Personelin doğum tarihi.|
|email|Metin|Hayır<br>(opsiyonel)|Personelin e-posta adresi.|
|firma|Metin|Hayır<br>(opsiyonel)|Personelin bağlı olduğu firma.|
|girisTarih|Tarih<br>(YYYY-MM-<br>DD)|Evet<br>(zorunlu)|Personelin işe giriş tarihi.|
|gorev|Metin|Hayır<br>(opsiyonel)|Personelin görevi/unvanı.|
|il|Metin|Hayır<br>(opsiyonel)|İkamet edilen il.|
|ilce|Metin|Hayır<br>(opsiyonel)|İkamet edilen ilçe.|
|kangrubu|Metin|Hayır|Personelin kan grubu bilgisi.|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|||(opsiyonel)||
|okod1|Metin|Hayır<br>(opsiyonel)|Firmaya özel 1. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod2|Metin|Hayır<br>(opsiyonel)|Firmaya özel 2. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod3|Metin|Hayır<br>(opsiyonel)|Firmaya özel 3. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod4|Metin|Hayır<br>(opsiyonel)|Firmaya özel 4. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod5|Metin|Hayır<br>(opsiyonel)|Firmaya özel 5. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod6|Metin|Hayır<br>(opsiyonel)|Firmaya özel 6. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod7|Metin|Hayır<br>(opsiyonel)|Firmaya özel 7. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod8|Metin|Hayır<br>(opsiyonel)|Firmaya özel 8. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod9|Metin|Hayır<br>(opsiyonel)|Firmaya özel 9. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod10|Metin|Hayır<br>(opsiyonel)|Firmaya özel 10. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod11|Metin|Hayır<br>(opsiyonel)|Firmaya özel 11. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod12|Metin|Hayır<br>(opsiyonel)|Firmaya özel 12. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod13|Metin|Hayır<br>(opsiyonel)|Firmaya özel 13. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod14|Metin|Hayır<br>(opsiyonel)|Firmaya özel 14. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod15|Metin|Hayır<br>(opsiyonel)|Firmaya özel 15. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod17|Metin|Hayır<br>(opsiyonel)|Firmaya özel 17. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod18|Metin|Hayır<br>(opsiyonel)|Firmaya özel 18. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod19|Metin|Hayır<br>(opsiyonel)|Firmaya özel 19. serbest tanım (opsiyonel<br>kodlama) alanı.|
|okod20|Metin|Hayır<br>(opsiyonel)|Firmaya özel 20. serbest tanım (opsiyonel<br>kodlama) alanı.|
|personelNo|Metin|Hayır|Firmaya özel personel numarası (varsa sicil|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|||(opsiyonel)|numarasından farklı olabilir).|
|pozisyon|Metin|Hayır<br>(opsiyonel)|Personelin pozisyon bilgisi.|
|sicilNo|Metin|Evet<br>(zorunlu)|Personelin Meyer sistemindeki sicil numarası.|
|soyad|Metin|Evet<br>(zorunlu)|Kişinin soyadı.|
|yaka|Metin|Hayır<br>(opsiyonel)|Personelin çalıştığı yaka/lokasyon bilgisi (ör.<br>Avrupa/Anadolu yakası gibi kullanıma özel<br>alan).|
|telefon|Metin|Hayır<br>(opsiyonel)|Personelin sabit/diğer telefon numarası.|



#### Örnek İstek (JSON) 

{ "data": [ { "ad": "Ahmet", "adres": "Örnek Mah. Örnek Cad. No:1 Kadıköy/İstanbul", "altFirma": "Meyer Alt Firma A.Ş.", "bolum": "Bilgi İşlem", "cepTelefonu": "05551234567", "cikisTarih": null, "cinsiyet": "E", "direktorluk": "Operasyon Direktörlüğü", "dogumTarihi": "1990-05-12", "email": "ahmet.yilmaz@ornekfirma.com", "firma": "Örnek Firma A.Ş.", "girisTarih": "2022-03-01", "gorev": "Yazılım Uzmanı", "il": "İstanbul", "ilce": "Kadıköy", "kangrubu": "0 Rh+", "okod1": null, "okod2": null, "okod3": null, "okod4": null, "okod5": null, "okod6": null, "okod7": null, "okod8": null, 

"okod9": null, "okod10": null, "okod11": null, "okod12": null, "okod13": null, "okod14": null, "okod15": null, "okod17": null, "okod18": null, "okod19": null, "okod20": null, "personelNo": "P-4521", "pozisyon": "Uzman", "sicilNo": "10045", "soyad": "Yılmaz", "yaka": "Anadolu", "telefon": "02161234567" } ] } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

POST /API/SicilServisi/getSicil 

Meyerde bulunan sicil bilgilerini getirir. 

İstek Gövdesi (Request Body) — RequestSicilGet 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır<br>(opsiyonel)|Personelin Meyer sistemindeki sicil numarası.|
|firma|Metin|Hayır<br>(opsiyonel)|Personelin bağlı olduğu firma.|
|altFirma|Metin|Hayır<br>(opsiyonel)|Bağlı olduğu alt firma/şirket bilgisi.|
|pozisyon|Metin|Hayır<br>(opsiyonel)|Personelin pozisyon bilgisi.|
|gorev|Metin|Hayır<br>(opsiyonel)|Personelin görevi/unvanı.|
|bolum|Metin|Hayır<br>(opsiyonel)|Personelin çalıştığı bölüm.|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|direktorluk|Metin|Hayır<br>(opsiyonel)|Personelin bağlı olduğu direktörlük bilgisi.|
|yaka|Metin|Hayır<br>(opsiyonel)|Personelin çalıştığı yaka/lokasyon bilgisi (ör.<br>Avrupa/Anadolu yakası gibi kullanıma özel alan).|
|durum|Sayı<br>(Tam<br>Sayı)|Evet<br>(zorunlu)|Kayıt durumu (aktif:1,pasif:2,hepsi:0).|



Örnek İstek (JSON) 

{ "sicilNo": "10045", "firma": "Örnek Firma A.Ş.", "altFirma": "Meyer Alt Firma A.Ş.", "pozisyon": "Uzman", "gorev": "Yazılım Uzmanı", "bolum": "Bilgi İşlem", "direktorluk": "Operasyon Direktörlüğü", "yaka": "Anadolu", "durum": 1 } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **7. İzin Servisi** 

Personel izin taleplerinin oluşturulması, güncellenmesi, iptal edilmesi ve mevcut izin kayıtlarının sorgulanması için kullanılır. 

POST /API/IzinServisi/setIzinTalepleri_IzinBolme 

Küsüratlı(2 gün 2 saat gibi) gelen izinleri böler ve Meyer yapısına uygun bir şekilde talep oluşturur, günceller ve pasife alır. 

İstek Gövdesi (Request Body) — RequestIzin 

|Alan||||
|---|---|---|---|
|Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|data|Liste|Evet|Aşağıda açıklanan alt nesne listesini içeren dizi|
||<DatumIzin>|(zorunlu)|alanı.|



↳ **DatumIzin** nesnesinin alanları: 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|formID|Metin|Evet<br>(zorunlu)|İlgili form/talep için benzersiz kayıt kimliği<br>(form referans numarası).|
|islemTipi|Metin|Evet<br>(zorunlu)|"i" (yeni kayıt/insert), "u"<br>(güncelleme/update) veya "d" (iptal/silme-<br>delete) değerlerinden biri.|
|sicilNo|Metin|Evet<br>(zorunlu)|Personelin Meyer sistemindeki sicil<br>numarası.|
|izinAciklamasi|Metin|Hayır<br>(opsiyonel)|İzin talebine ait açıklama metni.|
|baslangicTarihi|Tarih/Saat<br>(ISO 8601)|Evet<br>(zorunlu)|Talebin/hareketin başlangıç tarih ve saati.|
|bitisTarihi|Tarih/Saat<br>(ISO 8601)|Evet<br>(zorunlu)|Talebin/hareketin bitiş tarih ve saati.|
|islemTarihi|Tarih/Saat<br>(ISO 8601)|Evet<br>(zorunlu)|Talebin oluşturulduğu/işlendiği tarih ve<br>saat.|
|isBasiTarihiMi|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|Belirtilen tarihin iş başı (göreve dönüş)<br>tarihi olup olmadığı.|
|saatlikMi|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|İznin saatlik izin olarak mı<br>değerlendirileceği.|
|ucretliMi|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|İznin ücretli izin olup olmadığı.|
|yillikIzinMi|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|İznin yıllık izin kapsamında olup olmadığı.|
|izinTipiKodu|Metin|Evet<br>(zorunlu)|Meyer sisteminde tanımlı izin tipi kodu<br>(getIzinTipleri ile listelenebilir).|
|izinTipiAdi|Metin|Evet<br>(zorunlu)|İzin tipinin okunabilir adı (ör. "Yıllık İzin",<br>"Mazeret İzni").|



#### Örnek İstek (JSON) 

{ "data": [ { "formID": "F-000123", "islemTipi": "i", "sicilNo": "10045", "izinAciklamasi": "Yıllık izin talebi", "baslangicTarihi": "2026-07-22T18:00:00", "bitisTarihi": "2026-07-22T22:00:00", "islemTarihi": "2026-07-22T09:15:00", "isBasiTarihiMi": false, "saatlikMi": false, 

"ucretliMi": true, 

"yillikIzinMi": true, 

"izinTipiKodu": "01", "izinTipiAdi": "Yıllık İzin" 

} ] } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

POST /API/IzinServisi/setIzinTalepleri 

Yeni izin talebi oluşturur günceller ve iptal eder. İptal için işlem tipi "d", yeni bir talep için işlem tipi "i" güncellenen talep için işlem tipi "u" gönderilmelidir. 

İstek Gövdesi (Request Body) — RequestIzin 

#### Alan 

|Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|data|Liste|Evet|Aşağıda açıklanan alt nesne listesini içeren dizi|
||<DatumIzin>|(zorunlu)|alanı.|



↳ **DatumIzin** nesnesinin alanları: 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|formID|Metin|Evet<br>(zorunlu)|İlgili form/talep için benzersiz kayıt kimliği<br>(form referans numarası).|
|islemTipi|Metin|Evet<br>(zorunlu)|"i" (yeni kayıt/insert), "u"<br>(güncelleme/update) veya "d" (iptal/silme-<br>delete) değerlerinden biri.|
|sicilNo|Metin|Evet<br>(zorunlu)|Personelin Meyer sistemindeki sicil<br>numarası.|
|izinAciklamasi|Metin|Hayır<br>(opsiyonel)|İzin talebine ait açıklama metni.|
|baslangicTarihi|Tarih/Saat<br>(ISO 8601)|Evet<br>(zorunlu)|Talebin/hareketin başlangıç tarih ve saati.|
|bitisTarihi|Tarih/Saat<br>(ISO 8601)|Evet<br>(zorunlu)|Talebin/hareketin bitiş tarih ve saati.|
|islemTarihi|Tarih/Saat<br>(ISO 8601)|Evet<br>(zorunlu)|Talebin oluşturulduğu/işlendiği tarih ve<br>saat.|
|isBasiTarihiMi|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|Belirtilen tarihin iş başı (göreve dönüş)<br>tarihi olup olmadığı.|
|saatlikMi|Mantıksal|Evet|İznin saatlik izin olarak mı|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
||(true/false)|(zorunlu)|değerlendirileceği.|
|ucretliMi|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|İznin ücretli izin olup olmadığı.|
|yillikIzinMi|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|İznin yıllık izin kapsamında olup olmadığı.|
|izinTipiKodu|Metin|Evet<br>(zorunlu)|Meyer sisteminde tanımlı izin tipi kodu<br>(getIzinTipleri ile listelenebilir).|
|izinTipiAdi|Metin|Evet<br>(zorunlu)|İzin tipinin okunabilir adı (ör. "Yıllık İzin",<br>"Mazeret İzni").|



Örnek İstek (JSON) 

{ "data": [ { "formID": "F-000123", "islemTipi": "i", "sicilNo": "10045", "izinAciklamasi": "Yıllık izin talebi", "baslangicTarihi": "2026-07-22T18:00:00", "bitisTarihi": "2026-07-22T22:00:00", "islemTarihi": "2026-07-22T09:15:00", "isBasiTarihiMi": false, "saatlikMi": false, "ucretliMi": true, "yillikIzinMi": true, "izinTipiKodu": "01", "izinTipiAdi": "Yıllık İzin" } ] } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

POST /API/IzinServisi/getIzinTalepleri 

Meyer de bulunan izin taleplerini başlangıç ve bitiş tarihi olacak şekilde blok halinde getirir. İstek Gövdesi (Request Body) — RequestIzinTalepGet 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır|Personelin Meyer sistemindeki sicil|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|||(opsiyonel)|numarası.|
|firma|Metin|Hayır<br>(opsiyonel)|Personelin bağlı olduğu firma.|
|altFirma|Metin|Hayır<br>(opsiyonel)|Bağlı olduğu alt firma/şirket bilgisi.|
|pozisyon|Metin|Hayır<br>(opsiyonel)|Personelin pozisyon bilgisi.|
|gorev|Metin|Hayır<br>(opsiyonel)|Personelin görevi/unvanı.|
|bolum|Metin|Hayır<br>(opsiyonel)|Personelin çalıştığı bölüm.|
|direktorluk|Metin|Hayır<br>(opsiyonel)|Personelin bağlı olduğu direktörlük bilgisi.|
|yaka|Metin|Hayır<br>(opsiyonel)|Personelin çalıştığı yaka/lokasyon bilgisi (ör.<br>Avrupa/Anadolu yakası gibi kullanıma özel<br>alan).|
|baslangicTarih|Tarih/Saat<br>(ISO 8601)|Hayır<br>(opsiyonel)|Talebin başlangıç tarihi.|
|talepTarih|Tarih/Saat<br>(ISO 8601)|Hayır<br>(opsiyonel)|İznin talep edildiği tarih.|
|onayTarih|Tarih/Saat<br>(ISO 8601)|Hayır<br>(opsiyonel)|İznin onaylandığı/reddedildiği tarih.|
|durum|Sayı (Tam<br>Sayı)|Evet<br>(zorunlu)|Onay durumu ya da kayıt durumu<br>(aktif:1,pasif:2,hepsi:0).|



#### Örnek İstek (JSON) 

{ "sicilNo": "10045", "firma": "Örnek Firma A.Ş.", "altFirma": "Meyer Alt Firma A.Ş.", "pozisyon": "Uzman", "gorev": "Yazılım Uzmanı", "bolum": "Bilgi İşlem", "direktorluk": "Operasyon Direktörlüğü", "yaka": "Anadolu", "baslangicTarih": "2026-07-20T09:00:00", "talepTarih": "2026-07-19T14:22:00", "onayTarih": "2026-07-20T08:00:00", "durum": true } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

#### POST /API/IzinServisi/getIzin 

Meyerde bulunan izinleri her gün bir satır olacak şekilde getirir. 

İstek Gövdesi (Request Body) — RequestIzinGet 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır<br>(opsiyonel)|Personelin Meyer sistemindeki sicil numarası.|
|bastarih|Tarih/Saat (ISO<br>8601)|Evet<br>(zorunlu)|Sorgulanacak tarih aralığının başlangıcı.|
|bittarih|Tarih/Saat (ISO<br>8601)|Evet<br>(zorunlu)|Sorgulanacak tarih aralığının bitişi.|
|yaka|Metin|Hayır<br>(opsiyonel)|Personelin çalıştığı yaka/lokasyon bilgisi (ör.<br>Avrupa/Anadolu yakası gibi kullanıma özel alan).|



Örnek İstek (JSON) 

{ 

"sicilNo": "10045", "bastarih": "2026-07-01T00:00:00", "bittarih": "2026-07-22T23:59:59", "yaka": "Anadolu" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

GET /API/IzinServisi/getIzinTipleri 

İzin tiplerini getirir. 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **8. İzin Onay Servisi** 

Meyer sisteminde bekleyen izin taleplerinin onaylanması veya reddedilmesi için kullanılır. POST /API/IzinOnayServisi/IzinOnay 

Bekleyen izin talebini onaylamak veya reddetmek için kullanılır. 

İstek Gövdesi (Request Body) — IzinOnayRequest 

|Alan<br>Adı|Veri Tipi|Zorunlu<br>mu?|Açıklama|
|---|---|---|---|
|izinId|Sayı (Tam Sayı)|Evet<br>(zorunlu)|Onaylanacak/reddedilecek izin talebinin kimlik<br>numarası (ID).|
|durum|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|Onay durumu ya da kayıt durumu (bağlama göre:<br>true/false ya da durum kodu).|
|Örnek İs|tek (JSON)|||



{ "izinId": 3456, "durum": true } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **9. Fazla Mesai Servisi** 

Personel fazla mesai taleplerinin oluşturulması, güncellenmesi ve iptal edilmesi için kullanılır. 

POST /API/FazlaMesaiServisi/setFMTalepleri 

Yeni mesai talebi oluşturur günceller ve iptal eder. İptal için işlem tipi "d", yeni bir talep için işlem tipi "i" güncellenen talep için işlem tipi "u" gönderilmelidir. 

İstek Gövdesi (Request Body) — FazlaMesaiRequest 

|Alan<br>Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|data|Liste <DatumFM>|Evet<br>(zorunlu)|Aşağıda açıklanan alt nesne listesini içeren<br>dizi alanı.|
|date|Tarih/Saat (ISO<br>8601)|Evet<br>(zorunlu)|İlgili talep grubunun tarihi.|
|↳**Datum**|**FM**nesnesinin alanla|rı:||
|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|formID|Metin|Hayır<br>(opsiyonel)|İlgili form/talep için benzersiz kayıt kimliği<br>(form referans numarası).|
|islemTipi|Metin|Evet<br>(zorunlu)|"i" (yeni kayıt/insert), "u"<br>(güncelleme/update) veya "d" (iptal/silme-|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
||||delete) değerlerinden biri.|
|sicilNo|Metin|Evet<br>(zorunlu)|Personelin Meyer sistemindeki sicil<br>numarası.|
|fmAciklama|Metin|Hayır<br>(opsiyonel)|Fazla mesai talebine ait açıklama metni.|
|baslangicTarihi|Tarih/Saat<br>(ISO 8601)|Evet<br>(zorunlu)|Talebin/hareketin başlangıç tarih ve saati.|
|bitisTarihi|Tarih/Saat<br>(ISO 8601)|Evet<br>(zorunlu)|Talebin/hareketin bitiş tarih ve saati.|
|islemTarihi|Tarih/Saat<br>(ISO 8601)|Hayır<br>(opsiyonel)|Talebin oluşturulduğu/işlendiği tarih ve<br>saat.|
|yemek|Sayı (Tam<br>Sayı)|Hayır<br>(opsiyonel)|Fazla mesai kapsamında yemek hakkı olup<br>olmadığını belirtir (0/1).|
|ulasim|Sayı (Tam<br>Sayı)|Hayır<br>(opsiyonel)|Fazla mesai kapsamında ulaşım hakkı olup<br>olmadığını belirtir (0/1).|
|fmNedenKodu|Metin|Evet<br>(zorunlu)|Fazla mesai gerekçe/neden kodu.|



Örnek İstek (JSON) 

{ "data": [ { "formID": "F-000123", "islemTipi": "i", "sicilNo": "10045", "fmAciklama": "Proje teslim tarihi nedeniyle fazla mesai", "baslangicTarihi": "2026-07-22T18:00:00", "bitisTarihi": "2026-07-22T22:00:00", "islemTarihi": "2026-07-22T09:15:00", "yemek": 1, "ulasim": 1, "fmNedenKodu": "01" } ], "date": "2026-07-22T00:00:00" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **10. Hareket Servisi (Giriş-Çıkış Kayıtları)** 

Personelin turnike, kart okuyucu, parmak izi veya yüz tanıma terminallerinden yaptığı geçiş hareketlerinin sorgulanması için kullanılır. Puantaj ve devam-devamsızlık hesaplamalarında sıklıkla kullanılır. 

POST /API/HareketServisi/GetHareket 

Personellere ait kart,parmak ve yüz okutma hareketlerini getirir. Tarih verisi zorunlu olarak girilmelidir. SicilNo alanı boş gönderildiğinde verilen tarih aralığındaki bütün veriyi getirecektir. 

İstek Gövdesi (Request Body) — RequestHareket 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır<br>(opsiyonel)|Personelin Meyer sistemindeki sicil<br>numarası.|
|baslangic|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için başlangıç tarih ve saati.|
|bitis|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için bitiş tarih ve saati.|



Örnek İstek (JSON) 

{ "sicilNo": "10045", "baslangic": "2026-07-01T00:00:00", "bitis": "2026-07-22T23:59:59" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

POST /API/HareketServisi/getHareketFirstInLastOut 

Personellere ait puantaja dahil olan ilk giriş ve son çıkış kart/parmak/yüz okutma hareketlerini getirecektir.Tarih verisi zorunlu olarak girilmelidir. SicilNo alanı boş gönderildiğinde verilen tarih aralığındaki bütün veriyi getirecektir. 

İstek Gövdesi (Request Body) — RequestHareket 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır<br>(opsiyonel)|Personelin Meyer sistemindeki sicil<br>numarası.|
|baslangic|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için başlangıç tarih ve saati.|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|bitis|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için bitiş tarih ve saati.|



Örnek İstek (JSON) 

{ "sicilNo": "10045", "baslangic": "2026-07-01T00:00:00", "bitis": "2026-07-22T23:59:59" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

POST /API/HareketServisi/getHareketOneTime 

Personellere ait kart, parmak izi veya yüz okutma hareket (geçiş) kayıtlarını getirir.Önemli Not: Bu metot, okunan bir hareketi yalnızca bir kez döndürecek şekilde tasarlanmıştır. Aynı parametrelerle tekrar istek atıldığında daha önce dönülmüş olan hareket bilgileri tekrar gelmez. Önceden çekilmiş verileri yeniden alabilmek için öncelikle getHareketReset metodu kullanılarak hareket verisi sıfırlanmalıdır. Sıfırlama işleminin ardından ilgili hareketler tekrar çekilebilir. 

İstek Gövdesi (Request Body) — RequestHareket 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır<br>(opsiyonel)|Personelin Meyer sistemindeki sicil<br>numarası.|
|baslangic|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için başlangıç tarih ve saati.|
|bitis|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için bitiş tarih ve saati.|



Örnek İstek (JSON) 

{ "sicilNo": "10045", "baslangic": "2026-07-01T00:00:00", "bitis": "2026-07-22T23:59:59" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

POST /API/HareketServisi/getHareketID 

Hareket ID sine göre hareket verilerini getirir. Okunan ID tekrar çekilemez getHareketReset fonksiyonu ile resetlenmelidir. 

İstek Gövdesi (Request Body) — RequestHareketID 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır (opsiyonel)|Personelin Meyer sistemindeki sicil numarası.|
|id|Sayı (Tam Sayı)|Evet (zorunlu)|İlgili kaydın benzersiz kimlik numarası (ID).|



Örnek İstek (JSON) 

{ "sicilNo": "10045", "id": 987654 } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

POST /API/HareketServisi/getHareketReset 

getHareketOneTime vegetHareketID metodları ile çekilen hareketleri resetlemek amacıyla kullanılır. 

İstek Gövdesi (Request Body) — RequestHareket 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır<br>(opsiyonel)|Personelin Meyer sistemindeki sicil<br>numarası.|
|baslangic|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için başlangıç tarih ve saati.|
|bitis|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için bitiş tarih ve saati.|



#### Örnek İstek (JSON) 

{ 

"sicilNo": "10045", "baslangic": "2026-07-01T00:00:00", "bitis": "2026-07-22T23:59:59" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **11. Vardiya Servisi** 

Personel vardiya/mesai planlarının oluşturulması ve mevcut vardiya bilgilerinin sorgulanması için kullanılır. 

POST /API/VardiyaServisi/setVardiya 

Verilen tarihe vardiya/shift planlamak için kullanılır. 

İstek Gövdesi (Request Body) — RequestVardiya 

|Alan||||
|---|---|---|---|
|Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|data|Liste|Evet|Aşağıda açıklanan alt nesne listesini içeren|
||<DatumVardiya>|(zorunlu)|dizi alanı.|



#### ↳ **DatumVardiya** nesnesinin alanları: 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Evet<br>(zorunlu)|Personelin Meyer sistemindeki sicil<br>numarası.|
|vardiyaKodu|Metin|Evet<br>(zorunlu)|Meyer sisteminde tanımlı vardiya/mesai<br>kodu.|
|tarih|Tarih (YYYY-MM-<br>DD)|Evet<br>(zorunlu)|Vardiyanın planlanacağı tarih.|



Örnek İstek (JSON) 

{ "data": [ { "sicilNo": "10045", "vardiyaKodu": "V01", "tarih": "2026-07-25" } ] } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

GET /API/VardiyaServisi/getVardiya 

Tanımlı mesai bilgilerini getirir. 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

POST /API/VardiyaServisi/getPersonelMesai 

Personellerin planlı vardiya bilgilerini getirir. 

İstek Gövdesi (Request Body) — RequestPuantaj 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır<br>(opsiyonel)|Personelin Meyer sistemindeki sicil<br>numarası.|
|baslangic|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için başlangıç tarih ve saati.|
|bitis|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için bitiş tarih ve saati.|



Örnek İstek (JSON) 

{ "sicilNo": "10045", "baslangic": "2026-07-01T00:00:00", "bitis": "2026-07-22T23:59:59" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **12. Puantaj Servisi** 

Firmaya özel geliştirilen puantaj raporlarına JSON formatında erişim sağlamak için kullanılır. 

POST /API/PuantajServisi/getPuantaj 

Firmanıza özel puantaj rapor geliştirmesi tamamlandığında getPuantaj metodunun kullanarak puantaj rapor verisine json formatta erişebilmek amacı ile kullanılır. Ayrıca özel bir rapor talebi var ise ilgili parametreler tanımlandığında yine getPuantaj metodunu kullanarak erişebilirsiniz. 

İstek Gövdesi (Request Body) — RequestPuantaj 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Hayır<br>(opsiyonel)|Personelin Meyer sistemindeki sicil<br>numarası.|
|baslangic|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için başlangıç tarih ve saati.|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|bitis|Tarih/Saat (ISO<br>8601)|Evet (zorunlu)|Sorgu için bitiş tarih ve saati.|



Örnek İstek (JSON) 

{ "sicilNo": "10045", "baslangic": "2026-07-01T00:00:00", "bitis": "2026-07-22T23:59:59" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **13. Geçiş Yetki Servisi** 

Personele, Meyer Angel üzerinde tanımlı geçiş gruplarının (terminal yetkilerinin) atanması için kullanılır. 

POST /API/GecisYetkiServisi/setGecisYetkisi 

Meyer Angel üzerinde oluşturulan terminal geçiş grubunu personel kartına ekler. Böylece personel geçiş yetkisi üzerinde tanımlı terminallerden okutma yaparak geçiş sağlayabilir. Geçiş grubu ID si ile çalışmaktadır. Birden fazla geçiş yetkisi verilecek ise ; ile eklenerek gönderilmelidir. 

İstek Gövdesi (Request Body) — YetkiRequest 

|Alan Adı|Veri<br>Tipi|Zorunlu<br>mu?|Açıklama|
|---|---|---|---|
|sicilNo|Metin|Evet<br>(zorunlu)|Personelin Meyer sistemindeki sicil numarası.|
|gecisYetki|Metin|Evet|Personele tanımlanacak geçiş grubu ID’si; birden fazla ise|
|||(zorunlu)|";" karakteri ile ayrılarak gönderilir.|



Örnek İstek (JSON) 

{ "sicilNo": "10045", "gecisYetki": "12;15" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **14. Kapı Açma Servisi** 

Meyer okutma cihazlarına bağlı kapılara uzaktan açma komutu göndermek için kullanılır. 

POST /API/KapiAcmaServisi/OpentheDoor 

Meyer okutma cihazları ile bağlı kapılarına kapı açma komutu gönderir. 

İstek Gövdesi (Request Body) — RequestKapiAcma 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|terminalName|Metin|Evet<br>(zorunlu)|Kapının bağlı olduğu terminal/cihaz adı.|
|controllerNo|Sayı (Tam Sayı)|Evet<br>(zorunlu)|Terminale bağlı kapı kontrolörü<br>numarası.|
|open|Mantıksal<br>(true/false)|Evet<br>(zorunlu)|true gönderildiğinde kapı açma komutu<br>tetiklenir.|



Örnek İstek (JSON) 

{ "terminalName": "Ana Giriş Kapısı", "controllerNo": 2, "open": true } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **15. Terminal Servisi** 

Sistemde tanımlı geçiş terminallerinin (turnike, kapı vb.) listelenmesi için kullanılır. 

POST /API/TerminalServisi/getTerminal 

Terminalleri getirir. 

İstek Gövdesi (Request Body) — RequestTerminal 

|Alan Adı|Veri<br>Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|terminalAd|Metin|Hayır<br>(opsiyonel)|Terminalin adı.|
|terminalPort|Metin|Hayır<br>(opsiyonel)|Terminalin bağlı olduğu port bilgisi.|
|terminalTuru|Metin|Hayır|Terminal türü (ör. kart okuyucu, parmak izi, yüz|



||Veri|||
|---|---|---|---|
|Alan Adı|Tipi|Zorunlu mu?|Açıklama|
|||(opsiyonel)|tanıma vb.).|



Örnek İstek (JSON) 

{ 

"terminalAd": "Ana Giriş Turnike", 

"terminalPort": "COM3", "terminalTuru": "Kart Okuyucu" } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **16. Fotoğraf Servisi** 

Personel sicil fotoğraflarının eklenmesi veya güncellenmesi için kullanılır. 

POST /API/FotografServisi/setSicilFotograf 

Sicil fotoğraf eklemek ya da güncellemek için kullanılır 

İstek Gövdesi (Request Body) — RequestSicilFoto 

|Alan||||
|---|---|---|---|
|Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|data|Liste <FotoRequest>|Evet|Aşağıda açıklanan alt nesne listesini içeren|
|||(zorunlu)|dizi alanı.|



- ↳ **FotoRequest** nesnesinin alanları: 

|Alan Adı|Veri<br>Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|fotoJGPtoBase64|Metin|Evet<br>(zorunlu)|Personel fotoğrafının Base64 formatında<br>kodlanmış hâli (JPEG).|
|sicilNo|Metin|Evet<br>(zorunlu)|Personelin Meyer sistemindeki sicil numarası.|



Örnek İstek (JSON) 

{ 

"data": [ 

{ 

"fotoJGPtoBase64": "/9j/4AAQSkZJRgABAQAAAQABAAD... (kısaltılmıştır)", "sicilNo": "10045" 

} ] } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **17. Ziyaretçi Servisi** 

Ziyaretçi kayıtlarının oluşturulması ile kimlik tipi, ziyaret nedeni ve sicil kartı gibi tanımlı liste değerlerinin sorgulanması için kullanılır. 

GET /API/ZiyaretciServisi/getKimlikTipiListesi 

_Bu metot için ek açıklama girilmemiştir._ 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

GET /API/ZiyaretciServisi/getZiyaretNedeniListesi 

_Bu metot için ek açıklama girilmemiştir._ 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

GET /API/ZiyaretciServisi/getSicilKartListesi 

_Bu metot için ek açıklama girilmemiştir._ 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

POST /API/ZiyaretciServisi/setZiyaretci 

_Bu metot için ek açıklama girilmemiştir._ 

İstek Gövdesi (Request Body) — ZiyaretciRequest 

|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|islemTipi|Metin|Evet|"i" (yeni kayıt/insert), "u"|
|||(zorunlu)|(güncelleme/update) veya "d" (iptal/silme-|
||||delete) değerlerinden biri.|
|id|Sayı (Tam|Hayır|İlgili kaydın benzersiz kimlik numarası (ID).|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
||Sayı)|(opsiyonel)||
|ad|Metin|Evet<br>(zorunlu)|Kişinin adı.|
|soyad|Metin|Evet<br>(zorunlu)|Kişinin soyadı.|
|bilgi|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye dair ek bilgi/not.|
|giris|Tarih/Saat<br>(ISO 8601)|Hayır<br>(opsiyonel)|Ziyaretçinin giriş tarih ve saati.|
|cikis|Tarih/Saat<br>(ISO 8601)|Hayır<br>(opsiyonel)|Ziyaretçinin çıkış tarih ve saati.|
|isgTarih|Tarih/Saat<br>(ISO 8601)|Hayır<br>(opsiyonel)|İSG (İş Sağlığı ve Güvenliği) bilgilendirmesinin<br>yapıldığı tarih.|
|gizlilikTarih|Tarih/Saat<br>(ISO 8601)|Hayır<br>(opsiyonel)|Gizlilik sözleşmesinin onaylandığı tarih.|
|plaka|Metin|Hayır<br>(opsiyonel)|Ziyaretçinin aracına ait plaka bilgisi.|
|arac|Metin|Hayır<br>(opsiyonel)|Ziyaretçinin araç bilgisi.|
|firma|Metin|Hayır<br>(opsiyonel)|Personelin bağlı olduğu firma.|
|kimlikTipi|Sayı (Tam<br>Sayı)|Evet<br>(zorunlu)|Kimlik tipi kodu (getKimlikTipiListesi ile<br>listelenebilir).|
|kimlikNo|Metin|Hayır<br>(opsiyonel)|Ziyaretçinin kimlik/pasaport numarası.|
|ziyaretTipi|Sayı (Tam<br>Sayı)|Evet<br>(zorunlu)|Ziyaret nedeni kodu (getZiyaretNedeniListesi<br>ile listelenebilir).|
|kimeGeldi|Metin|Evet<br>(zorunlu)|Ziyaretçinin görüşmeye geldiği personelin sicil<br>no/adı.|
|userId|Metin|Hayır<br>(opsiyonel)|Kaydı oluşturan/işleyen kullanıcının kimliği.|
|zoKod1|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 1. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod2|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 2. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod3|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 3. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod4|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 4. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod5|Metin|Hayır|Ziyaretçiye özel 5. serbest tanım (opsiyonel|



|Alan Adı|Veri Tipi|Zorunlu mu?|Açıklama|
|---|---|---|---|
|||(opsiyonel)|kodlama) alanı.|
|zoKod6|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 6. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod7|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 7. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod8|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 8. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod9|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 9. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod10|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 10. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod11|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 11. serbest tanım (opsiyonel<br>kodlama) alanı.|
|zoKod12|Metin|Hayır<br>(opsiyonel)|Ziyaretçiye özel 12. serbest tanım (opsiyonel<br>kodlama) alanı.|



Örnek İstek (JSON) 

{ "islemTipi": "i", "id": 987654, "ad": "Ahmet", "soyad": "Yılmaz", "bilgi": "Toplantı için ziyaret", "giris": "2026-07-22T09:00:00", "cikis": "2026-07-22T11:00:00", "isgTarih": "2026-07-22T08:55:00", "gizlilikTarih": "2026-07-22T08:56:00", "plaka": "34 AB 1234", "arac": "Binek Otomobil", "firma": "Örnek Firma A.Ş.", "kimlikTipi": 1, "kimlikNo": "12345678901", "ziyaretTipi": 2, "kimeGeldi": "10045", "userId": "entegrasyon_kullanicisi", "zoKod1": null, "zoKod2": null, "zoKod3": null, "zoKod4": null, "zoKod5": null, "zoKod6": null, 

"zoKod7": null, "zoKod8": null, "zoKod9": null, "zoKod10": null, "zoKod11": null, "zoKod12": null } 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

### **18. Doküman Servisi** 

API dokümantasyonunun servis üzerinden indirilmesi için kullanılır. 

GET /API/doc 

Api dokümantasyonu indirmek için kullanılır. 

Başarılı Yanıt (200 OK) 

Servis, isteğin işlenip işlenmediğine dair bir durum bilgisi döner. Dönüş içeriği bulunmamaktadır ya da servise özel bir gövde ile döner. 

