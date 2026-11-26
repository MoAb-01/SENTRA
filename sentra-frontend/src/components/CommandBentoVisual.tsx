import React from 'react';

export const CommandBentoVisual: React.FC = () => {
  return (
    <div
      style={{
        width: '100%',
        aspectRatio: '16 / 10',
        borderRadius: '16px',
        backgroundColor: '#F8FAFC',
        border: '1px solid #E2E8F0',
        padding: '16px',
        display: 'grid',
        gridTemplateColumns: '1.15fr 0.85fr',
        gridTemplateRows: '1fr 1fr',
        gap: '12px',
        direction: 'ltr',
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        boxShadow: '0 12px 32px rgba(15, 23, 42, 0.04)',
      }}
    >
      {/* Block 1: Live WebSocket Incident Feed */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          border: '1px solid #E2E8F0',
          borderRadius: '12px',
          padding: '14px 16px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '9.5px',
              fontWeight: 700,
              color: '#64748B',
              letterSpacing: '0.05em',
            }}
          >
            LIVE INCIDENT FEED
          </span>
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '9.5px',
              fontWeight: 700,
              color: '#FF5500',
              backgroundColor: 'rgba(255, 85, 0, 0.08)',
              padding: '2px 7px',
              borderRadius: '5px',
            }}
          >
            WS • &lt;1s
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '7px', marginTop: '8px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 10px',
              borderRadius: '8px',
              backgroundColor: 'rgba(255, 85, 0, 0.05)',
              border: '1px solid rgba(255, 85, 0, 0.25)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  backgroundColor: '#FF5500',
                }}
              />
              <span style={{ fontSize: '11.5px', fontWeight: 700, color: '#0F172A' }}>
                Perimeter Breach
              </span>
            </div>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '9.5px',
                fontWeight: 600,
                color: '#FF5500',
              }}
            >
              CAM-04
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '7px 10px',
              borderRadius: '8px',
              backgroundColor: '#F8FAFC',
              border: '1px solid #E2E8F0',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: '#10B981',
                }}
              />
              <span style={{ fontSize: '11px', fontWeight: 500, color: '#475569' }}>
                Node Heartbeat OK
              </span>
            </div>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '9.5px',
                color: '#94A3B8',
              }}
            >
              4/4 ONLINE
            </span>
          </div>
        </div>
      </div>

      {/* Block 2: Matte-Dark MinIO Encrypted Evidence Vault */}
      <div
        style={{
          backgroundColor: '#0F172A',
          borderRadius: '12px',
          padding: '14px 15px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          color: '#FFFFFF',
          boxShadow: '0 8px 20px rgba(15, 23, 42, 0.14)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '9.5px',
              fontWeight: 700,
              color: '#94A3B8',
              letterSpacing: '0.05em',
            }}
          >
            MINIO VAULT
          </span>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#FF5500" strokeWidth="2.2">
            <rect x="4" y="11" width="16" height="10" rx="2" />
            <path d="M8 11V7a4 4 0 0 1 8 0v4" />
          </svg>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', margin: '8px 0' }}>
          <div
            style={{
              borderRadius: '7px',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              padding: '10px 6px',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '9px', fontWeight: 600, color: '#CBD5E1' }}>Wide Scene</div>
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '8px',
                color: '#64748B',
                marginTop: '2px',
              }}
            >
              ENCRYPTED
            </div>
          </div>
          <div
            style={{
              borderRadius: '7px',
              backgroundColor: 'rgba(255, 85, 0, 0.12)',
              border: '1px solid rgba(255, 85, 0, 0.35)',
              padding: '10px 6px',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '9px', fontWeight: 700, color: '#FF5500' }}>Subject RoI</div>
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '8px',
                color: '#FDBA74',
                marginTop: '2px',
              }}
            >
              DECRYPTED
            </div>
          </div>
        </div>

        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '9px',
            color: '#10B981',
            fontWeight: 600,
          }}
        >
          ✓ SHA-256 AUDIT VERIFIED
        </div>
      </div>

      {/* Block 3: Geofence Polygon Control */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          border: '1px solid #E2E8F0',
          borderRadius: '12px',
          padding: '14px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%' }}>
          <div>
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '9.5px',
                fontWeight: 700,
                color: '#64748B',
                letterSpacing: '0.05em',
              }}
            >
              GEOFENCE CONTROL
            </div>
            <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#0F172A', marginTop: '4px' }}>
              Zone Polygons
            </div>
          </div>
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '9.5px',
              color: '#64748B',
            }}
          >
            PostgreSQL JSONB
          </div>
        </div>

        {/* Crisp Interactive Vertex Polygon Graphic */}
        <svg width="96" height="68" viewBox="0 0 96 68" fill="none">
          <polygon
            points="16,14 78,10 86,52 24,58"
            fill="rgba(255, 85, 0, 0.1)"
            stroke="#FF5500"
            strokeWidth="1.8"
          />
          <circle cx="16" cy="14" r="3.5" fill="#FFFFFF" stroke="#FF5500" strokeWidth="2" />
          <circle cx="78" cy="10" r="3.5" fill="#FFFFFF" stroke="#FF5500" strokeWidth="2" />
          <circle cx="86" cy="52" r="3.5" fill="#FFFFFF" stroke="#FF5500" strokeWidth="2" />
          <circle cx="24" cy="58" r="3.5" fill="#FFFFFF" stroke="#FF5500" strokeWidth="2" />
        </svg>
      </div>

      {/* Block 4: FastAPI & RBAC Control */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          border: '1px solid #E2E8F0',
          borderRadius: '12px',
          padding: '14px 15px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}
      >
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '9.5px',
            fontWeight: 700,
            color: '#64748B',
            letterSpacing: '0.05em',
          }}
        >
          ADMIN &amp; RBAC
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: '#334155', fontWeight: 600 }}>Replay Guard</span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: '#10B981', fontWeight: 700 }}>
              ACTIVE
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: '#334155', fontWeight: 600 }}>Operator Roles</span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: '#0F172A', fontWeight: 700 }}>
              RBAC
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: '#334155', fontWeight: 600 }}>Ingest API</span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: '#FF5500', fontWeight: 700 }}>
              200 OK
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
