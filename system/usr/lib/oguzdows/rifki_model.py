"""Rıfkı'nın çevrimdışı, sınırlı ve eylemleri açık onaylı kurulum rehberi."""
import unicodedata

from install_status import description
from rifki_dialogue import LIGHT_NOTE, STAGES
from rifki_narration_texts import TEXTS


def normalize(text):
    return ''.join(char for char in unicodedata.normalize('NFKD', text.lower().replace('ı', 'i')) if not unicodedata.combining(char))[:2000]


def reply(text, status=None):
    query = normalize(text)
    answer = {'text': '', 'clip': None, 'action': None, 'emotion': 'listening'}
    if any(word in query for word in ('sudo ', 'mkfs', 'grub-install', 'rm -', '/dev/')):
        answer.update(text='Yazdığın komutu çalıştırmam. Yanlış diske yazmak verilerini silebilir. Önce salt-okunur açılış raporunu alalım.', action='boot-report')
    elif any(word in query for word in ('apk', '.exe', 'wine', 'waydroid', 'uyumluluk')):
        answer.update(text=TEXTS['compatibility'], action='compatibility')
    elif any(word in query for word in ('imece', 'heybe', 'yedek', 'hizli yazim', 'cay molasi')):
        answer.update(text=TEXTS['culture'], action='culture')
    elif any(word in query for word in ('magaza', 'flathub', 'flatpak', 'uygulama')):
        answer.update(text=TEXTS['store'], action='store')
    elif any(word in query for word in ('tema', 'koyu', 'tasarim', 'tarz', 'baslat menusu')):
        answer.update(text=TEXTS['appearance'], action='styles')
    elif any(word in query for word in ('guncelle', 'paket plani')):
        answer.update(text=TEXTS['applications'], action='updates')
    elif any(word in query for word in ('raspberry', 'pinephone', 'telefon', 'arm64', 'cihaz merkezi')):
        answer.update(text=TEXTS['compatibility'], action='devices')
    elif any(word in query for word in ('zipla','kuyru','tuy','cay','oyna')):
        answer.update(text=LIGHT_NOTE)
    elif any(word in query for word in ('boot', 'grub', 'bios', 'uefi', 'acilm', 'acilis', 'baslamiyor')):
        answer.update(text='Bu hata masaüstünden önceyse önce firmware, disk ve GRUB yolunu kontrol ederiz. Fotoğraf tek başına nedeni kanıtlamaz. Aşağıdaki rapor diskleri ve şu anki açılış kipini yalnızca okur; onarım yapmaz.', action='boot-report')
    elif any(word in query for word in ('sonuc', 'bitti', 'basari', 'hata', 'tamamlan', 'yarim')):
        if (status or {}).get('outcome') in ('preparing','ready','running'):
            title,detail=STAGES.get(status.get('stage'),('Kurulum sürüyor','Kesin sonuç henüz oluşmadı. Gerçek ilerlemeyi kurucudan izle.'))
            answer.update(text=title+'\n'+detail)
            return answer
        title, detail = description(status or {'outcome': 'unknown'})
        good = (status or {}).get('complete') is True and (status or {}).get('outcome') == 'success'
        answer.update(text=title + '\n' + detail, result=True, clip='success' if good else 'failure', emotion='happy' if good else 'concerned')
    elif any(word in query for word in ('disk', 'bolum', 'format', 'silme')):
        answer.update(text='Hedefi disk modeli ve kapasitesiyle doğrula. Diski sil o diskin verilerini siler. BIOS kurulumunda GRUB hedefi diskin tamamıdır; UEFI kurulumunda FAT EFI sistem bölümü gerekir. Yedek almadan ilerleme; ben disk seçmem veya biçimlendirmem.', clip='disk', emotion='concerned')
    elif any(word in query for word in ('internet', 'wifi', 'wi-fi', 'baglan', 'kablosuz', 'ag bag')):
        answer.update(text='Temel kurulum internet olmadan yapılabilir. Wi-Fi için önce uçak modunu ve donanım anahtarını kontrol et. Ağ bağlantılarını açabilirim; ağ parolanı sohbete yazma.', action='network')
    elif any(word in query for word in ('surucu', 'driver', 'ekran', 'ses', 'donanim')):
        answer.update(text='Önce donanımın hangi sürücüye bağlandığını okuyalım. Donanım sekmesi algılanan kartları gösterir; ek paketler yalnızca uygun kart ve açık lisans/yönetici onayıyla kurulur.', action='drivers')
    elif any(word in query for word in ('duvar', 'wallpaper', 'manzara')):
        answer.update(text=TEXTS['wallpapers'], action='wallpapers', emotion='happy')
    elif any(word in query for word in ('pil', 'sarj', 'nazar')):
        answer.update(text='Nazar boncuğu pil doldukça aşağıdan yukarı görünür. Tam dolunca bütünü görünür. Şimşek şarj olmayı, uyarı işareti düşük pili belirtir; güç yöneticisinin kritik pil koruması değişmez.')
    elif any(word in query for word in ('kur', 'yukle', 'install')):
        answer.update(text='Canlı USB’den OğuzDows’u kur düğmesini kullan. Dil, klavye, disk ve kullanıcı bilgilerini gözden geçir. Son özeti onaylamadan diske yazılmaz. Kurulum sırasında beni küçük pencere olarak yanında tutabilirsin.', action='install', clip='disk')
    else:
        answer.update(text='Ben Rıfkı: çevrimdışı Türkçe kurulum rehberin. Disk, açılış, kurulum sonucu, internet, sürücüler, pil ve duvar kâğıdı konularında yardımcı olurum. Genel amaçlı bir yapay zekâ sohbet servisi değilim; mikrofonunu dinlemem, mesajlarını göndermem.', clip='help')
    return answer
