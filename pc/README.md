# PC amd64 · düşük RAM erken açılışı

Bu katman yalnızca `scripts/configure.py` içindeki **amd64 / trixie** yoluna
kopyalanır. Ortak `system/`, i386, Raspberry Pi ve diğer ARM tarifleri bu hook'u
almaz. Ürün özellikleri veya firmware paketleri çıkarılmaz.

## Neden dış initrd sıkıştırıcısını değiştirmek yetmez?

`3833b71` PC koşusu [45047556003](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45047556003),
512 MiB'de `gunzip → unpack_to_rootfs → do_populate_rootfs` içinde,
**kullanıcı alanı / zram başlamadan** `System is deadlocked on memory` ile durdu.
Aynı hedefin 2 GiB açılışı geçti; bu, 512 MiB başarısı değildir. Eski initrd
**160.643.364 bayt**: değer, aynı artefaktın salt-okunur
[rapor aktarma işinden](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45068204890)
geldi; ISO baytlarının bu sandbox'ta indirildiği iddia edilmez. Eski arşivin tüm
üye boyutları elde olmadığı için belirli tek dosya kesin kök neden ilan edilmez.

Dış gzip/xz/zstd seçimi arşivin açılmış dosya boyutunu azaltmaz. Genel Plymouth
GPU firmware'inin **yalnızca initramfs kopyasını**, çekirdeğin istek anında
çözebildiği `.xz` biçiminde tutmak erken rootfs yükünü azaltmayı hedefler.
Gerçek etki aşağıdaki yeni envanter ve 512/1024 MiB boot kapısıyla doğrulandı; sonuç yalnızca o kaynak içindir.

## Korunanlar ve güvenlik sınırı

- `/etc/initramfs-tools/hooks/oguzdows-firmware`, dağıtımın bütün hook'larından
  sonra çalışır. 0.148'in beklettiği modülleri `apply_add_modules` ile önce
  kopyalatır. **MODULES=dep / donanım budama yok**; varsayılan `most` korunur.
- Gerçek paketlenmekte olan çekirdeğin yapılandırmasında
  `CONFIG_FW_LOADER_COMPRESS=y` **ve** `CONFIG_FW_LOADER_COMPRESS_XZ=y`
  doğrulanmadan hiçbir firmware dönüştürülmez. Eksik destek rapora yazılır.
- Yalnızca `amdgpu`, `radeon`, `i915`, `xe`, `nvidia` dizinlerindeki uygun
  dosyalar; XZ + **CRC32**, LZMA2 **1 MiB sözlük**. Mikro kod, disk/ağ firmware'i,
  regulatory verisi, modüller, cryptroot ve Plymouth görsellerine dokunulmaz.
- Kurulu `/usr/lib/firmware` değişmez. İşlem, `/` kabul etmeyen geçici DESTDIR
  içindedir. Mutlak symlink arşiv köküne göre çözülür; dışarı kaçan / döngülü
  bağlantı reddedilir. Firmware alias zincirleri aynı içeriğe `.xz` fallback'i
  ile erişir. Önceden var olan `.xz` / `.zst` alternatifleri ve hardlink'ler
  ezilmez; küçük / faydasız sıkıştırma atlanır.
- Ham kopya kaldırılmadan sıkışık kopya açılarak **SHA-256 + bayt boyu**
  karşılaştırılır. Dosya modu / mtime korunur; bütün mantıksal adlar manifestte
  tutulur. Hata, yeni initrd'nin oluşturulmasını durdurur; sahte başarı yoktur.

## Her imajda kanıt

`etc/oguzdows/initramfs-firmware.json` **initrd içindedir**; gerçek kernel
config hash'i, önce/sonra dosya verisi, özgün payload SHA-256'ları ve alias'lar
kaydedilir. `scripts/initramfs-report.py` gerçek üretilen initrd'yi özel geçici
dizine açar; early/early2/main veya early katmanı olmayan düz çıktı ayrımını gözetir, paketlenmiş payload ve alias'ları
yeniden doğrular. Geç gelen bir hook ham firmware'i geri koyarsa test durur.
Arşiv boyutu/SHA-256, firmware/modül/diğer dosya baytları, büyük üyeler ve tam
manifest hedef-test artefaktına yazılır; küçük envanter kontrol notuna da çıkar.

