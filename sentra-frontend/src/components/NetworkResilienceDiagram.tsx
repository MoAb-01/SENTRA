import React from 'react';

export const NetworkResilienceDiagram: React.FC = () => {
  return (
    <div
      style={{
        width: '100%',
        aspectRatio: '16 / 10',
        backgroundColor: '#FFFFFF',
        border: '1px solid #E2E8F0',
        borderRadius: '14px',
        overflow: 'hidden',
        direction: 'ltr',
        userSelect: 'none',
        boxShadow: '0 10px 30px rgba(15, 23, 42, 0.05)',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
      }}
    >
      <svg
        viewBox="0 0 640 400"
        style={{ width: '100%', height: '100%', display: 'block' }}
        role="img"
        aria-label="Edge-to-WAN Egress Architecture with AES-256-GCM and SQLite WAL Outbox"
      >
        <defs>
          {/* Subtle architectural dot grid */}
          <pattern id="net-dot-grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="1.5" cy="1.5" r="0.85" fill="#E2E8F0" />
          </pattern>

          {/* Crisp directional arrowheads */}
          <marker
            id="arrow-slate"
            viewBox="0 0 10 10"
            refX="8.5"
            refY="5"
            markerWidth="6.5"
            markerHeight="6.5"
            orient="auto-start-reverse"
          >
            <path d="M 1 1.5 L 8.5 5 L 1 8.5 Z" fill="#0F172A" />
          </marker>
          <marker
            id="arrow-orange"
            viewBox="0 0 10 10"
            refX="8.5"
            refY="5"
            markerWidth="6.5"
            markerHeight="6.5"
            orient="auto-start-reverse"
          >
            <path d="M 1 1.5 L 8.5 5 L 1 8.5 Z" fill="#FF5500" />
          </marker>
        </defs>

        {/* Card Background & Subtle Grid */}
        <rect width="640" height="400" fill="#FFFFFF" />
        <rect x="0" y="48" width="640" height="352" fill="url(#net-dot-grid)" opacity="0.7" />

        {/* 1. HEADER BAR */}
        <rect x="0" y="0" width="640" height="48" fill="#FAFAFA" />
        <line x1="0" y1="48" x2="640" y2="48" stroke="#E2E8F0" strokeWidth="1" />

        {/* Top-left tag */}
        <text
          x="22"
          y="28"
          fill="#0F172A"
          fontSize="10.5"
          fontWeight="700"
          letterSpacing="0.09em"
          fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
        >
          EDGE-TO-WAN EGRESS ARCHITECTURE
        </text>

        {/* Top-right pill */}
        <rect
          x="426"
          y="13"
          width="192"
          height="22"
          rx="11"
          fill="rgba(255, 85, 0, 0.08)"
          stroke="rgba(255, 85, 0, 0.35)"
          strokeWidth="1"
        />
        <text
          x="522"
          y="27.5"
          textAnchor="middle"
          fill="#FF5500"
          fontSize="9.5"
          fontWeight="700"
          letterSpacing="0.06em"
          fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
        >
          AES-256-GCM • SQLITE WAL
        </text>

        {/* 2. PRIMARY PATH (NORMAL DELIVERY) */}
        <text
          x="28"
          y="78"
          fill="#64748B"
          fontSize="9"
          fontWeight="700"
          letterSpacing="0.08em"
          fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
        >
          PRIMARY PATH // NORMAL DELIVERY
        </text>

        {/* Left Node: BREACH PAYLOAD */}
        <g transform="translate(28, 92)">
          <rect
            width="156"
            height="84"
            rx="10"
            fill="#FFFFFF"
            stroke="#CBD5E1"
            strokeWidth="1.5"
          />
          <rect x="12" y="12" width="22" height="22" rx="5" fill="#F1F5F9" />
          <path
            d="M 18 19 H 28 M 18 23 H 28 M 18 27 H 24"
            stroke="#0F172A"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <text
            x="42"
            y="26.5"
            fill="#0F172A"
            fontSize="10.5"
            fontWeight="800"
            letterSpacing="0.04em"
            fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            BREACH PAYLOAD
          </text>
          <line x1="12" y1="44" x2="144" y2="44" stroke="#F1F5F9" strokeWidth="1" />
          <text x="12" y="60" fill="#475569" fontSize="10.5" fontWeight="600">
            Dual-Crop RoI
          </text>
          <text x="12" y="74" fill="#64748B" fontSize="9.5">
            + Verified Event Metadata
          </text>
        </g>

        {/* Arrow: BREACH PAYLOAD -> AES-256-GCM SEAL */}
        <line
          x1="184"
          y1="134"
          x2="226"
          y2="134"
          stroke="#0F172A"
          strokeWidth="1.5"
          markerEnd="url(#arrow-slate)"
        />

        {/* Center Node: AES-256-GCM SEAL (Bordered in #0F172A) */}
        <g transform="translate(230, 88)">
          <rect
            width="180"
            height="92"
            rx="10"
            fill="#FFFFFF"
            stroke="#0F172A"
            strokeWidth="1.75"
          />
          {/* Lock Icon */}
          <rect x="14" y="13" width="22" height="22" rx="5" fill="#0F172A" />
          <rect x="20.5" y="22.5" width="9" height="7" rx="1.2" fill="none" stroke="#FFFFFF" strokeWidth="1.4" />
          <path d="M 22.5 22.5 V 20 A 2.5 2.5 0 0 1 27.5 20 V 22.5" fill="none" stroke="#FFFFFF" strokeWidth="1.4" />
          <text
            x="44"
            y="27.5"
            fill="#0F172A"
            fontSize="10.5"
            fontWeight="800"
            letterSpacing="0.04em"
            fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            AES-256-GCM SEAL
          </text>

          {/* Two Spec Pills */}
          <rect x="14" y="45" width="152" height="17" rx="4" fill="#F8FAFC" stroke="#E2E8F0" strokeWidth="1" />
          <text
            x="22"
            y="56.5"
            fill="#334155"
            fontSize="9"
            fontWeight="600"
            fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            12B Monotonic Nonce
          </text>

          <rect x="14" y="66" width="152" height="17" rx="4" fill="#F8FAFC" stroke="#E2E8F0" strokeWidth="1" />
          <text
            x="22"
            y="77.5"
            fill="#334155"
            fontSize="9"
            fontWeight="600"
            fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            16B Auth Tag (AEAD)
          </text>
        </g>

        {/* Arrow: AES-256-GCM SEAL -> TLS 1.3 UPLINK */}
        <line
          x1="410"
          y1="134"
          x2="452"
          y2="134"
          stroke="#0F172A"
          strokeWidth="1.5"
          markerEnd="url(#arrow-slate)"
        />
        <text
          x="431"
          y="125"
          textAnchor="middle"
          fill="#64748B"
          fontSize="8"
          fontWeight="700"
          fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
        >
          WAN OK
        </text>

        {/* Right Node: TLS 1.3 UPLINK */}
        <g transform="translate(456, 92)">
          <rect
            width="156"
            height="84"
            rx="10"
            fill="#FFFFFF"
            stroke="#CBD5E1"
            strokeWidth="1.5"
          />
          <rect x="12" y="12" width="22" height="22" rx="5" fill="rgba(255, 85, 0, 0.1)" />
          <path
            d="M 23 28 V 18 M 19 21.5 L 23 17.5 L 27 21.5"
            fill="none"
            stroke="#FF5500"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text
            x="42"
            y="26.5"
            fill="#0F172A"
            fontSize="10.5"
            fontWeight="800"
            letterSpacing="0.04em"
            fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            TLS 1.3 UPLINK
          </text>
          <line x1="12" y1="44" x2="144" y2="44" stroke="#F1F5F9" strokeWidth="1" />
          <text x="12" y="60" fill="#475569" fontSize="10.5" fontWeight="600">
            FastAPI Ingest
          </text>
          <text x="12" y="74" fill="#64748B" fontSize="9.5">
            + Monotonic Replay Guard
          </text>
        </g>

        {/* 3. FAILOVER LOOP (WAN BLACKOUT & RECOVERY) */}
        {/* Dashed Orange Failover Branch dropping down from AES-256-GCM SEAL */}
        <path
          d="M 320 180 L 320 242"
          fill="none"
          stroke="#FF5500"
          strokeWidth="1.6"
          strokeDasharray="5 4"
          markerEnd="url(#arrow-orange)"
        />
        {/* WAN: OFFLINE Pill */}
        <rect
          x="212"
          y="200"
          width="96"
          height="20"
          rx="4"
          fill="#FFF7ED"
          stroke="rgba(255, 85, 0, 0.45)"
          strokeWidth="1"
        />
        <text
          x="260"
          y="213.5"
          textAnchor="middle"
          fill="#FF5500"
          fontSize="8.5"
          fontWeight="700"
          letterSpacing="0.05em"
          fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
        >
          WAN: OFFLINE
        </text>

        {/* SQLITE WAL OUTBOX Container */}
        <g transform="translate(86, 248)">
          <rect
            width="368"
            height="122"
            rx="12"
            fill="#FFFFFF"
            stroke="#FF5500"
            strokeWidth="1.5"
          />
          {/* Subtle Orange Top Header Strip */}
          <path
            d="M 1 12 A 11 11 0 0 1 12 1 H 356 A 11 11 0 0 1 367 12 V 34 H 1 Z"
            fill="rgba(255, 85, 0, 0.06)"
          />
          <line x1="1" y1="34" x2="367" y2="34" stroke="rgba(255, 85, 0, 0.22)" strokeWidth="1" />

          {/* Outbox Header Text */}
          <text
            x="16"
            y="21.5"
            fill="#0F172A"
            fontSize="10.5"
            fontWeight="800"
            letterSpacing="0.05em"
            fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            SQLITE WAL OUTBOX
          </text>
          <text
            x="352"
            y="21.5"
            textAnchor="end"
            fill="#64748B"
            fontSize="9"
            fontWeight="600"
            fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            wal_outbox.db • fsync: ON
          </text>

          {/* Three Ordered Queue Slots (SEQ #1042, SEQ #1043, SEQ #1044) */}
          {[
            { seq: 'SEQ #1042', state: 'SEALED • READY', x: 16 },
            { seq: 'SEQ #1043', state: 'SEALED • QUEUED', x: 132 },
            { seq: 'SEQ #1044', state: 'SEALED • QUEUED', x: 248 },
          ].map((slot, idx) => (
            <g key={slot.seq} transform={`translate(${slot.x}, 48)`}>
              <rect
                width="104"
                height="56"
                rx="7"
                fill={idx === 0 ? '#FFF7ED' : '#F8FAFC'}
                stroke={idx === 0 ? '#FF5500' : '#CBD5E1'}
                strokeWidth={idx === 0 ? '1.35' : '1.15'}
              />
              <text
                x="10"
                y="21"
                fill="#0F172A"
                fontSize="10"
                fontWeight="800"
                fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
              >
                {slot.seq}
              </text>
              <line x1="10" y1="29" x2="94" y2="29" stroke={idx === 0 ? 'rgba(255,85,0,0.2)' : '#E2E8F0'} strokeWidth="1" />
              <text
                x="10"
                y="43"
                fill={idx === 0 ? '#FF5500' : '#64748B'}
                fontSize="8"
                fontWeight="700"
                fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
              >
                {slot.state}
              </text>
            </g>
          ))}
        </g>

        {/* Solid Orange FIFO AUTO-FLUSH ON RECONNECT Return Arrow back up to TLS 1.3 UPLINK */}
        <path
          d="M 454 309 L 534 309 Q 546 309 546 297 L 546 182"
          fill="none"
          stroke="#FF5500"
          strokeWidth="1.75"
          markerEnd="url(#arrow-orange)"
        />

        {/* Label along Recovery Arrow */}
        <text
          x="534"
          y="236"
          textAnchor="end"
          fill="#FF5500"
          fontSize="8.5"
          fontWeight="800"
          letterSpacing="0.04em"
          fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
        >
          FIFO AUTO-FLUSH
        </text>
        <text
          x="534"
          y="248"
          textAnchor="end"
          fill="#64748B"
          fontSize="8"
          fontWeight="700"
          letterSpacing="0.04em"
          fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
        >
          ON RECONNECT
        </text>

        {/* Subtle 0% DATA LOSS Badge */}
        <g transform="translate(486, 332)">
          <rect
            width="126"
            height="28"
            rx="14"
            fill="#FFFFFF"
            stroke="#FF5500"
            strokeWidth="1.25"
          />
          <circle cx="15" cy="14" r="3.5" fill="#FF5500" />
          <text
            x="26"
            y="17.5"
            fill="#0F172A"
            fontSize="9.5"
            fontWeight="800"
            letterSpacing="0.05em"
            fontFamily="'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            0% DATA LOSS
          </text>
        </g>
      </svg>
    </div>
  );
};
