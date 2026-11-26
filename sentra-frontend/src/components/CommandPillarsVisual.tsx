import React from 'react';

interface PillarCard {
  color: string;
  acronym: string;
  subtitleLine1: string;
  subtitleLine2: string;
  desc: string;
  icon: React.ReactNode;
}

const PILLARS: PillarCard[] = [
  {
    color: '#FF5500',
    acronym: 'LIVE',
    subtitleLine1: 'Real-Time',
    subtitleLine2: 'Feed',
    desc: 'Surfaces verified breaches in <1s via WebSocket streams.',
    icon: (
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#0F172A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9" />
        <path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5" />
        <circle cx="12" cy="12" r="2" />
        <path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5" />
        <path d="M19.1 4.9C23 8.8 23 15.2 19.1 19.1" />
      </svg>
    ),
  },
  {
    color: '#0F172A',
    acronym: 'API',
    subtitleLine1: 'FastAPI &',
    subtitleLine2: 'PG16',
    desc: 'High-concurrency ingest, replay guard, and JSONB zones.',
    icon: (
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#0F172A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="8" y="3" width="8" height="5" rx="1.2" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <path d="M5 16v-2a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v2" />
        <rect x="2.5" y="16" width="5" height="5" rx="1" />
        <rect x="9.5" y="16" width="5" height="5" rx="1" />
        <rect x="16.5" y="16" width="5" height="5" rx="1" />
      </svg>
    ),
  },
  {
    color: '#1E293B',
    acronym: 'VAULT',
    subtitleLine1: 'MinIO',
    subtitleLine2: 'Storage',
    desc: 'Encrypted wide-scene & RoI media with immutable hashes.',
    icon: (
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#0F172A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    ),
  },
  {
    color: '#334155',
    acronym: 'CTRL',
    subtitleLine1: 'Admin',
    subtitleLine2: 'Console',
    desc: 'Interactive geofence drawing, node status, and RBAC.',
    icon: (
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#0F172A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="4,9 12,4 20,9 18,19 6,19" />
        <circle cx="12" cy="11.5" r="2.2" />
        <path d="M12 13.7V16.5" />
      </svg>
    ),
  },
];

export const CommandPillarsVisual: React.FC = () => {
  return (
    <div
      style={{
        width: '100%',
        aspectRatio: '16 / 10',
        backgroundColor: 'transparent',
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '10px',
        direction: 'ltr',
        userSelect: 'none',
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      }}
    >
      {PILLARS.map((card) => (
        <div
          key={card.acronym}
          style={{
            borderRadius: '12px',
            overflow: 'hidden',
            border: '1px solid #E2E8F0',
            backgroundColor: '#FFFFFF',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Top 38%: Solid Colored Header */}
          <div
            style={{
              flex: '0 0 38%',
              backgroundColor: card.color,
              color: '#FFFFFF',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              padding: '10px 8px',
            }}
          >
            <div
              style={{
                fontSize: '22px',
                fontWeight: 800,
                letterSpacing: '-0.02em',
                lineHeight: 1.1,
              }}
            >
              {card.acronym}
            </div>
            <div
              style={{
                fontSize: '11px',
                fontWeight: 600,
                lineHeight: 1.25,
                marginTop: '6px',
                opacity: 0.94,
              }}
            >
              {card.subtitleLine1}
              <br />
              {card.subtitleLine2}
            </div>
          </div>

          {/* Bottom 62%: Pure #FFFFFF Body */}
          <div
            style={{
              flex: '1 1 62%',
              backgroundColor: '#FFFFFF',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              padding: '14px 10px',
              gap: '12px',
            }}
          >
            <div>{card.icon}</div>
            <p
              style={{
                margin: 0,
                fontSize: '10.5px',
                color: '#334155',
                lineHeight: 1.4,
                fontWeight: 500,
              }}
            >
              {card.desc}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
};
