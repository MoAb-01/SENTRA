import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { SupportedLang } from '../i18n';

interface PolicyCopy {
  backHome: string;
  eyebrow: string;
  title: string;
  updated: string;
  intro: string;
  sections: {
    heading: string;
    body: string;
  }[];
  contactHeading: string;
  contactBody: string;
}

const POLICY_COPY: Record<SupportedLang, PolicyCopy> = {
  en: {
    backHome: 'Back to Home',
    eyebrow: 'PRIVACY & COOKIES',
    title: 'Privacy Policy',
    updated: 'Last updated: November 26, 2026',
    intro:
      'This website is an informational landing page for the SENTRA project. We respect your privacy and keep data handling minimal and transparent.',
    sections: [
      {
        heading: '1. No Personal Data Collection',
        body: 'Browsing this landing page does not require registration, forms, or account creation. We do not collect, sell, or share personal information from visitors.',
      },
      {
        heading: '2. Zero Cookies & Zero Tracking',
        body: 'This landing page does not set any cookies, advertising trackers, analytics scripts, or local browser storage.',
      },
      {
        heading: '3. Third-Party Resources & External Links',
        body: 'Web fonts (Nunito and Caveat) are loaded from Google Fonts. Clicking external links such as GitHub or LinkedIn takes you to third-party websites governed by their own privacy policies.',
      },
    ],
    contactHeading: '4. Contact',
    contactBody:
      'If you have any questions about this website or its privacy policy, you can reach Mohamed Abdou via GitHub or LinkedIn.',
  },
  tr: {
    backHome: 'Ana Sayfaya Dön',
    eyebrow: 'GİZLİLİK VE ÇEREZLER',
    title: 'Gizlilik Politikası',
    updated: 'Son güncelleme: 26 Kasım 2026',
    intro:
      'Bu web sitesi SENTRA projesi için hazırlanmış bilgilendirici bir açılış sayfasıdır. Gizliliğinize saygı duyuyoruz ve veri kullanımını en aza indiriyoruz.',
    sections: [
      {
        heading: '1. Kişisel Veri Toplanmaz',
        body: 'Bu açılış sayfasını ziyaret etmek için kayıt olmanız, form doldurmanız veya hesap açmanız gerekmez. Ziyaretçilerden kişisel veri toplamıyor, satmıyor veya paylaşmıyoruz.',
      },
      {
        heading: '2. Sıfır Çerez ve Sıfır İzleme',
        body: 'Bu açılış sayfası hiçbir çerez, reklam izleyicisi, analitik betiği veya yerel tarayıcı depolaması kullanmaz.',
      },
      {
        heading: '3. Üçüncü Taraf Kaynaklar ve Dış Bağlantılar',
        body: 'Yazı tipleri (Nunito ve Caveat) Google Fonts üzerinden yüklenir. GitHub veya LinkedIn gibi dış bağlantılara tıkladığınızda ilgili platformların kendi gizlilik politikaları geçerlidir.',
      },
    ],
    contactHeading: '4. İletişim',
    contactBody:
      'Bu web sitesi veya gizlilik politikası hakkında sorularınız için Mohamed Abdou ile GitHub veya LinkedIn üzerinden iletişime geçebilirsiniz.',
  },
  ar: {
    backHome: 'العودة إلى الرئيسية',
    eyebrow: 'الخصوصية وملفات تعريف الارتباط',
    title: 'سياسة الخصوصية',
    updated: 'آخر تحديث: 26 نوفمبر 2026',
    intro:
      'هذا الموقع هو صفحة تعريفية لمشروع SENTRA. نحن نحترم خصوصيتك ونلتزم بالشفافية الكاملة وعدم جمع أي بيانات غير ضرورية.',
    sections: [
      {
        heading: '1. عدم جمع البيانات الشخصية',
        body: 'لا يتطلب تصفح هذه الصفحة إنشاء حساب أو تعبئة نماذج. نحن لا نجمع أو نبيع أو نشارك أي بيانات شخصية عن الزوار.',
      },
      {
        heading: '2. بدون ملفات تعريف ارتباط أو تتبع',
        body: 'لا تستخدم هذه الصفحة أي ملفات تعريف ارتباط أو متتبعات إعلانية أو أدوات تحليلية أو تخزين محلي في المتصفح.',
      },
      {
        heading: '3. الموارد والروابط الخارجية',
        body: 'يتم تحميل خطوط الويب (Nunito و Caveat) من Google Fonts. كما أن النقر على الروابط الخارجية مثل GitHub أو LinkedIn ينقلك إلى مواقع خارجية تخضع لسياسات الخصوصية الخاصة بها.',
      },
    ],
    contactHeading: '4. التواصل',
    contactBody:
      'لأي استفسار حول هذا الموقع أو سياسة الخصوصية، يمكنك التواصل مع Mohamed Abdou عبر GitHub أو LinkedIn.',
  },
};

