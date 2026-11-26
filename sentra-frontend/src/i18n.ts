export type SupportedLang = 'tr' | 'en' | 'ar';

export interface TranslationDict {
  brandName: string;
  tagline: string;
  nav: {
    corporate: string;
    sustainability: string;
    innovation: string;
    infoCenter: string;
    kvkk: string;
    contact: string;
    aboutProject: string;
    techStack: string;
    aboutDeveloper: string;
    portal: string;
    login: string;
    logout: string;
    dashboard: string;
  };
  hero: {
    titleLine1: string;
    titleLine2: string;
    titleLine3: string;
    cta: string;
    badgeText: string;
    badgeSub: string;
  };
  actions: {
    card1Title: string;
    card1Desc: string;
    card2Title: string;
    card2Desc: string;
    card3Title: string;
    card3Desc: string;
    card4Title: string;
    card4Desc: string;
    card5Title: string;
    card5Desc: string;
  };
  glab: {
    badge: string;
    subtitle: string;
    title: string;
    footerText: string;
  };
  architecture: {
    title: string;
    subtitle: string;
    tier1Title: string;
    tier1Desc: string;
    tier1Spec1: string;
    tier1Spec2: string;
    tier2Title: string;
    tier2Desc: string;
    tier2Spec1: string;
    tier2Spec2: string;
    tier3Title: string;
    tier3Desc: string;
    tier3Spec1: string;
    tier3Spec2: string;
  };
  social: {
    card1Title: string;
    card1Sub: string;
    card1Text: string;
    card2Title: string;
    card2Sub: string;
    card2Text: string;
    card3Title: string;
    card3Sub: string;
    card3Text: string;
    card4Title: string;
    card4Sub: string;
    card4Text: string;
    readMore: string;
  };
  portal: {
    title: string;
    subtitle: string;
    activeIncidents: string;
    gridStability: string;
    activeNodes: string;
    telemetryRate: string;
    incidentFeed: string;
    nodeManager: string;
    actionsHeader: string;
    dispatchUnit: string;
    securityAudit: string;
    renewTokenManual: string;
    authStatus: string;
    tokenExpiry: string;
    loginPrompt: string;
    adminRole: string;
    operatorRole: string;
  };
  footer: {
    elderText: string;
    corporateCol: string;
    investorCol: string;
    sustainabilityCol: string;
    infoCol: string;
    mediaCol: string;
    followUs: string;
    rightsReserved: string;
  };
}

