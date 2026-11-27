import React, { useEffect, useState } from 'react';
import { StageStepperIcon } from './StageStepperIcon';

interface Point {
  x: number;
  y: number;
}

// 2D perspective floor polygon for the RESTRICTED DOOR ZONE in front of SECTOR B-04 (640x400, 16:10)
const DOOR_ZONE: Point[] = [
  { x: 350, y: 286 },
  { x: 562, y: 286 },
  { x: 584, y: 338 },
  { x: 326, y: 338 },
];

const DOOR_ZONE_STR = DOOR_ZONE.map((p) => `${p.x},${p.y}`).join(' ');

// Real Jordan Curve Ray-Casting (horizontal ray to +Infinity)
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

const WALK_Y = 312;
const START_X = 10;
const END_X = 472;
const CAM3_FOV_LEFT = 95;
const CAM3_X = 315;
const CAM3_Y = 145;
const CAM_X = 592;
const CAM_Y = 88;

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

const STEPS = [
  {
    id: 1,
    title: 'Multi-node edge coverage',
    desc: 'Independent edge cameras run local YOLOv8n inference across adjacent perimeter zones.',
  },
  {
    id: 2,
    title: 'Local Tracking, No Bandwidth',
    desc: 'Edge stream tracks the target, but even ray intersections suppress the transmission.',
  },
  {
    id: 3,
    title: 'Zone breach and Frame Lock',
    desc: 'Entering the virtual fence flips the ray-cast to odd (HITS: 1) and starts the 3-frame persistence check.',
  },
  {
    id: 4,
    title: 'Dual-crop encrypted & queued',
    desc: 'At 3/3 frames, wide-scene and upper-body RoI crops are sealed with AES-256-GCM into SQLite WAL.',
  },
];

