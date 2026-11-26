import React from 'react';

export const CommandCenterVisual: React.FC = () => {
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '16 / 10',
        borderRadius: '16px',
        backgroundColor: '#F8FAFC',
        border: '1px solid #E2E8F0',
        overflow: 'hidden',
        direction: 'ltr',
        userSelect: 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: '0 12px 32px rgba(15, 23, 42, 0.04)',
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Subtle Architectural Dot Grid */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: 'radial-gradient(#CBD5E1 1px, transparent 1px)',
          backgroundSize: '20px 20px',
          opacity: 0.55,
          pointerEvents: 'none',
        }}
      />

      {/* Left Panel: Geospatial Polygon View (Architectural Vector Floorplan) */}
      <div
        style={{
          position: 'relative',
          width: '58%',
          height: '82%',
          marginLeft: '-26%',
          borderRadius: '12px',
          backgroundColor: '#FFFFFF',
          border: '1px solid #E2E8F0',
          boxShadow: '0 8px 24px rgba(15, 23, 42, 0.05)',
          overflow: 'hidden',
          zIndex: 2,
        }}
      >
        <svg viewBox="0 0 360 280" style={{ width: '100%', height: '100%', display: 'block' }}>
          {/* Subtle Architectural Floorplan Grid & Walls */}
          <g stroke="#E2E8F0" strokeWidth="1">
            <line x1="0" y1="70" x2="360" y2="70" />
            <line x1="0" y1="140" x2="360" y2="140" />
            <line x1="0" y1="210" x2="360" y2="210" />
            <line x1="90" y1="0" x2="90" y2="280" />
            <line x1="180" y1="0" x2="180" y2="280" />
            <line x1="270" y1="0" x2="270" y2="280" />
          </g>

          {/* Building Footprint & Perimeter Walls */}
          <g fill="#F8FAFC" stroke="#CBD5E1" strokeWidth="1.5">
            <rect x="34" y="36" width="118" height="74" rx="2" />
            <rect x="174" y="36" width="146" height="62" rx="2" />
            <rect x="34" y="132" width="84" height="108" rx="2" />
          </g>

          {/* Translucent #FF5500 Perimeter Polygon */}
          <polygon
            points="138,118 292,110 318,216 146,232"
            fill="rgba(255, 85, 0, 0.12)"
            stroke="#FF5500"
            strokeWidth="2"
            strokeLinejoin="round"
          />

          {/* Polygon Vertices */}
          {[
            { x: 138, y: 118 },
            { x: 292, y: 110 },
            { x: 318, y: 216 },
            { x: 146, y: 232 },
          ].map((pt, i) => (
            <circle key={i} cx={pt.x} cy={pt.y} r="3.5" fill="#FFFFFF" stroke="#FF5500" strokeWidth="1.75" />
          ))}

          {/* Active Breach Pin (CAM-04) */}
          <g transform="translate(214, 166)">
            <circle cx="0" cy="0" r="14" fill="rgba(255, 85, 0, 0.16)" />
            <circle cx="0" cy="0" r="5.5" fill="#FF5500" stroke="#FFFFFF" strokeWidth="1.75" />
            <rect x="10" y="-11" width="54" height="18" rx="4" fill="#0F172A" />
            <text
              x="37"
              y="1"
              textAnchor="middle"
              fill="#FFFFFF"
              fontSize="8.5"
              fontWeight="700"
              fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
            >
              CAM-04
            </text>
          </g>
        </svg>
      </div>

      {/* Right Panel: Matte-Dark Evidence Vault Card (#0F172A) floating slightly forward */}
      <div
        style={{
          position: 'relative',
          width: '50%',
          marginLeft: '-10%',
          marginTop: '14px',
          borderRadius: '14px',
          backgroundColor: '#0F172A',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          boxShadow: '0 24px 48px -12px rgba(15, 23, 42, 0.34), 0 0 0 1px rgba(15, 23, 42, 0.08)',
          padding: '16px',
          color: '#F8FAFC',
          zIndex: 5,
        }}
      >
        {/* Two Side-by-Side Placeholder Frames */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '10px',
            marginBottom: '14px',
          }}
        >
          {/* WIDE SCENE */}
          <div
            style={{
              aspectRatio: '4 / 3',
              borderRadius: '8px',
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.10)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '8px',
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="1.6">
              <rect x="3" y="5" width="18" height="14" rx="2" />
              <circle cx="8.5" cy="10.5" r="1.5" />
              <path d="M21 15l-5-5L5 19" />
            </svg>
            <span
              style={{
                fontFamily: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
                fontSize: '8.5px',
                fontWeight: 700,
                color: '#94A3B8',
                letterSpacing: '0.05em',
              }}
            >
              WIDE SCENE
            </span>
          </div>

          {/* UPPER-BODY ROI */}
          <div
            style={{
              aspectRatio: '4 / 3',
              borderRadius: '8px',
              backgroundColor: 'rgba(255, 85, 0, 0.08)',
              border: '1px solid rgba(255, 85, 0, 0.32)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '8px',
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FF5500" strokeWidth="1.6">
              <path d="M4 8V6a2 2 0 0 1 2-2h2" />
              <path d="M16 4h2a2 2 0 0 1 2 2v2" />
              <path d="M20 16v2a2 2 0 0 1-2 2h-2" />
              <path d="M8 20H6a2 2 0 0 1-2-2v-2" />
              <circle cx="12" cy="10" r="2.5" />
              <path d="M8.5 17a3.5 3.5 0 0 1 7 0" />
            </svg>
            <span
              style={{
                fontFamily: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
                fontSize: '8.5px',
                fontWeight: 700,
                color: '#FF5500',
                letterSpacing: '0.05em',
              }}
            >
              UPPER-BODY ROI
            </span>
          </div>
        </div>

        {/* Minimal #FF5500 DECRYPTED • VERIFIED Badge */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '7px',
            padding: '7px 10px',
            borderRadius: '8px',
            backgroundColor: 'rgba(255, 85, 0, 0.12)',
            border: '1px solid rgba(255, 85, 0, 0.35)',
            fontFamily: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: '9.5px',
            fontWeight: 700,
            color: '#FF5500',
            letterSpacing: '0.06em',
          }}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: '#FF5500',
            }}
          />
          <span>DECRYPTED • VERIFIED</span>
        </div>
      </div>
    </div>
  );
};
