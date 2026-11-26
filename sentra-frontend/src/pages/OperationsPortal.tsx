import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { translations, SupportedLang } from '../i18n';
import { auth } from '../services/auth';
import { ShieldCheck, RefreshCw, AlertTriangle, Activity, Wifi, Server, LogOut, CheckCircle2 } from 'lucide-react';

export const OperationsPortal: React.FC = () => {
  const { lang = 'tr' } = useParams<{ lang: SupportedLang }>();
  const currentLang = (['tr', 'en', 'ar'].includes(lang) ? lang : 'tr') as SupportedLang;
  const t = translations[currentLang];
  const isRtl = currentLang === 'ar';

  const [isAuth, setIsAuth] = useState(auth.isAuthenticated());
  const [tokenTimeLeft, setTokenTimeLeft] = useState(auth.getExpiresInSeconds());
  const [isRenewing, setIsRenewing] = useState(false);
  const [loginUser, setLoginUser] = useState('admin');
  const [notification, setNotification] = useState<string | null>(null);

  // Synchronize authentication status & timer
  useEffect(() => {
    const unsub = auth.subscribe((authStatus) => {
      setIsAuth(authStatus);
    });

    const interval = setInterval(() => {
      setTokenTimeLeft(auth.getExpiresInSeconds());
    }, 1000);

    return () => {
      unsub();
      clearInterval(interval);
    };
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    await auth.login(loginUser, 'ADMIN');
    setNotification('Giriş başarılı! Kısa ömürlü Erişim Tokeni belleğe alındı.');
    setTimeout(() => setNotification(null), 4000);
  };

  const handleManualRenew = async () => {
    setIsRenewing(true);
    await auth.silentRenew();
    setIsRenewing(false);
    setNotification('Token Rotasyonu Başarılı: Yeni Erişim ve Yenileme Tokeni oluşturuldu.');
    setTimeout(() => setNotification(null), 4000);
  };

  const handleLogout = () => {
    auth.logout();
  };

  return (
    <div className={`portal-container ${isRtl ? 'rtl' : ''}`} style={{ padding: '40px 20px', minHeight: '80vh' }}>
      <div className="container">
        {/* Breadcrumb & Navigation Back */}
        <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Link to={`/${currentLang}`} style={{ color: 'var(--brand-orange)', fontWeight: 700, fontSize: '14px' }}>
              ← {currentLang === 'tr' ? 'Ana Sayfaya Dön' : currentLang === 'en' ? 'Back to Landing' : 'العودة للرئيسية'}
            </Link>
            <h1 style={{ fontSize: '28px', fontWeight: 800, marginTop: '8px', color: '#1F2937' }}>
              {t.portal.title}
            </h1>
            <p style={{ color: '#6B7280', fontSize: '15px' }}>{t.portal.subtitle}</p>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            {(['tr', 'en', 'ar'] as SupportedLang[]).map((l) => (
              <Link
                key={l}
                to={`/${l}/portal`}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: 700,
                  background: l === currentLang ? 'var(--brand-orange)' : '#E5E7EB',
                  color: l === currentLang ? '#fff' : '#4B5563',
                  textTransform: 'uppercase',
                }}
              >
                {l}
              </Link>
            ))}
          </div>
        </div>

        {notification && (
          <div style={{
            background: '#DEF7EC',
            color: '#03543F',
            border: '1px solid #BCF0DA',
            padding: '12px 18px',
            borderRadius: '8px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '14px',
            fontWeight: 600
          }}>
            <CheckCircle2 size={18} /> {notification}
          </div>
        )}

        {/* Security Rule Dual-Token Panel */}
        <div style={{
          background: '#FFFFFF',
          border: '1px solid #E5E7EB',
          borderRadius: '12px',
          padding: '24px',
          marginBottom: '32px',
          boxShadow: '0 4px 15px rgba(0,0,0,0.04)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div style={{
                background: isAuth ? '#ECFDF5' : '#FEF2F2',
                color: isAuth ? '#059669' : '#DC2626',
                padding: '12px',
                borderRadius: '10px'
              }}>
                <ShieldCheck size={28} />
              </div>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#111827' }}>
                  {t.portal.authStatus}: {isAuth ? <span style={{ color: '#059669' }}>Aktif (Oturum Açık)</span> : <span style={{ color: '#DC2626' }}>Yetkisiz / Kapalı</span>}
                </h3>
                <p style={{ fontSize: '13px', color: '#6B7280' }}>
                  Çift-Token Mimarisi: Kısa ömürlü Bellek İçi Token (15 dk) + Dönen Yenileme Tokeni (Rotated Refresh Token)
                </p>
              </div>
            </div>

            {isAuth ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div style={{ textAlign: isRtl ? 'left' : 'right' }}>
                  <span style={{ fontSize: '12px', color: '#9CA3AF', display: 'block' }}>{t.portal.tokenExpiry}</span>
                  <span style={{ fontSize: '16px', fontWeight: 800, color: tokenTimeLeft < 60 ? '#EF4444' : '#10B981' }}>
                    {Math.floor(tokenTimeLeft / 60)}m {tokenTimeLeft % 60}s
                  </span>
                </div>
                <button
                  onClick={handleManualRenew}
                  disabled={isRenewing}
                  style={{
                    background: '#F3F4F6',
                    border: '1px solid #D1D5DB',
                    color: '#374151',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <RefreshCw size={14} className={isRenewing ? 'spin' : ''} />
                  {t.portal.renewTokenManual}
                </button>
                <button
                  onClick={handleLogout}
                  style={{
                    background: '#FEE2E2',
                    border: '1px solid #FECACA',
                    color: '#B91C1C',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <LogOut size={14} />
                  {t.nav.logout}
                </button>
              </div>
            ) : (
              <form onSubmit={handleLogin} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input
                  type="text"
                  value={loginUser}
                  onChange={(e) => setLoginUser(e.target.value)}
                  placeholder="Kullanıcı Adı"
                  style={{
                    padding: '8px 12px',
                    border: '1px solid #D1D5DB',
                    borderRadius: '6px',
                    fontSize: '13px'
                  }}
                />
                <button
                  type="submit"
                  style={{
                    background: 'var(--brand-orange)',
                    color: '#FFF',
                    border: 'none',
                    padding: '8px 18px',
                    borderRadius: '6px',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  {t.nav.login}
                </button>
              </form>
            )}
          </div>
        </div>

        {/* Real-time Dashboard KPI Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '32px' }}>
          <div style={{ background: '#FFF', padding: '20px', borderRadius: '12px', border: '1px solid #E5E7EB', boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#6B7280', fontSize: '13px', fontWeight: 600 }}>
              <span>{t.portal.gridStability}</span>
              <Activity size={18} color="#10B981" />
            </div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#111827', marginTop: '10px' }}>99.98%</div>
            <div style={{ fontSize: '12px', color: '#10B981', marginTop: '4px' }}>↑ Normal Operasyon Aralığı</div>
          </div>

          <div style={{ background: '#FFF', padding: '20px', borderRadius: '12px', border: '1px solid #E5E7EB', boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#6B7280', fontSize: '13px', fontWeight: 600 }}>
              <span>{t.portal.activeIncidents}</span>
              <AlertTriangle size={18} color="#F59E0B" />
            </div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#D97706', marginTop: '10px' }}>3</div>
            <div style={{ fontSize: '12px', color: '#6B7280', marginTop: '4px' }}>2 İkincil Uyarı, 1 Bakım</div>
          </div>

          <div style={{ background: '#FFF', padding: '20px', borderRadius: '12px', border: '1px solid #E5E7EB', boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#6B7280', fontSize: '13px', fontWeight: 600 }}>
              <span>{t.portal.activeNodes}</span>
              <Server size={18} color="#3B82F6" />
            </div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#111827', marginTop: '10px' }}>1,482</div>
            <div style={{ fontSize: '12px', color: '#3B82F6', marginTop: '4px' }}>14 Bölgesel Trafo Merkezi</div>
          </div>

          <div style={{ background: '#FFF', padding: '20px', borderRadius: '12px', border: '1px solid #E5E7EB', boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#6B7280', fontSize: '13px', fontWeight: 600 }}>
              <span>{t.portal.telemetryRate}</span>
              <Wifi size={18} color="#8B5CF6" />
            </div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#111827', marginTop: '10px' }}>24.6k/s</div>
            <div style={{ fontSize: '12px', color: '#8B5CF6', marginTop: '4px' }}>Uç Nokta Veri Akışı</div>
          </div>
        </div>

        {/* Live Incident & Telemetry Stream */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
          <div style={{ background: '#FFF', borderRadius: '12px', border: '1px solid #E5E7EB', padding: '24px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '16px', color: '#1F2937' }}>
              {t.portal.incidentFeed}
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ padding: '14px', borderLeft: '4px solid #10B981', background: '#F9FAFB', borderRadius: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#6B7280' }}>
                  <span>TRAFO-İZMİR-042</span>
                  <span>10:24:15</span>
                </div>
                <div style={{ fontWeight: 700, fontSize: '14px', marginTop: '4px' }}>Yük Dengeleme Optimizasyonu Tamamlandı</div>
                <div style={{ fontSize: '12px', color: '#4B5563', marginTop: '2px' }}>Reaktif güç katsayısı nominal seviyeye çekildi.</div>
              </div>

              <div style={{ padding: '14px', borderLeft: '4px solid #F59E0B', background: '#F9FAFB', borderRadius: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#6B7280' }}>
                  <span>ŞEBEKE-MANİSA-11</span>
                  <span>09:58:02</span>
                </div>
                <div style={{ fontWeight: 700, fontSize: '14px', marginTop: '4px' }}>Planlı Hat Bakımı Devam Ediyor</div>
                <div style={{ fontSize: '12px', color: '#4B5563', marginTop: '2px' }}>Yedek hat üzerinden besleme kesintisiz sürdürülüyor.</div>
              </div>

              <div style={{ padding: '14px', borderLeft: '4px solid #3B82F6', background: '#F9FAFB', borderRadius: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#6B7280' }}>
                  <span>SENTRA-EDGE-NODE-08</span>
                  <span>09:12:44</span>
                </div>
                <div style={{ fontWeight: 700, fontSize: '14px', marginTop: '4px' }}>Yazılım ve Güvenlik Sertifikası Güncellendi</div>
                <div style={{ fontSize: '12px', color: '#4B5563', marginTop: '2px' }}>Kriptografik anahtar rotasyonu başarıyla işlendi.</div>
              </div>
            </div>
          </div>

          {/* Quick Dispatch Controls */}
          <div style={{ background: '#FFF', borderRadius: '12px', border: '1px solid #E5E7EB', padding: '24px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '16px', color: '#1F2937' }}>
              {t.portal.actionsHeader}
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <button
                disabled={!isAuth}
                style={{
                  padding: '12px',
                  background: isAuth ? 'var(--brand-orange)' : '#E5E7EB',
                  color: isAuth ? '#FFF' : '#9CA3AF',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 700,
                  fontSize: '13px',
                  cursor: isAuth ? 'pointer' : 'not-allowed',
                  textAlign: 'center'
                }}
              >
                {t.portal.dispatchUnit}
              </button>
              <button
                disabled={!isAuth}
                style={{
                  padding: '12px',
                  background: isAuth ? '#1F2937' : '#E5E7EB',
                  color: isAuth ? '#FFF' : '#9CA3AF',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 700,
                  fontSize: '13px',
                  cursor: isAuth ? 'pointer' : 'not-allowed',
                  textAlign: 'center'
                }}
              >
                {t.portal.securityAudit}
              </button>
              {!isAuth && (
                <p style={{ fontSize: '12px', color: '#EF4444', textAlign: 'center', marginTop: '8px' }}>
                  * {t.portal.loginPrompt}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