export const EdgePerceptionVisual: React.FC = () => {
  const [progress, setProgress] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    let rafId: number;
    let last = performance.now();

    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setProgress((prev) => (prev + dt * 0.125) % 1);
      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [paused]);

  // Walk smoothly from x=65 to x=472, then pause outside the entrance doors before looping
  const moveT = Math.min(1, progress / 0.78);
  const pos: Point = {
    x: lerp(START_X, END_X, moveT),
    y: WALK_Y,
  };

  const { inside } = castRay(pos, DOOR_ZONE);
  const inCam3 = !inside && pos.x >= CAM3_FOV_LEFT;

  // Compute temporal confirmation frames once inside the door zone
  const framesCount = !inside ? 0 : progress >= 0.72 ? 3 : progress >= 0.62 ? 2 : 1;
  const activeStep: 1 | 2 | 3 | 4 = !inside
    ? pos.x < 185
      ? 1
      : 2
    : framesCount < 3
    ? 3
    : 4;
  const confirmed = activeStep === 4;

  // Subtle walking bob while moving
  const bob = moveT < 1 ? Math.abs(Math.sin(progress * 48)) * 2.5 : 0;

  const jumpToStep = (stepId: number) => {
    if (stepId === 1) setProgress(0.16);
    else if (stepId === 2) setProgress(0.38);
    else if (stepId === 3) setProgress(0.60);
    else setProgress(0.84);
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
      {/* Seamless Transparent 16:10 Architectural CAD Viewport */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          aspectRatio: '16 / 10',
          backgroundColor: 'transparent',
          overflow: 'visible',
        }}
      >
        <svg
          viewBox="0 0 640 360"
          style={{ width: '100%', height: '100%', display: 'block', overflow: 'visible' }}
        >
          <defs>
            {/* 45-deg architectural hatch for RESTRICTED DOOR ZONE */}
            <pattern
              id="door-zone-hatch"
              width="9"
              height="9"
              patternTransform="rotate(45 0 0)"
              patternUnits="userSpaceOnUse"
            >
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="9"
                stroke={inside ? '#FF5500' : '#94A3B8'}
                strokeWidth="1.4"
                strokeOpacity={inside ? '0.34' : '0.22'}
              />
            </pattern>
            {/* Subtle FOV gradient from top-right rooftop camera */}
            <linearGradient id="cam-fov-grad" x1="100%" y1="0%" x2="30%" y2="100%">
              <stop
                offset="0%"
                stopColor={inside ? '#FF5500' : '#64748B'}
                stopOpacity={inside ? '0.18' : '0.07'}
              />
              <stop
                offset="100%"
                stopColor={inside ? '#FF5500' : '#64748B'}
                stopOpacity="0.01"
              />
            </linearGradient>
          </defs>

          {/* Public Sidewalk Only (Transparent Background Above & Below) */}
          <rect x="0" y="286" width="640" height="52" fill="#F8FAFC" />
          <line x1="0" y1="286" x2="640" y2="286" stroke="#CBD5E1" strokeWidth="1.25" />
          {/* Sidewalk Expansion Joints */}
          <g stroke="#E2E8F0" strokeWidth="1">
            <line x1="72" y1="286" x2="54" y2="338" />
            <line x1="156" y1="286" x2="138" y2="338" />
            <line x1="240" y1="286" x2="222" y2="338" />
            <line x1="324" y1="286" x2="306" y2="338" />
          </g>
          {/* Curb Edge */}
          <rect x="0" y="338" width="640" height="6" fill="#CBD5E1" />

          {/* Right-Side Architectural Facade: SECTOR B-04 */}
          <g>
            {/* Main Building Wall */}
            <rect
              x="362"
              y="88"
              width="250"
              height="198"
              fill="#F8FAFC"
              stroke="#CBD5E1"
              strokeWidth="1.5"
            />
            {/* Roof Parapet Cap */}
            <rect
              x="356"
              y="82"
              width="262"
              height="10"
              rx="1.5"
              fill="#E2E8F0"
              stroke="#94A3B8"
              strokeWidth="1.25"
            />
            {/* Horizontal Architectural Spandrel Band */}
            <line x1="362" y1="168" x2="612" y2="168" stroke="#E2E8F0" strokeWidth="1.5" />

            {/* Upper Architectural Windows */}
            {[382, 444, 506, 560].map((wx, idx) => (
              <g key={idx}>
                <rect
                  x={wx}
                  y="130"
                  width={idx === 3 ? 36 : 46}
                  height="28"
                  rx="1.5"
                  fill="#EFF6FF"
                  stroke="#94A3B8"
                  strokeWidth="1.2"
                />
                <line
                  x1={wx + 6}
                  y1="152"
                  x2={wx + 18}
                  y2="136"
                  stroke="#FFFFFF"
                  strokeWidth="1.5"
                  opacity="0.7"
                />
              </g>
            ))}

            {/* Recessed Double Glass Entrance Doors */}
            <g>
              {/* Entrance Canopy */}
              <rect
                x="412"
                y="182"
                width="124"
                height="7"
                rx="1"
                fill="#CBD5E1"
                stroke="#64748B"
                strokeWidth="1"
              />
              {/* Outer Recessed Frame */}
              <rect
                x="420"
                y="189"
                width="108"
                height="97"
                fill="#E2E8F0"
                stroke="#64748B"
                strokeWidth="1.5"
              />
              {/* Left Glass Door Leaf */}
              <rect
                x="426"
                y="195"
                width="46"
                height="91"
                fill="#DBEAFE"
                stroke="#475569"
                strokeWidth="1.2"
              />
              {/* Right Glass Door Leaf */}
              <rect
                x="476"
                y="195"
                width="46"
                height="91"
                fill="#DBEAFE"
                stroke="#475569"
                strokeWidth="1.2"
              />
              {/* Glass Diagonal Glare */}
              <line x1="432" y1="268" x2="464" y2="212" stroke="#FFFFFF" strokeWidth="2" opacity="0.55" />
              <line x1="482" y1="268" x2="514" y2="212" stroke="#FFFFFF" strokeWidth="2" opacity="0.55" />
              {/* Door Push Handles */}
              <line x1="466" y1="234" x2="466" y2="250" stroke="#1E293B" strokeWidth="2.2" strokeLinecap="round" />
              <line x1="482" y1="234" x2="482" y2="250" stroke="#1E293B" strokeWidth="2.2" strokeLinecap="round" />
              {/* Access Keypad Indicator */}
              <rect x="534" y="232" width="10" height="16" rx="1.5" fill="#1E293B" />
              <circle cx="539" cy="237" r="1.8" fill={inside ? '#FF5500' : '#10B981'} />
            </g>
          </g>

          {/* Left Sidewalk Camera (CAM-03) FOV Cone (turns subtle orange when stickman is in sight) */}
          <polygon
            points={`${CAM3_X},${CAM3_Y} ${CAM3_FOV_LEFT},338 310,338`}
            fill={inCam3 ? '#FF5500' : '#0F172A'}
            opacity={inCam3 ? '0.1' : '0.025'}
            style={{ transition: 'fill 0.25s ease, opacity 0.25s ease' }}
          />

          {/* Approach Sidewalk Pole & Mounted Camera Housing (CAM-03, facing left) */}
          <g>
            {/* Pole Base Plate on Sidewalk Back Edge */}
            <rect x={CAM3_X - 5} y="284" width="10" height="4" rx="1" fill="#475569" />
            {/* Vertical Street Pole rising from sidewalk edge (y=286) to y=145 */}
            <line
              x1={CAM3_X}
              y1="286"
              x2={CAM3_X}
              y2={CAM3_Y}
              stroke="#334155"
              strokeWidth="3"
              strokeLinecap="round"
            />
            {/* Short Mounting Arm extending left */}
            <line
              x1={CAM3_X}
              y1={CAM3_Y + 4}
              x2={CAM3_X - 7}
              y2={CAM3_Y + 4}
              stroke="#1E293B"
              strokeWidth="2.4"
              strokeLinecap="round"
            />
            {/* Camera Housing angled downward-left (rotate 142 deg) */}
            <g transform={`translate(${CAM3_X - 8}, ${CAM3_Y + 4}) rotate(142)`}>
              <rect x="-10" y="-5.5" width="20" height="11" rx="2" fill="#1E293B" />
              <rect x="8" y="-3.5" width="4.5" height="7" rx="1" fill="#475569" />
              <circle cx="10.5" cy="0" r="2" fill={inCam3 ? '#10B981' : '#64748B'} />
            </g>
          </g>

          {/* Rooftop Camera FOV Cone projecting downward-left over RESTRICTED DOOR ZONE */}
          <polygon
            points={`${CAM_X},${CAM_Y} 326,338 584,338`}
            fill="url(#cam-fov-grad)"
          />

          {/* RESTRICTED DOOR ZONE Polygon on Sidewalk */}
          <polygon
            points={DOOR_ZONE_STR}
            fill="url(#door-zone-hatch)"
            stroke={inside ? '#FF5500' : '#64748B'}
            strokeWidth={inside ? '2.25' : '1.5'}
            strokeDasharray={inside ? 'none' : '6 4'}
            style={{ transition: 'stroke 0.2s ease' }}
          />
          {DOOR_ZONE.map((p, idx) => (
            <circle
              key={idx}
              cx={p.x}
              cy={p.y}
              r="3"
              fill={inside ? '#FF5500' : '#64748B'}
            />
          ))}

          {/* Rooftop Camera Mount Bolted to Top-Right Building Corner */}
          <g>
            {/* Wall/Parapet Mounting Plate */}
            <rect x="606" y="78" width="6" height="18" rx="1" fill="#334155" />
            {/* Rigid Mounting Arm connecting plate to camera body */}
            <path
              d={`M 606 84 L ${CAM_X + 6} 84 L ${CAM_X + 2} ${CAM_Y}`}
              fill="none"
              stroke="#1E293B"
              strokeWidth="2.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* Pivot Joint */}
            <circle cx={CAM_X + 2} cy={CAM_Y} r="2.6" fill="#475569" />
            {/* Camera Body rotated 148 deg downward-left */}
            <g transform={`translate(${CAM_X}, ${CAM_Y}) rotate(148)`}>
              <rect x="-12" y="-6" width="22" height="12" rx="2" fill="#1E293B" />
              <rect x="8" y="-4" width="5" height="8" rx="1" fill="#475569" />
              <circle cx="11" cy="0" r="2.2" fill={inside ? '#FF5500' : '#10B981'} />
            </g>
            {/* Concentric Signal Wave Arcs above Rooftop Camera after Capture (Stage 4) */}
            {confirmed && (
              <g>
                <style>{`
                  @keyframes sentra-wave-pulse {
                    0%, 100% { opacity: 0.25; }
                    50% { opacity: 1; }
                  }
                `}</style>
                <path
                  d={`M ${CAM_X - 10} ${CAM_Y - 12} Q ${CAM_X - 2} ${CAM_Y - 22}, ${CAM_X + 10} ${CAM_Y - 20}`}
                  fill="none"
                  stroke="#FF5500"
                  strokeWidth="2"
                  strokeLinecap="round"
                  style={{ animation: 'sentra-wave-pulse 1.1s ease-in-out infinite' }}
                />
                <path
                  d={`M ${CAM_X - 15} ${CAM_Y - 18} Q ${CAM_X - 3} ${CAM_Y - 31}, ${CAM_X + 14} ${CAM_Y - 28}`}
                  fill="none"
                  stroke="#FF5500"
                  strokeWidth="2"
                  strokeLinecap="round"
                  style={{ animation: 'sentra-wave-pulse 1.1s ease-in-out 0.25s infinite' }}
                />
              </g>
            )}
          </g>

          {/* Ground Contact Point (xb, yb) */}
          <ellipse cx={pos.x} cy={pos.y} rx="12" ry="4.5" fill="#0F172A" opacity="0.14" />
          <circle cx={pos.x} cy={pos.y} r="4" fill={inside ? '#FF5500' : '#0F172A'} />
          <text
            x={pos.x - 24}
            y={pos.y + 16}
            fill={inside ? '#FF5500' : '#475569'}
            fontSize="8.5"
            fontWeight="700"
            fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            ({Math.round(pos.x)}, {Math.round(pos.y)})
          </text>

          {/* Extruded Orange Pegman-Style Figure + YOLOv8n Bounding Box */}
          <g transform={`translate(${pos.x}, ${pos.y - bob})`}>
            {/* Extruded 3D Side Body */}
            <path d="M 6 -44 L 11 -41 L 11 -6 L 6 -2 Z" fill="#C2410C" />
            {/* Front Body (Amber/Orange) */}
            <path
              d="M -8 -44 L 6 -44 L 6 -2 L -8 -5 Z"
              fill={inside ? '#FF5500' : '#F59E0B'}
              stroke="#1E293B"
              strokeWidth="1.75"
              strokeLinejoin="round"
            />
            {/* Collar V-Accent */}
            <polygon points="-4,-44 2,-44 -1,-34" fill="#EA580C" />
            {/* Head */}
            <circle
              cx="-1"
              cy="-55"
              r="8.5"
              fill={inside ? '#FF5500' : '#FBBF24'}
              stroke="#1E293B"
              strokeWidth="1.75"
            />

            {/* YOLOv8n Bounding Box & Tag (hidden until inside CAM-03 or CAM-04 sight) */}
            {(inCam3 || inside) && (
              <>
                <rect
                  x="-20"
                  y="-69"
                  width="40"
                  height="71"
                  fill={confirmed ? 'rgba(255, 85, 0, 0.08)' : 'none'}
                  stroke={inside ? '#FF5500' : '#0F172A'}
                  strokeWidth="1.5"
                />

                {/* Dashed Upper-Body RoI Sub-Box (only after 3rd frame confirmed) */}
                {confirmed && (
                  <rect
                    x="-16"
                    y="-65"
                    width="32"
                    height="27"
                    fill="rgba(255, 85, 0, 0.16)"
                    stroke="#FF5500"
                    strokeWidth="1.4"
                    strokeDasharray="3 2"
                  />
                )}

                {/* PERSON 0.94 Floating Tag */}
                <rect
                  x="-20"
                  y="-85"
                  width="70"
                  height="15"
                  rx="2.5"
                  fill={inside ? '#FF5500' : '#0F172A'}
                />
                <text
                  x="-15"
                  y="-74.5"
                  fill="#FFFFFF"
                  fontSize="8.5"
                  fontWeight="700"
                  fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
                >
                  PERSON 0.94
                </text>
              </>
            )}
          </g>
        </svg>
      </div>

      {/* Bottom 3-Step Caption & Control Bar */}
      <div
        style={{
          marginTop: '10px',
          paddingTop: '12px',
          borderTop: '1px solid #E2E8F0',
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '12px 16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', flex: '1 1 240px' }}>
          <StageStepperIcon step={activeStep} />
          <div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: '#0F172A' }}>
              {STEPS[activeStep - 1].title}
            </div>
            <div style={{ fontSize: '12px', color: '#64748B', marginTop: '2px' }}>
              {STEPS[activeStep - 1].desc}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
          {STEPS.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => jumpToStep(s.id)}
              style={{
                background: 'none',
                border: 'none',
                outline: 'none',
                boxShadow: 'none',
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
            type="button"
            onClick={() => setPaused((p) => !p)}
            style={{
              background: 'none',
              border: 'none',
              outline: 'none',
              boxShadow: 'none',
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