export const translations: Record<SupportedLang, TranslationDict> = {
  tr: {
    brandName: 'SENTRA',
    tagline: 'Gelecek Nesil Uç Güvenlik ve Enerji Operasyon Platformu',
    nav: {
      corporate: 'Kurumsal',
      sustainability: 'Sürdürülebilirlik',
      innovation: 'İnovasyon',
      infoCenter: 'Bilgi Merkezi',
      kvkk: 'KVKK',
      contact: 'İletişim',
      aboutProject: 'Proje Hakkında',
      techStack: 'Temel İlkeler',
      aboutDeveloper: 'Geliştirici Hakkında',
      portal: 'Operasyon Portalı',
      login: 'Giriş Yap',
      logout: 'Çıkış Yap',
      dashboard: 'Yönetim Masası',
    },
    hero: {
      titleLine1: 'Gelecek için',
      titleLine2: 'Kesintisiz Uç',
      titleLine3: 'Güvenlik Mimarisi',
      cta: 'DETAYLAR İÇİN TIKLAYINIZ',
      badgeText: 'ENERJİ',
      badgeSub: 'AVCILARI',
    },
    actions: {
      card1Title: 'Edge AI Perception',
      card1Desc: 'YOLOv8n object detection & ray-casting PiP validation.',
      card2Title: 'Offline Outbox',
      card2Desc: 'SQLite WAL local queue for zero data loss during network blackouts.',
      card3Title: 'Cryptographic Gateway',
      card3Desc: 'FastAPI ingestion with AES-256-GCM and replay protection.',
      card4Title: 'Dynamic Geofencing',
      card4Desc: 'JSONB polygon hot-reload synced instantly to edge nodes.',
      card5Title: 'Operator Audit Log',
      card5Desc: 'Append-only triage records and automated data purge.',
    },
    glab: {
      badge: '⚡ G-LAB',
      subtitle: 'İnovasyon ve Ar-ge Faaliyetleri',
      title: 'GLAB ile geleceğe inovatif çözümler sunuyoruz',
      footerText: 'İnovasyon ve Ar-ge Faaliyetleri hakkında detaylı bilgi için',
    },
    architecture: {
      title: 'Üç Katmanlı Sistem',
      subtitle: 'Uç algılama ve kriptografik dayanıklılıktan merkezi operasyonlara.',
      tier1Title: 'Uç Yapay Zeka Algılama',
      tier1Desc: 'Ham video akışı düğümden hiç ayrılmaz; yalnızca matematiksel olarak doğrulanmış ihlaller ve çift kırpma kanıtı iletilerek bant genişliği >95% oranında azaltılır.',
      tier1Spec1: '3 karelik zamansal filtreleme ile 30ms altı nicemlenmiş çıkarım.',
      tier1Spec2: 'Otomatik geniş sahne ve üst vücut RoI çıkarımı ile hassas zemin teması doğrulaması.',
      tier2Title: 'Çevrimdışı Kuyruk ve Kriptografi',
      tier2Desc: 'Ağ kesintilerinde bile hiçbir telemetri veya kanıt kaybolmaz; tüm paketler uçtan uca şifrelenir.',
      tier2Spec1: 'Kimlik doğrulamalı şifreleme ve tekrar saldırısı koruması.',
      tier2Spec2: 'Kesinti sırasında sıfır veri kaybı sağlayan yerel kuyruk.',
      tier3Title: 'Komuta Merkezi ve Kanıt Kasası',
      tier3Desc: 'Merkezi operasyon masası, gerçek zamanlı olay akışı ve değişmez denetim kayıtları sunar.',
      tier3Spec1: 'Yüksek eşzamanlılıklı API ve JSONB coğrafi veri yönetimi.',
      tier3Spec2: 'Şifreli medya kanıtları için ölçeklenebilir nesne depolama.',
    },
    social: {
      card1Title: 'ÇÜNKÜ HER ŞEY BİR FİKİRLE BAŞLAR',
      card1Sub: 'SENTRA Başlangıç Hikayesi',
      card1Text: 'SENTRA projesinin temelleri, bir üniversite öğrencisinin bitirme projesi kapsamında geliştirdiği yalın bir fikirle atıldı. Kurumların kritik tesis ve altyapılarını uç güvenlik mimarisiyle korumayı hedefleyen bu vizyon, bugün ölçeklenebilir bir savunma ekosistemine dönüştü.',
      card2Title: 'Birinci Aşama Bitti!',
      card2Sub: 'Mimari ve Dokümantasyon Tamamlandı',
      card2Text: 'SENTRA projesinin ilk aşaması olan kapsamlı dokümantasyon ve sistem mimarisi tasarımı gururla tamamlandı! Temel altyapı kodlamasına geçiş için hazırız.',
      card3Title: 'BÜYÜK GÜN YAKLAŞIYOR!',
      card3Sub: 'Proje Değerlendirmesi • 60 Gün',
      card3Text: 'Bugün, SENTRA projesinde kritik bir kilometre taşı olan web operasyon platformumuzun geliştirme sürecini resmen başlattık. Yeni fikir ve geri bildirimlerinizi heyecanla bekliyoruz!',
      card4Title: 'GRID UP',
      card4Sub: 'Hızlandırma Programı',
      card4Text: "Geleceğin enerji teknolojilerini şekillendiren girişimlerde büyük final için geri sayım başladı! Bodrum'da buluşuyoruz.",
      readMore: 'DAHA FAZLA İNCELE',
    },
    portal: {
      title: 'SENTRA Operasyon & Kontrol Masası',
      subtitle: 'Gerçek zamanlı uç şebeke güvenliği, telemetri izleme ve dinamik operasyon portali.',
      activeIncidents: 'Aktif Olaylar',
      gridStability: 'Şebeke Stabilitesi',
      activeNodes: 'Uç Düğümler',
      telemetryRate: 'Telemetri Hızı',
      incidentFeed: 'Canlı Olay Akışı',
      nodeManager: 'Düğüm ve Alt İstasyon Yönetimi',
      actionsHeader: 'Operasyonel Komutlar',
      dispatchUnit: 'Saha Ekibi Yönlendir',
      securityAudit: 'Güvenlik Taraması Başlat',
      renewTokenManual: 'Token Yenile (Manuel)',
      authStatus: 'Oturum Durumu',
      tokenExpiry: 'Kalan Erişim Süresi',
      loginPrompt: 'Operasyon portalına erişmek için lütfen giriş yapınız.',
      adminRole: 'Sistem Yöneticisi',
      operatorRole: 'Şebeke Operatörü',
    },
    footer: {
      elderText: 'Şirketimiz Elder Üyesidir',
      corporateCol: 'Kurumsal',
      investorCol: 'Yatırımcı İlişkileri',
      sustainabilityCol: 'Sürdürülebilirlik',
      infoCol: 'Bilgi Merkezi',
      mediaCol: 'Medya Merkezi',
      followUs: 'Bizi takip edin',
      rightsReserved: 'Tüm Hakları Saklıdır.',
    },
  },
  en: {
    brandName: 'SENTRA',
    tagline: 'Next-Gen Edge Security and Energy Operations Platform',
    nav: {
      corporate: 'Corporate',
      sustainability: 'Sustainability',
      innovation: 'Innovation',
      infoCenter: 'Info Center',
      kvkk: 'GDPR / KVKK',
      contact: 'Contact',
      aboutProject: 'About The Project',
      techStack: 'Core Pillars',
      aboutDeveloper: 'About the Developer',
      portal: 'Operations Portal',
      login: 'Sign In',
      logout: 'Sign Out',
      dashboard: 'Control Desk',
    },
    hero: {
      titleLine1: 'Resilient Edge',
      titleLine2: 'Security Architecture',
      titleLine3: 'For the Future',
      cta: 'CLICK FOR DETAILS',
      badgeText: 'ENERGY',
      badgeSub: 'HUNTERS',
    },
    actions: {
      card1Title: 'Edge AI Perception',
      card1Desc: 'YOLOv8n object detection & ray-casting PiP validation.',
      card2Title: 'Offline Outbox',
      card2Desc: 'SQLite WAL local queue for zero data loss during network blackouts.',
      card3Title: 'Cryptographic Gateway',
      card3Desc: 'FastAPI ingestion with AES-256-GCM and replay protection.',
      card4Title: 'Dynamic Geofencing',
      card4Desc: 'JSONB polygon hot-reload synced instantly to edge nodes.',
      card5Title: 'Operator Audit Log',
      card5Desc: 'Append-only triage records and automated data purge.',
    },
    glab: {
      badge: '⚡ G-LAB',
      subtitle: 'Innovation & R&D Operations',
      title: 'Delivering innovative solutions for the future with GLAB',
      footerText: 'Learn more about Innovation and R&D activities',
    },
    architecture: {
      title: 'Three-Tier System',
      subtitle: 'From edge perception and cryptographic resilience to centralized operations.',
      tier1Title: 'On the Edge AI',
      tier1Desc: 'Raw video never leaves the stream node, cutting bandwidth by >95% by transmitting only mathematically verified intrusions and dual-crop evidence.',
      tier1Spec1: 'Sub-30ms quantized inference with 3-frame temporal filtering.',
      tier1Spec2: 'Exact ground-contact validation paired with automated wide-scene and upper-body RoI extraction.',
      tier2Title: 'Offline Outbox & Cryptography',
      tier2Desc: 'Zero telemetry or evidence loss during network blackouts, with end-to-end authenticated encryption.',
      tier2Spec1: 'Authenticated encryption with replay attack protection.',
      tier2Spec2: 'Local persistent queue guaranteeing zero data loss.',
      tier3Title: 'Command Center & Evidence Vault',
      tier3Desc: 'Centralized operations desk providing real-time incident feeds and immutable audit trails.',
      tier3Spec1: 'High-concurrency API and JSONB geospatial management.',
      tier3Spec2: 'Scalable object storage for encrypted media evidence.',
    },
    social: {
      card1Title: 'BECAUSE EVERYTHING STARTS WITH AN IDEA',
      card1Sub: 'The SENTRA Origin Story',
      card1Text: 'The genesis of the SENTRA project began with a simple idea by a university student as part of a graduation project, designed to empower organizations and critical utilities to protect and monitor their facilities with resilient edge intelligence.',
      card2Title: 'Phase One Completed!',
      card2Sub: 'Architecture & Documentation Complete',
      card2Text: 'The first stage of the SENTRA project was the documentation and system architecture is proudly announced to be completed! Ready to move forward to the core implementation.',
      card3Title: 'THE BIG DAY IS APPROACHING!',
      card3Sub: 'Project Evaluation • 60 Days',
      card3Text: 'Today, we have started to work out the implementation plan of our website platform which serves as an important milestone into the SENTRA project. Waiting to hear opinions and ideas!',
      card4Title: 'GRID UP',
      card4Sub: 'Accelerator Program',
      card4Text: 'Countdown begins for the grand finale shaping future energy technology! Meeting in Bodrum.',
      readMore: 'EXPLORE MORE',
    },
    portal: {
      title: 'SENTRA Operations & Control Desk',
      subtitle: 'Real-time edge grid security, telemetry telemetry monitoring and operations portal.',
      activeIncidents: 'Active Incidents',
      gridStability: 'Grid Stability',
      activeNodes: 'Active Nodes',
      telemetryRate: 'Telemetry Rate',
      incidentFeed: 'Live Incident Feed',
      nodeManager: 'Node & Substation Management',
      actionsHeader: 'Operational Commands',
      dispatchUnit: 'Dispatch Field Unit',
      securityAudit: 'Trigger Security Audit',
      renewTokenManual: 'Renew Token (Manual)',
      authStatus: 'Session Status',
      tokenExpiry: 'Access Token Remaining',
      loginPrompt: 'Please authenticate to access the operations control portal.',
      adminRole: 'System Administrator',
      operatorRole: 'Grid Operator',
    },
    footer: {
      elderText: 'Our company is an Elder Member',
      corporateCol: 'Corporate',
      investorCol: 'Investor Relations',
      sustainabilityCol: 'Sustainability',
      infoCol: 'Information Center',
      mediaCol: 'Media Center',
      followUs: 'Follow Us',
      rightsReserved: 'All Rights Reserved.',
    },
  },
  ar: {
    brandName: 'سينترا SENTRA',
    tagline: 'منصة أمن الحافة والعمليات الذكية لشبكات الطاقة',
    nav: {
      corporate: 'عن الشركة',
      sustainability: 'الاستدامة',
      innovation: 'الابتكار',
      infoCenter: 'مركز المعلومات',
      kvkk: 'حماية البيانات',
      contact: 'اتصل بنا',
      aboutProject: 'عن المشروع',
      techStack: 'الركائز الأساسية',
      aboutDeveloper: 'عن المطور',
      portal: 'بوابة العمليات',
      login: 'تسجيل الدخول',
      logout: 'تسجيل الخروج',
      dashboard: 'لوحة التحكم',
    },
    hero: {
      titleLine1: 'معمارية أمان الحافة',
      titleLine2: 'المتواصلة والمرنة',
      titleLine3: 'من أجل المستقبل',
      cta: 'انقر للحصول على التفاصيل',
      badgeText: 'صائدو',
      badgeSub: 'الطاقة',
    },
    actions: {
      card1Title: 'Edge AI Perception',
      card1Desc: 'كشف الأجسام عبر YOLOv8n والتحقق الهندسي PiP عند الحافة.',
      card2Title: 'Offline Outbox',
      card2Desc: 'طابور محلي بتنسيق SQLite WAL لضمان عدم فقدان البيانات أثناء انقطاع الشبكة.',
      card3Title: 'Cryptographic Gateway',
      card3Desc: 'بوابة استقبال عبر FastAPI بتشفير AES-256-GCM وحماية من هجمات الإعادة.',
      card4Title: 'Dynamic Geofencing',
      card4Desc: 'تحديث فوري للمضلعات الجغرافية بتنسيق JSONB ومزامنتها مع أجهزة الحافة.',
      card5Title: 'Operator Audit Log',
      card5Desc: 'سجلات تدقيق غير قابلة للتعديل وفرز آلي للبيانات مع سياسات الإتلاف المنظم.',
    },
    glab: {
      badge: '⚡ جي-لاب',
      subtitle: 'أنشطة الابتكار والبحث والتطوير',
      title: 'نقدم حلولاً مبتكرة للمستقبل عبر مختبر GLAB',
      footerText: 'لمزيد من المعلومات حول أنشطة الابتكار والتطوير',
    },
    architecture: {
      title: 'نظام ثلاثي الطبقات',
      subtitle: 'من الإدراك عند الحافة والمرونة التشفيرية إلى العمليات المركزية.',
      tier1Title: 'الإدراك الذكي عند الحافة',
      tier1Desc: 'لا يغادر الفيديو الخام عقدة البث أبداً، مما يقلل استهلاك النطاق الترددي بنسبة >95% عبر إرسال الانتهاكات المؤكدة رياضياً والأدلة ثنائية الاقتصاص فقط.',
      tier1Spec1: 'استدلال مكمّم بأقل من 30 مللي ثانية مع ترشيح زمني لـ 3 إطارات.',
      tier1Spec2: 'تحقق دقيق من ملامسة الأرض مقترن باستخراج تلقائي للمشهد الواسع ومنطقة الاهتمام (RoI) للجزء العلوي من الجسم.',
      tier2Title: 'الطابور المحلي والتشفير',
      tier2Desc: 'لا تُفقد أي بيانات قياس أو أدلة أثناء انقطاع الشبكة، مع تشفير مصادق عليه من الطرف إلى الطرف.',
      tier2Spec1: 'تشفير مصادق عليه مع حماية ضد هجمات الإعادة.',
      tier2Spec2: 'طابور محلي مستمر يضمن عدم فقدان البيانات.',
      tier3Title: 'مركز القيادة وخزنة الأدلة',
      tier3Desc: 'مكتب عمليات مركزي يوفر بثاً مباشراً للحوادث وسجلات تدقيق غير قابلة للتعديل.',
      tier3Spec1: 'واجهة برمجية عالية التزامن وإدارة بيانات مكانية JSONB.',
      tier3Spec2: 'تخزين كائني قابل للتوسع للأدلة الإعلامية المشفرة.',
    },
    social: {
      card1Title: 'لأن كل شيء يبدأ بفكرة',
      card1Sub: 'قصة انطلاق مشروع سينترا',
      card1Text: 'انطلقت شرارة مشروع سينترا (SENTRA) من فكرة بسيطة لطالب جامعي كجزء من مشروع تخرجه، بهدف تمكين المؤسسات ومرافق البنية التحتية من حماية منشآتها عبر منظومة أمن الحافة الذكية.',
      card2Title: 'اكتملت المرحلة الأولى!',
      card2Sub: 'إنجاز التوثيق وهندسة النظام',
      card2Text: 'يسرنا الإعلان بفخر عن اكتمال المرحلة الأولى من مشروع سينترا والمتمثلة في التوثيق الشامل وهندسة وتصميم النظام، تمهيداً للانطلاق نحو مراحل التنفيذ والربط الميداني!',
      card3Title: 'اليوم الكبير يقترب!',
      card3Sub: 'تقييم المشروع • باقي 60 يوماً',
      card3Text: 'بدأنا اليوم رسمياً العمل على خطة تنفيذ منصة الويب التشغيلية لمشروع سينترا، والتي تمثل محطة محورية في مسار المشروع. ننتظر آراءكم وأفكاركم بشغف!',
      card4Title: 'GRID UP',
      card4Sub: 'برنامج التسريع والنمو',
      card4Text: 'بدأ العد التنازلي للنهائي الكبير الذي يرسم مستقبل حلول الطاقة الحديثة!',
      readMore: 'استكشف المزيد',
    },
    portal: {
      title: 'بوابة سينترا للعمليات والتحكم',
      subtitle: 'نظام المراقبة الفورية لأمن الشبكات وأجهزة الحافة والقياس عن بُعد.',
      activeIncidents: 'الحوادث النشطة',
      gridStability: 'استقرار الشبكة',
      activeNodes: 'العقد النشطة',
      telemetryRate: 'معدل القياس',
      incidentFeed: 'سجل البلاغات المباشر',
      nodeManager: 'إدارة المحطات والعقد الطرفية',
      actionsHeader: 'الأوامر التشغيلية',
      dispatchUnit: 'إرسال فريق الصيانة الميداني',
      securityAudit: 'إجراء فحص أمني فوري',
      renewTokenManual: 'تجديد الجلسة (يدوياً)',
      authStatus: 'حالة المصادقة',
      tokenExpiry: 'الوقت المتبقي لرمز الوصول',
      loginPrompt: 'يرجى تسجيل الدخول للوصول إلى لوحة العمليات التشغيلية.',
      adminRole: 'مدير النظام',
      operatorRole: 'مشغل الشبكة',
    },
    footer: {
      elderText: 'شركتنا عضو في اتحاد إلدر',
      corporateCol: 'المؤسسة',
      investorCol: 'علاقات المستثمرين',
      sustainabilityCol: 'الاستدامة',
      infoCol: 'مركز المعلومات',
      mediaCol: 'المركز الإعلامي',
      followUs: 'تابعونا',
      rightsReserved: 'جميع الحقوق محفوظة.',
    },
  },
};
