import React, { useEffect, useState } from 'react';

interface Point {
  x: number;
  y: number;
}

// Isometric restricted zone polygon on the ground (640x380 viewBox)
const ZONE_POLY: Point[] = [
  { x: 255, y: 155 },
  { x: 430, y: 105 },
  { x: 525, y: 185 },
  { x: 350, y: 245 },
];

const ZONE_STR = ZONE_POLY.map((p) => `${p.x},${p.y}`).join(' ');

// Real Ray-Casting Point-in-Polygon check
function castRay(pt: Point, poly: Point[]): { inside: boolean; hits: Point[] } {
  const hits: Point[] = [];
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i];
    const b = poly[j];
    if ((a.y > pt.y) !== (b.y > pt.y)) {
      const ix = a.x + ((pt.y - a.y) * (b.x - a.x)) / (b.y - a.y);
      if (ix > pt.x) hits.push({ x: ix, y: pt.y });
    }
  }
  return { inside: hits.length % 2 === 1, hits };
}

// Smooth isometric walking path: outside -> crosses fence -> deep inside -> loops
const PATH_START: Point = { x: 155, y: 248 };
const PATH_END: Point = { x: 405, y: 168 };

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

const STEPS = [
  {
    id: 1,
    title: 'Edge detection active',
    desc: 'YOLOv8n tracks ground contact (xb, yb). Ray-casting confirms target is outside.',
    tRange: [0, 0.36],
  },
  {
    id: 2,
    title: 'Virtual fence breached',
    desc: 'Odd ray intersection detected. 3-frame temporal filter suppresses false positives.',
    tRange: [0.36, 0.72],
  },
  {
    id: 3,
    title: 'Dual-crop evidence queued',
    desc: 'Wide scene + upper-body RoI extracted and encrypted for zero-loss transmission.',
    tRange: [0.72, 1.0],
  },
];

