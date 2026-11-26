import React from 'react';

const DISCS = [
  { cy: 266, id: 'disc-3' },
  { cy: 208, id: 'disc-2' },
  { cy: 150, id: 'disc-1' },
];

export const NetworkResilienceVisual: React.FC = () => {
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '16 / 10',
        backgroundColor: 'transparent',
        overflow: 'visible',
        direction: 'ltr',
        userSelect: 'none',
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      }}
    >
      {/* 3D Isometric Packaged Circular Data Disks Inside Translucent Cylinder Sleeve */}
      <svg
        viewBox="0 0 640 400"
        style={{ position: 'relative', width: '100%', height: '100%', display: 'block', zIndex: 2 }}
        role="img"
        aria-label="Three stacked AES-256-GCM sealed circular data disks inside a SQLite WAL protective cylinder sleeve"
      >
        <defs>
          {/* Ambient warm glow behind the cylinder */}
          <radialGradient id="vault-ambient" cx="50%" cy="54%" r="42%">
            <stop offset="0%" stopColor="#FF5500" stopOpacity="0.14" />
            <stop offset="65%" stopColor="#FF5500" stopOpacity="0.03" />
            <stop offset="100%" stopColor="#FF5500" stopOpacity="0" />
          </radialGradient>

          {/* Soft floor shadow */}
          <radialGradient id="floor-shadow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#0F172A" stopOpacity="0.24" />
            <stop offset="65%" stopColor="#0F172A" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#0F172A" stopOpacity="0" />
          </radialGradient>

          {/* Charcoal-slate extruded disc rim gradient */}
          <linearGradient id="disc-side-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#090E1A" />
            <stop offset="28%" stopColor="#1E293B" />
            <stop offset="55%" stopColor="#0F172A" />
            <stop offset="82%" stopColor="#334155" />
            <stop offset="100%" stopColor="#090E1A" />
          </linearGradient>

          {/* Sleek metallic charcoal top face gradient */}
          <linearGradient id="disc-top-grad" x1="15%" y1="0%" x2="85%" y2="100%">
            <stop offset="0%" stopColor="#334155" />
            <stop offset="35%" stopColor="#1E293B" />
            <stop offset="72%" stopColor="#0F172A" />
            <stop offset="100%" stopColor="#1E293B" />
          </linearGradient>

          {/* Subtle metallic top specular sheen */}
          <linearGradient id="disc-sheen" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.22" />
            <stop offset="45%" stopColor="#FFFFFF" stopOpacity="0.04" />
            <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
          </linearGradient>

          {/* Signal-orange rim seal gradient */}
          <linearGradient id="orange-seal-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#EA580C" />
            <stop offset="45%" stopColor="#FF5500" />
            <stop offset="75%" stopColor="#FF7A33" />
            <stop offset="100%" stopColor="#C2410C" />
          </linearGradient>

          {/* Frosted-glass cylinder sleeve gradient */}
          <linearGradient id="sleeve-glass-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.42" />
            <stop offset="16%" stopColor="#FFFFFF" stopOpacity="0.14" />
            <stop offset="48%" stopColor="#E2E8F0" stopOpacity="0.05" />
            <stop offset="82%" stopColor="#FFFFFF" stopOpacity="0.24" />
            <stop offset="100%" stopColor="#CBD5E1" stopOpacity="0.34" />
          </linearGradient>

          {/* Soft drop shadow for each stacked disc */}
          <filter id="disc-shadow" x="-20%" y="-20%" width="140%" height="160%">
            <feDropShadow dx="0" dy="10" stdDeviation="7" floodColor="#0F172A" floodOpacity="0.22" />
          </filter>
        </defs>

        {/* Ambient Glow & Ground Shadow */}
        <ellipse cx="320" cy="215" rx="220" ry="155" fill="url(#vault-ambient)" />
        <ellipse cx="320" cy="322" rx="158" ry="44" fill="url(#floor-shadow)" />

        {/* BACK HALF OF TRANSLUCENT CYLINDER SLEEVE */}
        <g>
          {/* Back Top Ellipse Rim */}
          <path
            d="M 186 106 A 134 40 0 0 1 454 106"
            fill="none"
            stroke="#94A3B8"
            strokeWidth="1.25"
            strokeDasharray="4 4"
            opacity="0.7"
          />
          {/* Back Bottom Ellipse Rim */}
          <path
            d="M 186 306 A 134 40 0 0 1 454 306"
            fill="none"
            stroke="#94A3B8"
            strokeWidth="1.15"
            strokeDasharray="4 4"
            opacity="0.55"
          />
          {/* Subtle Inner Back Cylinder Fill */}
          <path
            d="M 186 106 A 134 40 0 0 1 454 106 L 454 306 A 134 40 0 0 0 186 306 Z"
            fill="#FFFFFF"
            opacity="0.22"
          />
        </g>

        {/* THREE STACKED CIRCULAR CHARCOAL-SLATE DATA DISKS */}
        {DISCS.map((disc, idx) => {
          const rx = 112;
          const ry = 33;
          const thickness = 22;
          const yTop = disc.cy;
          const yBot = disc.cy + thickness;
          const ySeal = disc.cy + thickness * 0.56;

          return (
            <g key={disc.id} filter="url(#disc-shadow)">
              {/* Extruded Cylindrical Side Wall */}
              <path
                d={`M ${320 - rx} ${yTop} L ${320 - rx} ${yBot} A ${rx} ${ry} 0 0 0 ${320 + rx} ${yBot} L ${320 + rx} ${yTop} A ${rx} ${ry} 0 0 1 ${320 - rx} ${yTop} Z`}
                fill="url(#disc-side-grad)"
                stroke="#090E1A"
                strokeWidth="1"
              />

              {/* Crisp Signal-Orange Locking Ring Around Rim */}
              <path
                d={`M ${320 - rx} ${ySeal} A ${rx} ${ry} 0 0 0 ${320 + rx} ${ySeal}`}
                fill="none"
                stroke="url(#orange-seal-grad)"
                strokeWidth="2.6"
                strokeLinecap="round"
              />

              {/* Mechanical Security Clasp / Seal Notch on Front-Right Rim */}
              <g transform={`translate(${320 + 68}, ${ySeal + 21})`}>
                <rect
                  x="-11"
                  y="-6"
                  width="22"
                  height="12"
                  rx="3"
                  fill="#0F172A"
                  stroke="#FF5500"
                  strokeWidth="1.6"
                />
                <circle cx="0" cy="0" r="2.2" fill="#FF5500" />
              </g>

              {/* Top Circular Platter Face */}
              <ellipse
                cx="320"
                cy={yTop}
                rx={rx}
                ry={ry}
                fill="url(#disc-top-grad)"
                stroke="#475569"
                strokeWidth="1.2"
              />

              {/* Subtle Metallic Sheen Overlay */}
              <ellipse
                cx="320"
                cy={yTop}
                rx={rx - 1.5}
                ry={ry - 0.8}
                fill="url(#disc-sheen)"
              />

              {/* Concentric Precision Data Grooves */}
              <ellipse
                cx="320"
                cy={yTop}
                rx={rx * 0.78}
                ry={ry * 0.78}
                fill="none"
                stroke="rgba(255, 255, 255, 0.08)"
                strokeWidth="1"
              />
              <ellipse
                cx="320"
                cy={yTop}
                rx={rx * 0.56}
                ry={ry * 0.56}
                fill="none"
                stroke="rgba(255, 255, 255, 0.06)"
                strokeWidth="1"
              />

              {/* Center Hub / Cryptographic Spindle Ring (most prominent on top disc) */}
              <ellipse
                cx="320"
                cy={yTop}
                rx="24"
                ry="7.5"
                fill="#090E1A"
                stroke={idx === 2 ? '#FF5500' : '#475569'}
                strokeWidth={idx === 2 ? '1.5' : '1.1'}
              />
              <ellipse
                cx="320"
                cy={yTop}
                rx="9"
                ry="2.8"
                fill={idx === 2 ? '#FF5500' : '#334155'}
                opacity={idx === 2 ? '0.9' : '0.7'}
              />
            </g>
          );
        })}

        {/* FRONT HALF OF TRANSLUCENT FROSTED-GLASS / WIREFRAME CYLINDER SLEEVE */}
        <g style={{ pointerEvents: 'none' }}>
          {/* Translucent Front Glass Body */}
          <path
            d="M 186 106 A 134 40 0 0 0 454 106 L 454 306 A 134 40 0 0 1 186 306 Z"
            fill="url(#sleeve-glass-grad)"
          />

          {/* Vertical Specular Glass Highlight Strips */}
          <path
            d="M 212 126 L 212 326"
            stroke="#FFFFFF"
            strokeWidth="6"
            strokeLinecap="round"
            opacity="0.32"
          />
          <path
            d="M 224 130 L 224 330"
            stroke="#FFFFFF"
            strokeWidth="2"
            strokeLinecap="round"
            opacity="0.45"
          />
          <path
            d="M 430 124 L 430 324"
            stroke="#FFFFFF"
            strokeWidth="3.5"
            strokeLinecap="round"
            opacity="0.28"
          />

          {/* Crisp Wireframe Side Tangent Lines */}
          <line x1="186" y1="106" x2="186" y2="306" stroke="#94A3B8" strokeWidth="1.4" opacity="0.85" />
          <line x1="454" y1="106" x2="454" y2="306" stroke="#94A3B8" strokeWidth="1.4" opacity="0.85" />

          {/* Top Glass Cylinder Rim (Front Arc) */}
          <path
            d="M 186 106 A 134 40 0 0 0 454 106"
            fill="none"
            stroke="#94A3B8"
            strokeWidth="1.5"
            opacity="0.9"
          />
          <ellipse
            cx="320"
            cy="106"
            rx="134"
            ry="40"
            fill="rgba(255, 255, 255, 0.14)"
            stroke="none"
          />

          {/* Bottom Glass Cylinder Rim (Front Arc) */}
          <path
            d="M 186 306 A 134 40 0 0 0 454 306"
            fill="none"
            stroke="#94A3B8"
            strokeWidth="1.6"
            opacity="0.95"
          />
        </g>
      </svg>
    </div>
  );
};
