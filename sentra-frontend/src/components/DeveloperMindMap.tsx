import React from 'react';

interface DeveloperMindMapProps {
  eyebrow: string;
}

const HAND_FONT = "'Caveat', 'Comic Sans MS', cursive";

export const DeveloperMindMap: React.FC<DeveloperMindMapProps> = ({ eyebrow }) => {
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        maxWidth: '820px',
        margin: '0 auto',
        aspectRatio: '16 / 7.2',
        minHeight: '300px',
        direction: 'ltr',
        userSelect: 'none',
      }}
    >
      <style>{`
        .dev-sketch-link {
          transition: transform 0.2s ease, color 0.2s ease;
        }
        .dev-sketch-link:hover {
          transform: scale(1.07) rotate(0deg) !important;
        }
      `}</style>

      {/* Hand-Drawn Squiggly Ink Arrows & Sketch Doodles */}
      <svg
        viewBox="0 0 820 360"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          overflow: 'visible',
        }}
      >
        {/* 1. Top-Left Squiggly Arrow -> Computer Engineer */}
        <g stroke="#1E293B" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M 222 146 C 210 138, 214 124, 200 118 C 186 112, 190 98, 176 92 C 164 86, 166 76, 154 72" />
          {/* Hand-drawn open arrowhead */}
          <path d="M 166 69 L 152 71 L 158 84" />
        </g>

        {/* 2. Bottom-Center-Left Squiggly Arrow -> Computer Vision */}
        <g stroke="#1E293B" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M 332 208 C 322 218, 332 230, 318 240 C 306 248, 312 258, 300 268" />
          <path d="M 297 256 L 298 270 L 311 266" />
        </g>

        {/* 3. Bottom-Left Squiggly Arrow -> Electrical Engineer */}
        <g stroke="#1E293B" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M 218 196 C 204 194, 200 208, 186 206 C 172 204, 168 218, 154 216 C 142 214, 138 224, 128 228" />
          <path d="M 139 219 L 126 229 L 140 234" />
        </g>

        {/* 4. Bottom-Center-Right Squiggly Arrow -> Embedded */}
        <g stroke="#1E293B" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M 476 208 C 488 216, 474 230, 488 240 C 500 248, 492 258, 502 268" />
          <path d="M 490 266 L 503 270 L 505 256" />
        </g>

        {/* 5. Top-Right Squiggly Orange Arrow -> LinkedIn */}
        <g stroke="#FF671D" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M 594 146 C 604 134, 616 140, 624 128 C 632 114, 644 120, 656 106" />
          <path d="M 643 105 L 658 104 L 654 119" />
        </g>

        {/* 6. Middle-Right Squiggly Orange Arrow -> Portfolio */}
        <g stroke="#FF671D" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M 596 172 C 608 164, 616 180, 628 172 C 636 166, 644 176, 656 170" />
          <path d="M 644 163 L 658 170 L 645 179" />
        </g>

        {/* 7. Bottom-Right Squiggly Orange Arrow -> GitHub */}
        <g stroke="#FF671D" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M 582 204 C 594 202, 594 218, 608 218 C 620 218, 622 234, 636 238" />
          <path d="M 625 229 L 639 239 L 625 246" />
        </g>

        {/* Tiny Sketchbook Sparkles / Pencil Marks around the Name */}
        <g stroke="#FF671D" strokeWidth="2" strokeLinecap="round" opacity="0.65">
          <line x1="258" y1="126" x2="252" y2="118" />
          <line x1="270" y1="118" x2="269" y2="109" />
          <line x1="564" y1="118" x2="571" y2="111" />
        </g>
      </svg>

      {/* Center: ABOUT THE DEVELOPER + Mohamed Abdou */}
      <div
        style={{
          position: 'absolute',
          top: '47%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center',
          whiteSpace: 'nowrap',
        }}
      >
        <p
          style={{
            fontSize: '12px',
            fontWeight: 800,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--brand-orange)',
            marginBottom: '6px',
          }}
        >
          {eyebrow}
        </p>
        <h2
          style={{
            fontSize: '46px',
            fontWeight: 900,
            color: '#22262A',
            letterSpacing: '-0.025em',
            lineHeight: 1.08,
          }}
        >
          Mohamed Abdou
        </h2>
      </div>

      {/* Top-Left Hand-Sketched: Computer Engineer */}
      <div
        style={{
          position: 'absolute',
          top: '3%',
          left: '1%',
          transform: 'rotate(-10deg)',
          fontFamily: HAND_FONT,
          fontSize: '30px',
          fontWeight: 700,
          lineHeight: 0.92,
          color: '#1E293B',
          textAlign: 'center',
        }}
      >
        <div>Computer</div>
        <div style={{ paddingLeft: '22px' }}>Engineer</div>
      </div>

      {/* Bottom-Center-Left Hand-Sketched: Computer Vision */}
      <div
        style={{
          position: 'absolute',
          bottom: '4%',
          left: '33%',
          transform: 'translateX(-50%) rotate(-2deg)',
          fontFamily: HAND_FONT,
          fontSize: '29px',
          fontWeight: 700,
          lineHeight: 0.95,
          color: '#1E293B',
          textAlign: 'center',
        }}
      >
        Computer Vision
      </div>

      {/* Bottom-Left Hand-Sketched: Electrical Engineer */}
      <div
        style={{
          position: 'absolute',
          bottom: '10%',
          left: '1%',
          transform: 'rotate(-5deg)',
          fontFamily: HAND_FONT,
          fontSize: '29px',
          fontWeight: 700,
          lineHeight: 0.92,
          color: '#1E293B',
          textAlign: 'center',
        }}
      >
        <div>Electrical</div>
        <div>Engineer</div>
        <svg
          width="96"
          height="10"
          viewBox="0 0 96 10"
          style={{ display: 'block', margin: '0 auto' }}
        >
          <path
            d="M 3 6 Q 48 2, 93 7"
            fill="none"
            stroke="#94A3B8"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </div>

      {/* Bottom-Center-Right Hand-Sketched: Embedded */}
      <div
        style={{
          position: 'absolute',
          bottom: '4%',
          left: '63%',
          transform: 'translateX(-50%) rotate(2deg)',
          fontFamily: HAND_FONT,
          fontSize: '32px',
          fontWeight: 700,
          color: '#1E293B',
        }}
      >
        Embedded
        <svg
          width="96"
          height="10"
          viewBox="0 0 96 10"
          style={{ display: 'block', margin: '-4px auto 0' }}
        >
          <path
            d="M 4 7 C 32 3, 66 3, 92 6"
            fill="none"
            stroke="#FF671D"
            strokeWidth="2.2"
            strokeLinecap="round"
            opacity="0.7"
          />
        </svg>
      </div>

      {/* Top-Right Hand-Sketched Clickable: LinkedIn + Hand-Drawn "in" Badge */}
      <a
        href="https://www.linkedin.com/in/contact-mohamed-abdou/"
        target="_blank"
        rel="noopener noreferrer"
        className="dev-sketch-link"
        style={{
          position: 'absolute',
          top: '11%',
          right: '2%',
          transform: 'rotate(-6deg)',
          fontFamily: HAND_FONT,
          fontSize: '33px',
          fontWeight: 700,
          color: '#1E293B',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        {/* Hand-sketched LinkedIn square icon */}
        <svg
          width="32"
          height="32"
          viewBox="0 0 36 36"
          fill="none"
          style={{ flexShrink: 0, overflow: 'visible' }}
        >
          <path
            d="M 5 7 C 13 4.5, 24 5, 31 6.5 C 32.5 14, 32 24, 30.5 30.5 C 22 32.5, 13 31.5, 5.5 30.5 C 4 22, 4.5 14, 5 7 Z"
            fill="rgba(255, 103, 29, 0.08)"
            stroke="#1E293B"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="11.5" cy="11.5" r="1.7" fill="#FF671D" />
          <path d="M 11.5 16 L 11.2 25.5" stroke="#1E293B" strokeWidth="2.3" strokeLinecap="round" />
          <path
            d="M 17 25.5 L 17.2 16.5 M 17.2 19.5 C 18.8 16.2, 24.5 15.8, 25 19.8 L 25.2 25.5"
            stroke="#1E293B"
            strokeWidth="2.3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
          <div>
            LinkedIn
            <svg
              width="92"
              height="12"
              viewBox="0 0 92 12"
              style={{ display: 'block', marginTop: '-5px' }}
            >
              <path
                d="M 2 7 Q 46 2, 90 6"
                fill="none"
                stroke="#FF671D"
                strokeWidth="2.4"
                strokeLinecap="round"
              />
              <path
                d="M 10 10 Q 48 7, 82 10"
                fill="none"
                stroke="#FF671D"
                strokeWidth="1.6"
                strokeLinecap="round"
                opacity="0.65"
              />
            </svg>
          </div>
          <svg width="11" height="11" viewBox="0 0 18 18" fill="none" style={{ marginTop: '-4px' }}>
            <path d="M 4 14 L 14 4 M 7 4 H 14 V 11" stroke="#FF671D" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </a>

      {/* Middle-Right Hand-Sketched Clickable: Portfolio */}
      <a
        href="#about-project"
        className="dev-sketch-link"
        style={{
          position: 'absolute',
          top: '44%',
          right: '1%',
          transform: 'rotate(-2deg)',
          fontFamily: HAND_FONT,
          fontSize: '31px',
          fontWeight: 700,
          color: '#1E293B',
          display: 'inline-block',
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
          <span>Portfolio</span>
          <svg width="11" height="11" viewBox="0 0 18 18" fill="none" style={{ marginTop: '-2px' }}>
            <path d="M 4 14 L 14 4 M 7 4 H 14 V 11" stroke="#FF671D" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <svg
          width="88"
          height="10"
          viewBox="0 0 88 10"
          style={{ display: 'block', marginTop: '-4px' }}
        >
          <path
            d="M 2 6 Q 44 2, 86 6"
            fill="none"
            stroke="#FF671D"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
        </svg>
      </a>

      {/* Bottom-Right Hand-Sketched Clickable: GitHub + Hand-Drawn Octocat */}
      <a
        href="https://github.com/MoAb-01"
        target="_blank"
        rel="noopener noreferrer"
        className="dev-sketch-link"
        style={{
          position: 'absolute',
          bottom: '12%',
          right: '3%',
          transform: 'rotate(3deg)',
          fontFamily: HAND_FONT,
          fontSize: '31px',
          fontWeight: 700,
          color: '#1E293B',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
        }}
      >
        {/* Hand-sketched GitHub Octocat outline */}
        <svg
          width="28"
          height="28"
          viewBox="0 0 32 32"
          fill="none"
          style={{ position: 'relative', zIndex: 1, flexShrink: 0 }}
        >
          <path
            d="M 16 4.5 C 9.4 4.5, 4.5 9.6, 4.5 16.2 C 4.5 21.4, 7.8 25.8, 12.4 27.3 C 13 27.4, 13.2 27, 13.2 26.6 L 13.2 24 C 10 24.7, 9.3 22.6, 9.3 22.6 C 8.8 21.3, 8 20.9, 8 20.9 C 6.9 20.2, 8.1 20.2, 8.1 20.2 C 9.3 20.3, 9.9 21.5, 9.9 21.5 C 11 23.3, 12.7 22.8, 13.4 22.5 C 13.5 21.7, 13.8 21.2, 14.2 20.9 C 11.6 20.6, 8.9 19.6, 8.9 15.1 C 8.9 13.8, 9.4 12.8, 10.1 12 C 10 11.7, 9.6 10.5, 10.2 8.9 C 10.2 8.9, 11.2 8.6, 13.4 10.1 C 14.3 9.8, 15.3 9.7, 16.3 9.7 C 17.3 9.7, 18.3 9.8, 19.2 10.1 C 21.4 8.6, 22.4 8.9, 22.4 8.9 C 23 10.5, 22.6 11.7, 22.5 12 C 23.2 12.8, 23.7 13.8, 23.7 15.1 C 23.7 19.6, 21 20.6, 18.4 20.9 C 18.9 21.3, 19.3 22.1, 19.3 23.3 L 19.3 26.6 C 19.3 27, 19.5 27.4, 20.1 27.3 C 24.7 25.8, 28 21.4, 28 16.2 C 28 9.6, 22.8 4.5, 16 4.5 Z"
            stroke="#1E293B"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span style={{ position: 'relative', zIndex: 1 }}>GitHub</span>
        <svg width="11" height="11" viewBox="0 0 18 18" fill="none" style={{ marginTop: '-2px' }}>
          <path d="M 4 14 L 14 4 M 7 4 H 14 V 11" stroke="#FF671D" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </a>
    </div>
  );
};
