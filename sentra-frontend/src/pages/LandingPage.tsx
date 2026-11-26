import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { translations, SupportedLang } from '../i18n';
import { EdgePerceptionVisual } from '../components/EdgePerceptionVisual';
import { NetworkResilienceVisual } from '../components/NetworkResilienceVisual';
import { CommandPillarsVisual } from '../components/CommandPillarsVisual';
import { DeveloperMindMap } from '../components/DeveloperMindMap';

export const MarkerHighlight: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className="marker-highlight">
    <span className="marker-highlight-text">{children}</span>
    <svg
      aria-hidden="true"
      viewBox="0 0 120 14"
      preserveAspectRatio="none"
      className="marker-highlight-svg"
    >
      <path
        d="M3 10.5 Q 42 3.5, 117 8.5"
        fill="none"
        stroke="#FF5500"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeOpacity="0.82"
      />
    </svg>
  </span>
);

export const LandingPage: React.FC = () => {
  const { lang = 'tr' } = useParams<{ lang: SupportedLang }>();
  const currentLang = (['tr', 'en', 'ar'].includes(lang) ? lang : 'tr') as SupportedLang;
  const t = translations[currentLang];
  const isRtl = currentLang === 'ar';

  return (
    <div className={`sentra-layout ${isRtl ? 'rtl' : ''}`}>
      {/* HEADER */}
      <header className="header">
        <div className="header-inner">
          <Link to={`/${currentLang}`} className="logo" aria-label="Sentra">
            <img
              src="/sentra-logo.png"
              alt="SENTRA"
              style={{ height: '34px', width: 'auto', display: 'block', objectFit: 'contain' }}
            />
          </Link>

          <nav>
            <ul className="nav-links">
              <li><a href="#about-project">{t.nav.aboutProject}</a></li>
              <li><a href="#stack">{t.nav.techStack}</a></li>
              <li><a href="#sustainability">{t.nav.sustainability}</a></li>
              <li><a href="#infocenter">{t.nav.infoCenter}</a></li>
              <li><a href="#about-developer">{t.nav.aboutDeveloper}</a></li>
              <li><a href="#contact">{t.nav.contact}</a></li>
            </ul>
          </nav>

          <div className="header-actions">
            {/* Language Switcher showing TR EN AR in URL link */}
            <div className="lang-switch">
              <Link to="/en" className={currentLang === 'en' ? 'active' : ''}>EN</Link>
              <Link to="/tr" className={currentLang === 'tr' ? 'active' : ''}>TR</Link>
              <Link to="/ar" className={currentLang === 'ar' ? 'active' : ''}>AR</Link>
            </div>
          </div>
        </div>
      </header>

      {/* HERO BANNER */}
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-content">
            <h1>
              {t.hero.titleLine1}<br />
              {t.hero.titleLine2}<br />
              {t.hero.titleLine3}
            </h1>
            <Link to={`/${currentLang}/portal`} className="hero-cta">
              {t.hero.cta}
            </Link>
          </div>
          <div>{/* Visual illustration is anchored to the right of the hero banner */}</div>
        </div>
      </section>

      {/* OVERLAPPING QUICK ACTION CARDS */}
      <section className="quick-actions" id="stack">
        <div className="container">
          <div className="cards-grid">
            <div className="action-card">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
              <h3>{t.actions.card1Title}</h3>
            </div>

            <div className="action-card">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="18" rx="2" />
                <path d="M16 2v4M8 2v4M3 10h18" />
              </svg>
              <h3>{t.actions.card2Title}</h3>
            </div>

            <div className="action-card">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <h3>{t.actions.card3Title}</h3>
            </div>

            <div className="action-card">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
                <line x1="8" y1="2" x2="8" y2="18" />
                <line x1="16" y1="6" x2="16" y2="22" />
              </svg>
              <h3>{t.actions.card4Title}</h3>
            </div>

            <div className="action-card">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
              <h3>{t.actions.card5Title}</h3>
            </div>
          </div>
        </div>
      </section>

      {/* SYSTEM ARCHITECTURE (ALTERNATING ZIG-ZAG) */}
      <section className="architecture-section" id="about-project">
        <div className="container">
          <div className="section-header">
            <h2>{t.architecture.title}</h2>
            <p>{t.architecture.subtitle}</p>
          </div>

          {/* TIER 1: Edge Perception (Text Left, Visual Right) */}
          <div className="arch-row">
            <div className="arch-content">
              <h3>{t.architecture.tier1Title}</h3>
              <p>
                {t.architecture.tier1Desc
                  .split(/(>95%|%95\+|\+95%)/)
                  .map((part, idx) =>
                    /^(>95%|%95\+|\+95%)$/.test(part) ? (
                      <MarkerHighlight key={idx}>{part}</MarkerHighlight>
                    ) : (
                      <React.Fragment key={idx}>{part}</React.Fragment>
                    )
                  )}
              </p>
              <ul className="arch-specs">
                <li><strong>YOLOv8n (INT8):</strong> {t.architecture.tier1Spec1}</li>
                <li><strong>Ray-Casting PiP:</strong> {t.architecture.tier1Spec2}</li>
              </ul>
            </div>
            <div className="arch-visual arch-visual-flush">
              <EdgePerceptionVisual />
            </div>
          </div>

          {/* TIER 2: Offline Outbox & Crypto (Visual Left, Text Right) */}
          <div className="arch-row arch-row-reverse">
            <div className="arch-content">
              <h3>{t.architecture.tier2Title}</h3>
              <p>
                {t.architecture.tier2Desc
                  .split(/(NO)/)
                  .map((part, idx) =>
                    part === 'NO' ? (
                      <span key={idx} className="marker-highlight">
                        {part}
                      </span>
                    ) : (
                      <React.Fragment key={idx}>{part}</React.Fragment>
                    )
                  )}
              </p>
              <ul className="arch-specs">
                <li><strong>AES-256-GCM:</strong> {t.architecture.tier2Spec1}</li>
                <li><strong>SQLite WAL Outbox:</strong> {t.architecture.tier2Spec2}</li>
              </ul>
            </div>
            <div className="arch-visual arch-visual-flush">
              <NetworkResilienceVisual />
            </div>
          </div>

          {/* TIER 3: Command Center & Vault (Text Left, Visual Right) */}
          <div className="arch-row">
            <div className="arch-content">
              <h3>{t.architecture.tier3Title}</h3>
              <p>
                {t.architecture.tier3Desc
                  .split(/(<1s|<1sn|1 ثانية)/)
                  .map((part, idx) =>
                    /^(<1s|<1sn|1 ثانية)$/.test(part) ? (
                      <MarkerHighlight key={idx}>{part}</MarkerHighlight>
                    ) : (
                      <React.Fragment key={idx}>{part}</React.Fragment>
                    )
                  )}
              </p>
              <ul className="arch-specs">
                <li><strong>{t.architecture.tier3Spec3Label}</strong> {t.architecture.tier3Spec3}</li>
                <li><strong>FastAPI + PostgreSQL 16:</strong> {t.architecture.tier3Spec1}</li>
              </ul>
            </div>
            <div className="arch-visual arch-visual-flush">
              <CommandPillarsVisual />
            </div>
          </div>
        </div>
      </section>

      {/* SOCIAL MEDIA FEED SLIDER CARDS */}
      <section className="social-section" id="corporate">
        <div className="container">
          <div className="social-grid">
            <article className="social-card">
              <div className="social-img orange">
                <span>LANDING PAGE UPDATE</span>
              </div>
              <div className="social-inner">
                <p className="social-handle">@sentra</p>
                <span className="social-date">26.11.2026</span>
                <p className="social-excerpt">{t.social.card4Text}</p>
                <a href="#about-project" className="social-more">{t.social.readMore}</a>
              </div>
            </article>

            <article className="social-card">
              <div className="social-img card-custom-bg-3">
                {/* Visual image rendered via background-image from uploaded graphic */}
              </div>
              <div className="social-inner">
                <p className="social-handle">@sentra</p>
                <span className="social-date">15.11.2026</span>
                <p className="social-excerpt">{t.social.card3Text}</p>
                <a href="#about-project" className="social-more">{t.social.readMore}</a>
              </div>
            </article>

            <article className="social-card">
              <div className="social-img card-custom-bg-2">
                {/* Visual image rendered via background-image from uploaded graphic */}
              </div>
              <div className="social-inner">
                <p className="social-handle">@sentra</p>
                <span className="social-date">08.11.2026</span>
                <p className="social-excerpt">{t.social.card2Text}</p>
                <a href="#about-project" className="social-more">{t.social.readMore}</a>
              </div>
            </article>

            <article className="social-card">
              <div className="social-img card-custom-bg">
                {/* Visual image rendered via background-image from uploaded graphic */}
              </div>
              <div className="social-inner">
                <p className="social-handle">@sentraproject</p>
                <span className="social-date">10.10.2026</span>
                <p className="social-excerpt">{t.social.card1Text}</p>
                <a href="#about-project" className="social-more">{t.social.readMore}</a>
              </div>
            </article>
          </div>
        </div>
      </section>

      {/* ABOUT THE DEVELOPER */}
      <section id="about-developer" style={{ padding: '40px 0 80px' }}>
        <div className="container">
          <DeveloperMindMap eyebrow={t.nav.aboutDeveloper} />
        </div>
      </section>

      {/* ANGLED FOOTER */}
      <div className="footer-wrapper" id="contact">
        <div className="floating-triangle"></div>
        <footer className="footer">
          <div className="container">
            <div className="footer-top">
              <div className="footer-col">
                <h4>{t.footer.corporateCol}</h4>
                <ul>
                  <li><a href="#about">{currentLang === 'tr' ? 'Hakkımızda' : currentLang === 'en' ? 'About Us' : 'من نحن'}</a></li>
                  <li><a href="#vision">{currentLang === 'tr' ? 'Misyon, Vizyon ve Değerlerimiz' : currentLang === 'en' ? 'Mission & Vision' : 'الرؤية والرسالة'}</a></li>
                  <li><a href="#history">{currentLang === 'tr' ? 'Tarihçe' : currentLang === 'en' ? 'History' : 'تاريخنا'}</a></li>
                  <li><a href="#careers">{currentLang === 'tr' ? 'Kariyer' : currentLang === 'en' ? 'Careers' : 'الوظائف'}</a></li>
                  <li><a href="#board">{currentLang === 'tr' ? 'Yönetim Kurulu' : currentLang === 'en' ? 'Board of Directors' : 'مجلس الإدارة'}</a></li>
                </ul>
              </div>

              <div className="footer-col">
                <h4>{t.footer.investorCol}</h4>
                <ul>
                  <li><a href="#financials">{currentLang === 'tr' ? 'Finansal Raporlar' : currentLang === 'en' ? 'Financial Reports' : 'التقارير المالية'}</a></li>
                  <li><a href="#announcements">{currentLang === 'tr' ? 'KAP Bildirimleri' : currentLang === 'en' ? 'Public Disclosures' : 'الإفصاحات'}</a></li>
                </ul>
              </div>

              <div className="footer-col">
                <h4>{t.footer.sustainabilityCol}</h4>
                <ul>
                  <li><a href="#sust-reports">{currentLang === 'tr' ? 'Sürdürülebilirlik Raporlarımız' : currentLang === 'en' ? 'Sustainability Reports' : 'تقارير الاستدامة'}</a></li>
                  <li><a href="#policies">{currentLang === 'tr' ? 'Politikalar' : currentLang === 'en' ? 'Policies' : 'السياسات'}</a></li>
                  <li><a href="#certs">{currentLang === 'tr' ? 'SR Sertifikamız' : currentLang === 'en' ? 'Certificates' : 'الشهادات'}</a></li>
                  <li><a href="#saving">{currentLang === 'tr' ? 'Enerji Tasarrufu' : currentLang === 'en' ? 'Energy Efficiency' : 'كفاءة الطاقة'}</a></li>
                </ul>
              </div>

              <div className="footer-col">
                <h4>{t.footer.infoCol}</h4>
                <ul>
                  <li><a href="#proc">{currentLang === 'tr' ? 'Yeni Bağlantı Süreçleri' : currentLang === 'en' ? 'New Connections' : 'إجراءات التوصيل'}</a></li>
                  <li><Link to={`/${currentLang}/privacy`}>{currentLang === 'tr' ? 'Gizlilik Politikası (KVKK)' : currentLang === 'en' ? 'Privacy & Cookies Policy' : 'سياسة الخصوصية وملفات الارتباط'}</Link></li>
                  <li><a href="#tenders">{currentLang === 'tr' ? 'İhaleler' : currentLang === 'en' ? 'Tenders' : 'المناقصات'}</a></li>
                  <li><a href="#faq">{currentLang === 'tr' ? 'Sıkça Sorulan Sorular' : currentLang === 'en' ? 'FAQs' : 'الأسئلة الشائعة'}</a></li>
                </ul>
              </div>

              <div className="footer-col">
                <h4>{t.footer.mediaCol}</h4>
                <ul>
                  <li><a href="#press">{currentLang === 'tr' ? 'Basın Bültenleri' : currentLang === 'en' ? 'Press Releases' : 'البيانات الصحفية'}</a></li>
                  <li><a href="#gallery">{currentLang === 'tr' ? 'Galeri' : currentLang === 'en' ? 'Media Gallery' : 'معرض الصور'}</a></li>
                  <li><a href="#contact" style={{ fontWeight: 800, display: 'inline-block', marginTop: '8px' }}>{t.nav.contact}</a></li>
                </ul>
              </div>
            </div>

            <div className="footer-bottom">
              <div>
                <img
                  src="/sentra-logo-allwhite.png"
                  alt="SENTRA"
                  style={{ height: '36px', width: 'auto', display: 'block', objectFit: 'contain' }}
                />
              </div>
              <div style={{ fontSize: '13px', opacity: 0.9 }}>{t.footer.rightsReserved}</div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
};