Bu sayılar **tam RAM ayak izi değildir**: inode, sayfa yuvarlama, çekirdek,
çözme çalışma alanı ve sıkışık arşivin aynı anda RAM'de olması ayrıdır.
Asıl kapı, ISO'dan hazırlanan hedefin **512 ve 1024 MiB'de tam Xfce açılışı**,
120 sn yerleşme, altı örnek, OOM olmaması, 600 decimal MB tavanı ve en az
`max(32 MiB, MemTotal / 10)` kullanılabilir RAM'dir. 512 hatası 1024 testini
engellemez ama iki sonuçtan **herhangi bir hata işi başarısız** yapar. Erken
kernel panic görülünce masaüstü işareti için 600 sn beklenmez.

Birim testleri payload, alias, CRC32, sınır/çakışma, modül/microcode/cryptroot
korumasını denetler. İki tabanın host CI'ında gerçek `cpio → gzip →
unmkinitramfs` fixture turu da çalışır. Bunlar gerçek GPU firmware yükleme,
fiziksel PC/LUKS kurulumu veya Pi performans kanıtı değildir. İlk istek [45068861604](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45068861604),
host birim testinde durdu, ISO üretmedi. Kanıt okuyucusunun early katmanı yokken
`main/` varsayımı ayrıca düzeltildi; aynı durum için yerel regresyon eklendi.
Ürün firmware kodu değişmedi. Takip kaynağı `440cf743ccde4c76d79a5d87d8530cd0c1229552`,
ayrı imaj isteği [45069328093](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45069328093);
yeni 512/1024 MiB sonucu ayrıca kaydedilir.
Eski işler iptal / yeniden başlatma almaz; v1.0.0 değişmez.

## İncelenen sabit kaynaklar

- [initramfs-tools 0.148.4 `mkinitramfs`](https://github.com/pexip/os-initramfs-tools/blob/961911088a0ce1a83ce6785a2352bda06ffc2f2e/mkinitramfs):
  dağıtım hook'ları → yerel hook'lar → ertelenmiş modüller; `.xz/.zst` üyeler
  ayrı sıkıştırılmamış CPIO katmanında tutulur. Mirror'un değişebilen Pexip
  dalı değil, Debian etiketinin kaynağı incelendi; kod kopyalanmadı.
- [Aynı sürümün `hook-functions`](https://github.com/pexip/os-initramfs-tools/blob/961911088a0ce1a83ce6785a2352bda06ffc2f2e/hook-functions):
  `.xz` firmware keşfi ve modül kuyruğu.
- [Linux 6.12 firmware Kconfig](https://github.com/torvalds/linux/blob/v6.12/drivers/base/firmware_loader/Kconfig)
  ve [yükleyici](https://github.com/torvalds/linux/blob/v6.12/drivers/base/firmware_loader/main.c):
  `.xz` fallback, CRC32 gereği, istek anında sayfalı açma. Referans sürümdür;
  kullanılan gerçek çekirdeğin config'i ayrıca her derlemede denetlenir.

## Tamamlanan yeni imaj sonucu · `440cf74`

[45069328093](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45069328093)
**başarılı tamamlandı**. amd64 ve i386 ISO'larının gerçek hedef OS / tam Xfce
512 ve 1024 MiB kapıları geçti. amd64: 512/1024/2048 MiB medyan **269,7 /
454,9 / 479,2 MB**; i386 **197,5 / 417,8 / 494,7 MB** (decimal MB, boşta VM).
Bu bir fiziksel Pi veya açık uygulama performans ölçümü değildir.

Gerçek amd64 initrd: **152.275.913 bayt**, SHA-256
`fb124fe64ddfdac00d88e8326d665a65c3b72db28aa5edf76524c83bd3fe7b52`.
**710 payload dönüştürüldü ve doğrulandı; 211 alias korundu; açılmış dosya
verisinde 93.426.608 bayt azalma** kaydedildi. Kurulu firmware / sürücü ve ürün
özellikleri çıkarılmadı. [Tam kayıt](../docs/releases/v1.1-development-images.json).
Bu sonuç `440cf74` kaynağına aittir; sonraki Pi oturum / yeni görünüm değişiklikleri
bu imajlarda varmış gibi gösterilmez. Önceki çalışmalar tekrar başlatılmadı.
