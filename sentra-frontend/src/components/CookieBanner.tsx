import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { SupportedLang } from '../i18n';

const STORAGE_KEY = 'sentra_cookie_ack';

const BANNER_COPY: Record<
  SupportedLang,
  {
    badge: string;
    message: string;
    policyLink: string;
    acceptBtn: string;
  }
> = {
  en: {
    badge: 'NO TRACKING COOKIES',
    message:
      'This landing page does not collect personal data or use tracking cookies. Dismissing this notice saves one local preference in your browser.',
    policyLink: 'Privacy Policy',
    acceptBtn: 'Got it',
  },
  tr: {
    badge: 'İZLEME ÇEREZİ YOK',
    message:
      'Bu açılış sayfası kişisel veri toplamaz ve izleme çerezi kullanmaz. Bu bildirimi kapattığınızda yalnızca tarayıcınızda tek bir yerel tercih kaydedilir.',
    policyLink: 'Gizlilik Politikası',
    acceptBtn: 'Anladım',
  },
  ar: {
    badge: 'لا ملفات تتبع',
    message:
      'لا تجمع هذه الصفحة بيانات شخصية ولا تستخدم ملفات تتبع. يؤدي إغلاق هذا الإشعار إلى حفظ تفضيل محلي واحد فقط في متصفحك.',
    policyLink: 'سياسة الخصوصية',
    acceptBtn: 'حسناً',
  },
};

interface CookieBannerProps {
  lang: SupportedLang;
}

export const CookieBanner: React.FC<CookieBannerProps> = ({ lang }) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) !== '1') {
        setVisible(true);
      }
    } catch {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  const copy = BANNER_COPY[lang];
  const isRtl = lang === 'ar';

  const handleDismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      // ignore storage errors in private browsing modes
    }
    setVisible(false);
  };

  return (
    <aside
      role="dialog"
      aria-label={copy.policyLink}
      style={{
        position: 'fixed',
        bottom: '20px',
        left: isRtl ? '20px' : 'auto',
        right: isRtl ? 'auto' : '20px',
        maxWidth: '390px',
        width: 'calc(100% - 40px)',
        backgroundColor: '#FFFFFF',
        border: '1px solid #E2E8F0',
        borderRadius: '14px',
        padding: '16px 18px',
        boxShadow: '0 16px 40px rgba(15, 23, 42, 0.14)',
        zIndex: 1000,
        direction: isRtl ? 'rtl' : 'ltr',
        textAlign: isRtl ? 'right' : 'left',
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '7px',
          fontSize: '10px',
          fontWeight: 800,
          letterSpacing: '0.08em',
          color: 'var(--brand-orange)',
          marginBottom: '8px',
        }}
      >
        <span
          style={{
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            backgroundColor: 'var(--brand-orange)',
          }}
        />
        <span>{copy.badge}</span>
      </div>

      <p style={{ fontSize: '13px', color: '#334155', lineHeight: 1.55, marginBottom: '14px' }}>
        {copy.message}
      </p>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
        <Link
          to={`/${lang}/privacy`}
          style={{
            fontSize: '12.5px',
            fontWeight: 700,
            color: '#475569',
            textDecoration: 'underline',
          }}
        >
          {copy.policyLink}
        </Link>

        <button
          type="button"
          onClick={handleDismiss}
          style={{
            background: 'var(--brand-orange)',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '999px',
            padding: '7px 18px',
            fontSize: '12.5px',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          {copy.acceptBtn}
        </button>
      </div>
    </aside>
  );
};
