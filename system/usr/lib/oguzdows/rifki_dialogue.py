"""Hafif rehber panellerinin hazır doğal seslere eşlenen Türkçe açıklamaları."""
from rifki_narration_texts import TEXTS

HELLO = 'Merhaba, ben Rıfkı. Artık daha hafifim. Kurulumu yavaşlatmamak için sakin duracağım. Disk, açılış, internet ve sürücüler hakkında yardımcı olabilirim. Sesim önceden hazırlanmış doğal Türkçe kayıtlardan geliyor.'
LIGHT_NOTE = 'Bilgisayarı yormamak için pencereye zıplama, oyuncak ve çay hareketlerini kaldırdım. Küçük resmim ve temel yardımım kaldı. İstersen yalnızca konuşurken çok hafif ağız hareketini açabilirsin. Kurulumda o da durur.'
PANELS = {
    'welcome': TEXTS['installed'],
    'hardware': 'Donanım ve sürücüler paneli. Raporu yenileyebilir, kendi seçtiğin bir dosyaya kaydedebilir veya ağ bağlantılarını açabilirsin. Ek Broadcom ve eski Intel paketleri yalnızca eşleşen kartta, lisans ve yönetici onayıyla kurulur. Gri düğme eksik sistem değil, o pakete uygun kart bulunmadığı anlamına gelir. Rapor hiçbir yere gönderilmez.',
    'wallpapers': TEXTS['wallpapers'],
    'styles': TEXTS['appearance'],
    'appearance': TEXTS['appearance'],
    'applications': TEXTS['applications'],
    'support': TEXTS['support'],
    'settings': 'Rıfkı artık hafif modda. Doğal Türkçe ses kayıtlarını açabilir, son mesajı tekrar dinleyebilir veya sesi hemen durdurabilirsin. Hafif ağız hareketi varsayılan olarak kapalıdır ve yalnızca ses çalarken çalışır. Kuruluma geçildiğinde hareket ve otomatik konuşma durur. Robotik ses sentezi kullanılmaz.',
}
STAGES = {
    'preparing': ('Kurucu hazırlanıyor', 'Canlı sistem ve kurulum kaynağı kontrol ediliyor. Diskine henüz yazıldığını varsayma.'),
    'ready': ('Seçimlerini kontrol et', 'Dil, klavye, disk ve kullanıcı bilgilerini kurucuda seç. Son özeti sen onaylayacaksın.'),
    'partition': ('Disk işlemleri başladı', 'Onayladığın bölüm düzeni uygulanıyor. Bilgisayarı kapatma.'),
    'copying': ('Dosyalar yerleşiyor', 'Dosyalar kopyalanıyor. Yüzde ve gerçek ilerleme kurucu ekranında; tahminî bir ilerleme göstermiyorum.'),
    'bootloader': ('Disk açılışı hazırlanıyor', 'Önyükleyici ve başlangıç dosyaları hazırlanıyor. Bu adım bitmeden başarı bildirmeyeceğim.'),
    'complete': ('Kurulum tamamlandı', 'Bütün kurulum işleri tamamlandı. Sonuç ekranını incele; diskten ilk açılış ayrıca denenmelidir.'),
}