export const EdgePerceptionVisual: React.FC = () => {
  const [progress, setProgress] = useState(0); // 0 to 1
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    let rafId: number;
    let last = performance.now();

    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setProgress((prev) => (prev + dt * 0.14) % 1); // ~7s full cycle
      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [paused]);

  // Ease out near the end so step 3 holds cleanly before looping
  const moveT = Math.min(1, progress / 0.85);
  const pos: Point = {
    x: lerp(PATH_START.x, PATH_END.x, moveT),
    y: lerp(PATH_START.y, PATH_END.y, moveT),
  };

  const { inside, hits } = castRay(pos, ZONE_POLY);
  const activeStep = progress < 0.36 ? 1 : progress < 0.72 ? 2 : 3;
  const confirmed = activeStep === 3;
  const framesCount = !inside ? 0 : activeStep === 3 ? 3 : progress > 0.56 ? 2 : 1;

  // Subtle walking bob
  const bob = moveT < 1 ? Math.abs(Math.sin(progress * 42)) * 2.5 : 0;

  const jumpToStep = (stepId: number) => {
    const targetT = stepId === 1 ? 0.15 : stepId === 2 ? 0.52 : 0.86;
    setProgress(targetT);
  };

  return (
    <div
      style={{
        width: '100%',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        direction: 'ltr',
        userSelect: 'none',
      }}
    >
      {/* Seamless Light-Mode Isometric Viewport */}
      <div style={{ position: 'relative', width: '100%', aspectRatio: '16 / 10' }}>
        <svg
          viewBox="0 0 640 380"
          style={{ width: '100%', height: '100%', display: 'block', overflow: 'visible' }}
        >
          <defs>
            {/* Clean 45-deg architectural hatch for restricted zone */}
            <pattern
              id="iso-hatch"
              width="10"
              height="10"
              patternTransform="rotate(45 0 0)"
              patternUnits="userSpaceOnUse"
            >
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="10"
                stroke={inside ? '#FF5500' : '#94A3B8'}
                strokeWidth="1.5"
                strokeOpacity={inside ? '0.32' : '0.22'}
              />
            </pattern>
            {/* Soft ground fade */}
            <linearGradient id="walkway-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#F1F5F9" />
              <stop offset="100%" stopColor="#E2E8F0" />
            </linearGradient>
          </defs>

          {/* Isometric Concrete Ground Slab */}
          <polygon
            points="60,235 450,85 595,180 205,335"
            fill="url(#walkway-grad)"
            stroke="#CBD5E1"
            strokeWidth="1.5"
          />
          {/* Slab Thickness (3D Edge) */}
          <polygon points="60,235 205,335 205,346 60,246" fill="#CBD5E1" />
          <polygon points="205,335 595,180 595,191 205,346" fill="#94A3B8" opacity="0.45" />

          {/* Subtle Isometric Paving Lines */}
          <g stroke="#CBD5E1" strokeWidth="1" opacity="0.65">
            <line x1="158" y1="197" x2="303" y2="297" />
            <line x1="255" y1="160" x2="400" y2="260" />
            <line x1="352" y1="122" x2="497" y2="222" />
            <line x1="132" y1="285" x2="522" y2="132" />
          </g>

          {/* Background Perimeter Fence Posts (Architectural) */}
          <g stroke="#64748B" strokeWidth="2" strokeLinecap="round">
            <line x1="255" y1="155" x2="255" y2="112" />
            <line x1="342" y1="130" x2="342" y2="87" />
            <line x1="430" y1="105" x2="430" y2="62" />
            <line x1="255" y1="118" x2="430" y2="68" strokeWidth="1.5" />
            <line x1="255" y1="136" x2="430" y2="86" strokeWidth="1" opacity="0.6" />
          </g>

          {/* Edge Camera Pole + Subtle FOV Cone */}
          <g>
            <polygon
              points="438,52 255,155 525,185"
              fill={inside ? '#FF5500' : '#0F172A'}
              opacity={inside ? '0.06' : '0.03'}
            />
            <line x1="438" y1="102" x2="438" y2="48" stroke="#1E293B" strokeWidth="3" />
            <rect x="427" y="42" width="16" height="9" rx="2" fill="#1E293B" />
            <circle cx="429" cy="46.5" r="2" fill={inside ? '#FF5500' : '#10B981'} />
          </g>

          {/* Restricted Virtual Fence Polygon (Flat on Isometric Ground) */}
          <polygon
            points={ZONE_STR}
            fill="url(#iso-hatch)"
            stroke={inside ? '#FF5500' : '#64748B'}
            strokeWidth={inside ? '2.5' : '1.5'}
            strokeDasharray={inside ? 'none' : '6 4'}
            style={{ transition: 'stroke 0.2s ease' }}
          />
          {ZONE_POLY.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r="3.5" fill={inside ? '#FF5500' : '#64748B'} />
          ))}

          {/* Walking Trajectory Line */}
          <line
            x1={PATH_START.x}
            y1={PATH_START.y}
            x2={PATH_END.x}
            y2={PATH_END.y}
            stroke="#94A3B8"
            strokeWidth="1.5"
            strokeDasharray="3 4"
            opacity="0.7"
          />

          {/* Live Horizontal Ray-Casting Line from (xb, yb) */}
          <line
            x1={pos.x}
            y1={pos.y}
            x2="585"
            y2={pos.y}
            stroke={inside ? '#FF5500' : '#64748B'}
            strokeWidth="1.5"
            strokeDasharray="5 4"
          />

          {/* Ray-Casting Edge Intersections */}
          {hits.map((h, i) => (
            <g key={i}>
              <circle cx={h.x} cy={h.y} r="5.5" fill="#FFFFFF" stroke="#FF5500" strokeWidth="2" />
              <circle cx={h.x} cy={h.y} r="2" fill="#FF5500" />
            </g>
          ))}

          {/* Target Ground Contact Point (xb, yb) */}
          <ellipse cx={pos.x} cy={pos.y} rx="12" ry="6" fill="#0F172A" opacity="0.14" />
          <circle cx={pos.x} cy={pos.y} r="4" fill={inside ? '#FF5500' : '#0F172A'} />

          {/* Clean Isometric Pegman-Style Figure */}
          <g transform={`translate(${pos.x}, ${pos.y - bob})`}>
            {/* Extruded 3D Side Body */}
            <path d="M 6 -42 L 11 -39 L 11 -6 L 6 -2 Z" fill="#C2410C" />
            {/* Front Body (Signal Amber/Orange) */}
            <path
              d="M -8 -42 L 6 -42 L 6 -2 L -8 -5 Z"
              fill={inside ? '#FF5500' : '#F59E0B'}
              stroke="#1E293B"
              strokeWidth="1.75"
              strokeLinejoin="round"
            />
            {/* Collar V-Accent */}
            <polygon points="-4,-42 2,-42 -1,-33" fill="#EA580C" />
            {/* Head */}
            <circle
              cx="-1"
              cy="-53"
              r="8.5"
              fill={inside ? '#FF5500' : '#FBBF24'}
              stroke="#1E293B"
              strokeWidth="1.75"
            />
            {/* Minimal YOLOv8n Corner Brackets around Figure */}
            <g stroke={inside ? '#FF5500' : '#0F172A'} strokeWidth="1.5" fill="none">
              <path d="M -18 -60 L -18 -67 L -11 -67" />
              <path d="M 10 -67 L 17 -67 L 17 -60" />
              <path d="M -18 -5 L -18 2 L -11 2" />
              <path d="M 10 2 L 17 2 L 17 -5" />
            </g>
            {/* Compact Floating Label */}
            <rect
              x="-18"
              y="-84"
              width="70"
              height="15"
              rx="3"
              fill={inside ? '#FF5500' : '#0F172A'}
            />
            <text
              x="-13"
              y="-73.5"
              fill="#FFFFFF"
              fontSize="8.5"
              fontWeight="700"
              fontFamily="ui-monospace, monospace"
            >
              PERSON 0.94
            </text>
          </g>

          {/* Floating Step-3 Evidence Card (Appears cleanly when confirmed) */}
          <g
            style={{
              opacity: confirmed ? 1 : 0,
              transform: confirmed ? 'translateY(0px)' : 'translateY(6px)',
              transition: 'all 0.25s ease',
            }}
          >
            <rect
              x="445"
              y="258"
              width="172"
              height="62"
              rx="8"
              fill="#FFFFFF"
              stroke="#FF5500"
              strokeWidth="1.5"
            />
            <text
              x="457"
              y="277"
              fill="#FF5500"
              fontSize="9"
              fontWeight="700"
              fontFamily="ui-monospace, monospace"
            >
              BREACH CONFIRMED • 3/3
            </text>
            <text x="457" y="294" fill="#0F172A" fontSize="10" fontWeight="600">
              Dual-Crop RoI Extracted
            </text>
            <text
              x="457"
              y="309"
              fill="#64748B"
              fontSize="8.5"
              fontFamily="ui-monospace, monospace"
            >
              AES-256-GCM → SQLite WAL
            </text>
          </g>
        </svg>

        {/* Minimal Top-Left Live Telemetry Pill (Light Mode) */}
        <div
          style={{
            position: 'absolute',
            top: '8px',
            left: '8px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '5px 10px',
            borderRadius: '6px',
            backgroundColor: '#FFFFFF',
            border: `1px solid ${inside ? '#FF5500' : '#E2E8F0'}`,
            boxShadow: '0 2px 8px rgba(15, 23, 42, 0.05)',
            fontSize: '11px',
            fontFamily: 'ui-monospace, monospace',
            color: '#0F172A',
          }}
        >
          <span style={{ color: '#FF5500', fontWeight: 700 }}>INT8</span>
          <span style={{ color: '#CBD5E1' }}>|</span>
          <span>18ms</span>
          <span style={{ color: '#CBD5E1' }}>|</span>
          <span style={{ color: inside ? '#FF5500' : '#64748B', fontWeight: 600 }}>
            {inside ? `${framesCount}/3 FRAMES` : `HITS: ${hits.length} (SAFE)`}
          </span>
        </div>
      </div>

      {/* Stepper Bar (Matches your reference: 1  2  3  || Pause) */}
      <div
        style={{
          marginTop: '12px',
          paddingTop: '12px',
          borderTop: '1px solid #E2E8F0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ fontSize: '13px', fontWeight: 700, color: '#0F172A' }}>
            {STEPS[activeStep - 1].title}
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '2px' }}>
            {STEPS[activeStep - 1].desc}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
          {STEPS.map((s) => (
            <button
              key={s.id}
              onClick={() => jumpToStep(s.id)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: activeStep === s.id ? '2px solid #FF5500' : '2px solid transparent',
                padding: '2px 4px',
                fontSize: '12px',
                fontWeight: activeStep === s.id ? 700 : 500,
                color: activeStep === s.id ? '#0F172A' : '#94A3B8',
                cursor: 'pointer',
              }}
            >
              {s.id}
            </button>
          ))}
          <button
            onClick={() => setPaused((p) => !p)}
            style={{
              background: 'none',
              border: 'none',
              padding: '2px 6px',
              fontSize: '12px',
              color: '#475569',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            {paused ? '▶ Play' : '⏸ Pause'}
          </button>
        </div>
      </div>
    </div>
  );
};
