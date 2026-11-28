export type Screen =
  | "home" | "apps" | "search" | "rifki" | "store" | "workbench"
  | "news" | "settings" | "google" | "culture" | "files" | "monitor"
  | "phone" | "messages" | "contacts" | "calendar" | "clock" | "media"
  | "browser" | "gallery" | "calculator" | "notes" | "tasks";
export type Contact = { id: string; name: string; number: string; favorite: boolean };
export type CalendarEntry = { id: string; date: string; title: string };
export type Preferences = {
  version: number; theme: "light" | "dark"; wallpaper: string; accent: "sea" | "copper" | "plum";
  lowPower: boolean; reducedMotion: boolean; wifi: boolean; bluetooth: boolean; airplane: boolean; focus: boolean;
  brightness: number; volume: number; muted: boolean; layout: "comfort" | "compact";
  tasks: { id: string; title: string; done: boolean }[];
  notes: string; snippets: string[]; wishlist: string[]; saved: string[]; read: string[];
  contacts: Contact[]; events: CalendarEntry[]; messageDraft: { number: string; body: string };
  timerEnd: number | null; stopwatch: { elapsed: number; startedAt: number | null };
};
export const WALLPAPER_NAMES: Record<string, string> = {
  bosphorus: "Boğaz sabahı", cappadocia: "Kapadokya ışığı", mountains: "Kaçkar sisi", "salt-lake": "Tuz Gölü akşamı",
};
export const apps: { id: Screen; name: string; icon: string; color: string; short: string; keywords?: string }[] = [
  {id:"store",name:"Mağaza",icon:"ShoppingBag",color:"mint",short:"Uygulamalar, kendi seçiminle.",keywords:"uygulama indir apk play"},
  {id:"workbench",name:"Atölye",icon:"Shapes",color:"orange",short:"Büyük fikirler, küçük araçlar."},
  {id:"news",name:"Haber",icon:"Newspaper",color:"blue",short:"Okumaya değer bir mola."},
  {id:"culture",name:"Koleksiyon",icon:"Image",color:"pink",short:"Biraz memleket, biraz sen.",keywords:"duvar kağıdı wallpaper"},
  {id:"files",name:"Dosyalar",icon:"FolderClosed",color:"sand",short:"Seçtiğin dosya sende kalır."},
  {id:"google",name:"Google",icon:"Globe2",color:"white",short:"Google, istediğin kadar."},
  {id:"monitor",name:"Cihazım",icon:"Activity",color:"lavender",short:"Kaynaklara saygılı bir telefon."},
  {id:"settings",name:"Ayarlar",icon:"Settings2",color:"gray",short:"En çok da sana benzesin.",keywords:"tema görünüm ses parlaklık"},
  {id:"rifki",name:"Rıfkı",icon:"Sparkles",color:"mint",short:"Birlikte düşünelim.",keywords:"asistan yapay zeka"},
  {id:"phone",name:"Telefon",icon:"Phone",color:"mint",short:"Bir ses kadar yakın.",keywords:"arama numara çevir dial"},
  {id:"messages",name:"Mesajlar",icon:"MessageCircle",color:"sand",short:"Bir mesajlık mesafe.",keywords:"sms mesaj yaz gönder"},
  {id:"contacts",name:"Kişiler",icon:"ContactRound",color:"blue",short:"Tanıdıkların, tek bir yerde.",keywords:"rehber kişi numara"},
  {id:"calendar",name:"Takvim",icon:"CalendarDays",color:"pink",short:"Günlerine biraz yer aç.",keywords:"etkinlik tarih ajanda"},
  {id:"clock",name:"Saat",icon:"Clock3",color:"lavender",short:"Bir an, bir mola.",keywords:"kronometre sayaç zamanlayıcı"},
  {id:"media",name:"Müzik",icon:"Music2",color:"orange",short:"Kendi müziğin, kendi ritmin.",keywords:"medya ses mp3 oynatıcı"},
  {id:"browser",name:"Tarayıcı",icon:"Globe2",color:"blue",short:"Yeni bir pencere aç.",keywords:"web internet ara"},
  {id:"gallery",name:"Galeri",icon:"Camera",color:"pink",short:"Güzel anlarına bir bak.",keywords:"fotoğraf kamera resim"},
  {id:"calculator",name:"Hesap",icon:"Calculator",color:"sand",short:"Sayılar, sadeleşsin.",keywords:"hesap makinesi matematik"},
  {id:"notes",name:"Defter",icon:"NotebookPen",color:"mint",short:"Aklında kalmasın.",keywords:"not yaz"},
  {id:"tasks",name:"Günüm",icon:"ListTodo",color:"lavender",short:"Bir küçük adım.",keywords:"görev plan yapılacak"},
];
export type CatalogApp = {
  id: string; name: string; category: string; icon: string; color: string; note: string;
  url: string; package: string; artwork: string; play: boolean;
};
export const catalog: CatalogApp[] = [
  {
    "id": "firefox",
    "name": "Firefox",
    "category": "İnternet",
    "icon": "Globe2",
    "color": "orange",
    "note": "Bağımsız bir pencere.",
    "url": "https://www.mozilla.org/firefox/browsers/mobile/android/",
    "package": "org.mozilla.firefox",
    "artwork": "/assets/apps/firefox.svg",
    "play": true
  },
  {
    "id": "signal",
    "name": "Signal",
    "category": "İletişim",
    "icon": "MessageCircle",
    "color": "blue",
    "note": "Konuşmaların sana ait.",
    "url": "https://signal.org/download/",
    "package": "org.thoughtcrime.securesms",
    "artwork": "/assets/apps/signal.svg",
    "play": true
  },
  {
    "id": "vlc",
    "name": "VLC",
    "category": "Medya",
    "icon": "Play",
    "color": "orange",
    "note": "Müzik ve videoların, yanında.",
    "url": "https://www.videolan.org/vlc/download-android.html",
    "package": "org.videolan.vlc",
    "artwork": "/assets/apps/vlc.svg",
    "play": true
  },
  {
    "id": "organicmaps",
    "name": "Organic Maps",
    "category": "Harita",
    "icon": "Map",
    "color": "mint",
    "note": "Çevrimdışı yollar keşfet.",
    "url": "https://organicmaps.app/",
    "package": "app.organicmaps",
    "artwork": "/assets/apps/organicmaps.svg",
    "play": true
  },
  {
    "id": "telegram",
    "name": "Telegram",
    "category": "İletişim",
    "icon": "SendHorizontal",
    "color": "blue",
    "note": "Kanallar ve sohbetler.",
    "url": "https://telegram.org/android",
    "package": "org.telegram.messenger",
    "artwork": "/assets/apps/telegram.svg",
    "play": true
  },
  {
    "id": "whatsapp",
    "name": "WhatsApp",
    "category": "İletişim",
    "icon": "Phone",
    "color": "mint",
    "note": "Sevdiklerinle bağlantıda kal.",
    "url": "https://www.whatsapp.com/android",
    "package": "com.whatsapp",
    "artwork": "/assets/apps/whatsapp.svg",
    "play": true
  },
  {
    "id": "spotify",
    "name": "Spotify",
    "category": "Medya",
    "icon": "Music2",
    "color": "mint",
    "note": "Müzik ve podcast keşfi.",
    "url": "https://www.spotify.com/download/android/",
    "package": "com.spotify.music",
    "artwork": "/assets/apps/spotify.svg",
    "play": true
  },
  {
    "id": "bitwarden",
    "name": "Bitwarden",
    "category": "Güvenlik",
    "icon": "ShieldCheck",
    "color": "blue",
    "note": "Parolalarına bir yuva.",
    "url": "https://bitwarden.com/download/",
    "package": "com.x8bit.bitwarden",
    "artwork": "/assets/apps/bitwarden.svg",
    "play": true
  },
  {
    "id": "protonmail",
    "name": "Proton Mail",
    "category": "İletişim",
    "icon": "Mail",
    "color": "lavender",
    "note": "Postana farklı bir yaklaşım.",
    "url": "https://proton.me/mail/download",
    "package": "ch.protonmail.android",
    "artwork": "/assets/apps/protonmail.svg",
    "play": true
  },
  {
    "id": "nextcloud",
    "name": "Nextcloud",
    "category": "Üretkenlik",
    "icon": "FolderClosed",
    "color": "blue",
    "note": "Dosyalarınla bağlantıda kal.",
    "url": "https://nextcloud.com/install/",
    "package": "com.nextcloud.client",
    "artwork": "/assets/apps/nextcloud.svg",
    "play": true
  },
  {
    "id": "joplin",
    "name": "Joplin",
    "category": "Üretkenlik",
    "icon": "NotebookPen",
    "color": "blue",
    "note": "Notlar, listeler, fikirler.",
    "url": "https://joplinapp.org/help/install/",
    "package": "net.cozic.joplin",
    "artwork": "/assets/apps/joplin.svg",
    "play": true
  },
  {
    "id": "obsidian",
    "name": "Obsidian",
    "category": "Üretkenlik",
    "icon": "BookOpen",
    "color": "lavender",
    "note": "Birbirine bağlanan düşünceler.",
    "url": "https://obsidian.md/download",
    "package": "md.obsidian",
    "artwork": "/assets/apps/obsidian.svg",
    "play": true
  },
  {
    "id": "duckduckgo",
    "name": "DuckDuckGo",
    "category": "İnternet",
    "icon": "Search",
    "color": "orange",
    "note": "Webde kendi yolunu seç.",
    "url": "https://duckduckgo.com/app",
    "package": "com.duckduckgo.mobile.android",
    "artwork": "/assets/apps/duckduckgo.svg",
    "play": true
  },
  {
    "id": "brave",
    "name": "Brave",
    "category": "İnternet",
    "icon": "Globe2",
    "color": "orange",
    "note": "Alternatif bir tarayıcı.",
    "url": "https://brave.com/download/",
    "package": "com.brave.browser",
    "artwork": "/assets/apps/brave.svg",
    "play": true
  },
  {
    "id": "kdeconnect",
    "name": "KDE Connect",
    "category": "Araçlar",
    "icon": "Smartphone",
    "color": "blue",
    "note": "Telefonun ve bilgisayarın.",
    "url": "https://kdeconnect.kde.org/download.html",
    "package": "org.kde.kdeconnect_tp",
    "artwork": "/assets/apps/kdeconnect.svg",
    "play": true
  },
  {
    "id": "wikipedia",
    "name": "Wikipedia",
    "category": "Okuma",
    "icon": "BookOpen",
    "color": "gray",
    "note": "Merakına bir sayfa aç.",
    "url": "https://www.mediawiki.org/wiki/Wikimedia_Apps",
    "package": "org.wikipedia",
    "artwork": "/assets/apps/wikipedia.svg",
    "play": true
  },
  {
    "id": "antennapod",
    "name": "AntennaPod",
    "category": "Medya",
    "icon": "Radio",
    "color": "blue",
    "note": "Podcastlerin için açık bir kapı.",
    "url": "https://antennapod.org/download",
    "package": "de.danoeh.antennapod",
    "artwork": "/assets/apps/antennapod.svg",
    "play": true
  },
  {
    "id": "element",
    "name": "Element X",
    "category": "İletişim",
    "icon": "MessageCircle",
    "color": "mint",
    "note": "Matrix üzerinde iletişim.",
    "url": "https://element.io/download",
    "package": "io.element.android.x",
    "artwork": "/assets/apps/element.svg",
    "play": true
  },
  {
    "id": "aegis",
    "name": "Aegis",
    "category": "Güvenlik",
    "icon": "LockKeyhole",
    "color": "blue",
    "note": "İki adımlı doğrulama kodları.",
    "url": "https://getaegis.app/",
    "package": "com.beemdevelopment.aegis",
    "artwork": "/assets/apps/aegis.svg",
    "play": true
  },
  {
    "id": "thunderbird",
    "name": "Thunderbird",
    "category": "İletişim",
    "icon": "Mail",
    "color": "blue",
    "note": "E-posta, açık bir yaklaşımla.",
    "url": "https://www.thunderbird.net/mobile/",
    "package": "net.thunderbird.android",
    "artwork": "/assets/apps/thunderbird.svg",
    "play": true
  },
  {
    "id": "fdroid",
    "name": "F-Droid",
    "category": "Araçlar",
    "icon": "ShoppingBag",
    "color": "mint",
    "note": "Özgür yazılım kataloğu.",
    "url": "https://f-droid.org/",
    "package": "org.fdroid.fdroid",
    "artwork": "/assets/apps/fdroid.svg",
    "play": false
  },
  {
    "id": "newpipe",
    "name": "NewPipe",
    "category": "Medya",
    "icon": "Play",
    "color": "pink",
    "note": "Bağımsız bir medya istemcisi.",
    "url": "https://newpipe.net/",
    "package": "org.schabi.newpipe",
    "artwork": "/assets/apps/newpipe.svg",
    "play": false
  },
  {
    "id": "osmand",
    "name": "OsmAnd",
    "category": "Harita",
    "icon": "Map",
    "color": "orange",
    "note": "Açık haritalarla yolunu bul.",
    "url": "https://osmand.net/",
    "package": "net.osmand",
    "artwork": "/assets/apps/osmand.svg",
    "play": true
  },
  {
    "id": "collabora",
    "name": "Collabora Office",
    "category": "Üretkenlik",
    "icon": "File",
    "color": "lavender",
    "note": "Belgelerin yanında olsun.",
    "url": "https://www.collaboraoffice.com/collabora-office-android-ios/",
    "package": "com.collabora.libreoffice",
    "artwork": "/assets/apps/collabora.svg",
    "play": true
  }
];
export const googleLinks = [
  {name:'Google',icon:'Search',url:'https://www.google.com/',color:'blue'},
  {name:'Gmail',icon:'Mail',url:'https://mail.google.com/',color:'pink'},
  {name:'Haritalar',icon:'Map',url:'https://maps.google.com/',color:'mint'},
  {name:'YouTube',icon:'Play',url:'https://www.youtube.com/',color:'orange'},
  {name:'Drive',icon:'FolderClosed',url:'https://drive.google.com/',color:'sand'},
  {name:'Çeviri',icon:'Languages',url:'https://translate.google.com/',color:'lavender'},
];
export const articles = [
  {id:'slow-city',title:'Bir şehri yavaşça keşfetmek',category:'KÜLTÜR ROTASI',image:'news-culture',time:'3 dk',subtitle:'Yol, bazen biraz yavaşlayınca başlar.',body:'Bir sabah rotanı biraz değiştir. Her gün önünden geçtiğin sokağa bu kez başka bir gözle bak. Bir kapının rengi, küçük bir dükkânın tabelası, uzaktan gelen bir çay kaşığının sesi… Keşif için her zaman uzaklara gitmek gerekmiyor.\n\nBu sayfa, OğuzDows kültür koleksiyonuyla hazırlanmış özgün bir okuma örneğidir; güncel haber veya seyahat verisi değildir. Görsel, mevcut kültür koleksiyonundan gelir.\n\nKendi küçük rotanı Defter’e yazabilir, daha sonra yeniden okumak için bu metni kitaplığına ekleyebilirsin.'},
  {id:'light-phone',title:'Daha hafif bir dijital gün',category:'İYİ YAŞAM',image:'mountains',time:'2 dk',subtitle:'Az bildirim. Daha çok kendine ait zaman.',body:'Telefonun gününe eşlik etsin, gününü ele geçirmesin. İhtiyacın olmayan bildirimleri sistem ayarlarından gözden geçirmek ve kendine kısa bir odak aralığı ayırmak iyi bir başlangıç olabilir.\n\nÖnizlemedeki Odak anahtarı yalnızca arayüz tercihini değiştirir; gerçek Rahatsız Etmeyin izni veya bildirim engellemesi sağlamaz. Hafif profil de sadece bu arayüzün görsel katmanını sadeleştirir.\n\nİstersen Günüm’e tek bir küçük hedef ekle. Tamamlandığında işaretlemek sana kalsın.'},
  {id:'own-device',title:'Cihazın senin, seçim de senin',category:'OĞUZDOWS NOTLARI',image:'salt-lake',time:'2 dk',subtitle:'Açık kaynak, açık bilgi, açık onay.',body:'OğuzDows Mobile tasarımı, uygulamaları ve verileri üzerinde söz sahibi olmanı önemser. Dışarıdan bir paket seçmek, onu güvenilir yapmaz. Kaynağını ve gereken izinleri incelemek her zaman önemlidir.\n\nBu tarayıcı, APK dosyasının yalnızca başlangıç baytlarını ve SHA-256 özetini inceleyebilir. Geliştirici güveni, imza doğrulaması, zararlı yazılım taraması veya kurulum sağlamaz.\n\nGerçek cihaz sürümünde son söz sistemin paket yükleyicisinde ve senin açık onayında olacaktır.'},
];