export const PrivacyPolicy: React.FC = () => {
  const { lang = 'tr' } = useParams<{ lang: SupportedLang }>();
  const currentLang = (['tr', 'en', 'ar'].includes(lang) ? lang : 'tr') as SupportedLang;
  const copy = POLICY_COPY[currentLang];
  const isRtl = currentLang === 'ar';

  return (
    <div className={`sentra-layout ${isRtl ? 'rtl' : ''}`} style={{ minHeight: '100vh', background: '#F8FAFC' }}>
      <header className="header">
        <div className="header-inner">
          <Link to={`/${currentLang}`} className="logo" aria-label="Sentra">
            <img
              src="/sentra-logo.png"
              alt="SENTRA"
              style={{ height: '34px', width: 'auto', display: 'block', objectFit: 'contain' }}
            />
          </Link>

          <div className="header-actions">
            <div className="lang-switch">
              <Link to="/en/privacy" className={currentLang === 'en' ? 'active' : ''}>EN</Link>
              <Link to="/tr/privacy" className={currentLang === 'tr' ? 'active' : ''}>TR</Link>
              <Link to="/ar/privacy" className={currentLang === 'ar' ? 'active' : ''}>AR</Link>
            </div>
          </div>
        </div>
      </header>

      <main className="container" style={{ maxWidth: '800px', padding: '56px 20px 84px' }}>
        <Link
          to={`/${currentLang}`}
          style={{
            display: 'inline-block',
            color: 'var(--brand-orange)',
            fontWeight: 800,
            fontSize: '13.5px',
            marginBottom: '20px',
          }}
        >
          {isRtl ? `${copy.backHome} →` : `← ${copy.backHome}`}
        </Link>

        <div
          style={{
            background: '#FFFFFF',
            border: '1px solid #E2E8F0',
            borderRadius: '16px',
            padding: '40px 36px',
            boxShadow: '0 10px 30px rgba(15, 23, 42, 0.04)',
          }}
        >
          <p
            style={{
              fontSize: '11.5px',
              fontWeight: 800,
              letterSpacing: '0.12em',
              color: 'var(--brand-orange)',
              marginBottom: '8px',
            }}
          >
            {copy.eyebrow}
          </p>
          <h1 style={{ fontSize: '30px', fontWeight: 800, color: '#0F172A', marginBottom: '8px' }}>
            {copy.title}
          </h1>
          <p style={{ fontSize: '13px', color: '#64748B', marginBottom: '24px' }}>{copy.updated}</p>

          <p
            style={{
              fontSize: '15px',
              color: '#334155',
              lineHeight: 1.7,
              paddingBottom: '24px',
              borderBottom: '1px solid #E2E8F0',
              marginBottom: '28px',
            }}
          >
            {copy.intro}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginBottom: '32px' }}>
            {copy.sections.map((sec) => (
              <section key={sec.heading}>
                <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#0F172A', marginBottom: '8px' }}>
                  {sec.heading}
                </h2>
                <p style={{ fontSize: '14.5px', color: '#475569', lineHeight: 1.7 }}>{sec.body}</p>
              </section>
            ))}
          </div>

          <section>
            <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#0F172A', marginBottom: '8px' }}>
              {copy.contactHeading}
            </h2>
            <p style={{ fontSize: '14.5px', color: '#475569', lineHeight: 1.7, marginBottom: '10px' }}>
              {copy.contactBody}
            </p>
            <div style={{ display: 'flex', gap: '16px', fontSize: '13.5px', fontWeight: 700 }}>
              <a
                href="https://github.com/MoAb-01"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--brand-orange)' }}
              >
                GitHub ↗
              </a>
              <a
                href="https://www.linkedin.com/in/contact-mohamed-abdou/"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--brand-orange)' }}
              >
                LinkedIn ↗
              </a>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};
