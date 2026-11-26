import React from 'react';

interface StageStepperIconProps {
  step: 1 | 2 | 3 | 4;
}

export const StageStepperIcon: React.FC<StageStepperIconProps> = ({ step }) => {
  return (
    <div
      style={{
        width: '44px',
        height: '52px',
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        direction: 'ltr',
      }}
    >
      <style>{`
        @keyframes sentra-fov-ping {
          0%, 100% { opacity: 0.35; }
          50% { opacity: 0.95; }
        }
        @keyframes sentra-walk-x {
          0%, 100% { transform: translateX(0px); }
          50% { transform: translateX(7px); }
        }
        @keyframes sentra-ray-sweep {
          0%, 100% { stroke-dashoffset: 18; }
          50% { stroke-dashoffset: 0; }
        }
        @keyframes sentra-pulse-ring {
          0% { r: 3; opacity: 0.9; }
          100% { r: 9; opacity: 0; }
        }
        @keyframes sentra-crop-lock {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(0.92); }
        }
      `}</style>

      {step === 1 && (
        /* Stage 1: Sequential Relay Cascade (Node -> Hub -> Next Node in #FF5500) */
        <svg viewBox="0 0 44 52" width="44" height="52" fill="none">
          <style>{`
            /* Spoke line draws/lights up in sequence */
            @keyframes relay-spoke-1 {
              0%, 10% { stroke-dashoffset: 18; stroke: #CBD5E1; }
              20%, 85% { stroke-dashoffset: 0; stroke: #FF5500; }
              95%, 100% { stroke-dashoffset: 18; stroke: #CBD5E1; }
            }
            @keyframes relay-spoke-2 {
              0%, 28% { stroke-dashoffset: 20; stroke: #CBD5E1; }
              38%, 85% { stroke-dashoffset: 0; stroke: #FF5500; }
              95%, 100% { stroke-dashoffset: 20; stroke: #CBD5E1; }
            }
            @keyframes relay-spoke-3 {
              0%, 46% { stroke-dashoffset: 18; stroke: #CBD5E1; }
              56%, 85% { stroke-dashoffset: 0; stroke: #FF5500; }
              95%, 100% { stroke-dashoffset: 18; stroke: #CBD5E1; }
            }
            @keyframes relay-spoke-4 {
              0%, 64% { stroke-dashoffset: 18; stroke: #CBD5E1; }
              74%, 85% { stroke-dashoffset: 0; stroke: #FF5500; }
              95%, 100% { stroke-dashoffset: 18; stroke: #CBD5E1; }
            }

            /* Each node turns orange the instant the relay reaches it */
            @keyframes relay-node-0 {
              0%, 85% { stroke: #FF5500; }
              95%, 100% { stroke: #64748B; }
            }
            @keyframes relay-hub {
              0%, 18% { stroke: #0F172A; }
              22%, 85% { stroke: #FF5500; }
              95%, 100% { stroke: #0F172A; }
            }
            @keyframes relay-node-2 {
              0%, 36% { stroke: #64748B; }
              40%, 85% { stroke: #FF5500; }
              95%, 100% { stroke: #64748B; }
            }
            @keyframes relay-node-3 {
              0%, 54% { stroke: #64748B; }
              58%, 85% { stroke: #FF5500; }
              95%, 100% { stroke: #64748B; }
            }
            @keyframes relay-node-4 {
              0%, 72% { stroke: #64748B; }
              76%, 85% { stroke: #FF5500; }
              95%, 100% { stroke: #64748B; }
            }
          `}</style>

          {/* Base Inactive Spokes */}
          <g stroke="#CBD5E1" strokeWidth="1.4" strokeLinecap="round">
            <line x1="10" y1="14" x2="22" y2="26" />
            <line x1="22" y1="26" x2="35" y2="15" />
            <line x1="22" y1="26" x2="35" y2="35" />
            <line x1="22" y1="26" x2="8" y2="37" />
          </g>

          {/* Sequential #FF5500 Relay Spokes (1 -> Hub -> 2 -> 3 -> 4) */}
          <line
            x1="10" y1="14" x2="22" y2="26"
            stroke="#FF5500" strokeWidth="1.6" strokeLinecap="round"
            strokeDasharray="18"
            style={{ animation: 'relay-spoke-1 3.2s linear infinite' }}
          />
          <line
            x1="22" y1="26" x2="35" y2="15"
            stroke="#FF5500" strokeWidth="1.6" strokeLinecap="round"
            strokeDasharray="20"
            style={{ animation: 'relay-spoke-2 3.2s linear infinite' }}
          />
          <line
            x1="22" y1="26" x2="35" y2="35"
            stroke="#FF5500" strokeWidth="1.6" strokeLinecap="round"
            strokeDasharray="18"
            style={{ animation: 'relay-spoke-3 3.2s linear infinite' }}
          />
          <line
            x1="22" y1="26" x2="8" y2="37"
            stroke="#FF5500" strokeWidth="1.6" strokeLinecap="round"
            strokeDasharray="18"
            style={{ animation: 'relay-spoke-4 3.2s linear infinite' }}
          />

          {/* Outer Nodes Turning Orange Sequentially */}
          {/* Node 0 (Origin - Top Left) */}
          <circle
            cx="10" cy="14" r="3.6" fill="#FFFFFF" strokeWidth="1.6"
            style={{ animation: 'relay-node-0 3.2s linear infinite' }}
          />

          {/* Node 2 (Top Right) */}
          <circle
            cx="35" cy="15" r="2.8" fill="#FFFFFF" strokeWidth="1.6"
            style={{ animation: 'relay-node-2 3.2s linear infinite' }}
          />
          {/* Node 3 (Bottom Right) */}
          <circle
            cx="35" cy="35" r="3.5" fill="#FFFFFF" strokeWidth="1.6"
            style={{ animation: 'relay-node-3 3.2s linear infinite' }}
          />
          {/* Node 4 (Bottom Left) */}
          <circle
            cx="8" cy="37" r="2.5" fill="#FFFFFF" strokeWidth="1.6"
            style={{ animation: 'relay-node-4 3.2s linear infinite' }}
          />

          {/* Central Hub (Lights up after Node 0 reaches it) */}
          <circle
            cx="22" cy="26" r="5.5" fill="#FFFFFF" strokeWidth="1.7"
            style={{ animation: 'relay-hub 3.2s linear infinite' }}
          />
          <circle cx="22" cy="26" r="2" fill="#FF5500" />
        </svg>
      )}

      {step === 2 && (
        /* Stage 2: Local Detection Outside Zone (HITS: 2, Zero Alerts) */
        <svg viewBox="0 0 44 52" width="44" height="52" fill="none">
          <defs>
            <pattern id="step-hatch-2" width="5" height="5" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="5" stroke="#94A3B8" strokeWidth="1.1" strokeOpacity="0.45" />
            </pattern>
          </defs>
          <line x1="4" y1="42" x2="40" y2="42" stroke="#CBD5E1" strokeWidth="1.25" />

          {/* Restricted Zone Box */}
          <rect x="24" y="18" width="14" height="24" fill="url(#step-hatch-2)" stroke="#94A3B8" strokeWidth="1.25" />

          {/* Moving Target Dot + Even Ray Passing Through Both Polygon Edges */}
          <g style={{ animation: 'sentra-walk-x 2s ease-in-out infinite' }}>
            <line x1="10" y1="32" x2="41" y2="32" stroke="#FF5500" strokeWidth="1.1" strokeDasharray="2 2" />
            <circle cx="10" cy="32" r="3" fill="#FF5500" />
            <circle cx="24" cy="32" r="2" fill="#FFFFFF" stroke="#FF5500" strokeWidth="1.2" />
            <circle cx="38" cy="32" r="2" fill="#FFFFFF" stroke="#FF5500" strokeWidth="1.2" />
          </g>
        </svg>
      )}

      {step === 3 && (
        /* Stage 3: Zone Breach & 3-Frame Temporal Lock */
        <svg viewBox="0 0 44 52" width="44" height="52" fill="none">
          <defs>
            <pattern id="step-hatch-3" width="5" height="5" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="5" stroke="#FF5500" strokeWidth="1.2" strokeOpacity="0.65" />
            </pattern>
          </defs>
          <line x1="6" y1="6" x2="6" y2="46" stroke="#CBD5E1" strokeWidth="1.25" />
          <line x1="38" y1="6" x2="38" y2="46" stroke="#CBD5E1" strokeWidth="1.25" />

          {/* Active Hatched Zone */}
          <rect x="21" y="10" width="14" height="18" fill="url(#step-hatch-3)" stroke="#FF5500" strokeWidth="1.4" />

          {/* Path Crossing Into Zone */}
          <path d="M 13 42 L 13 31 C 13 25, 28 26, 28 20" stroke="#FF5500" strokeWidth="1.6" strokeLinecap="round" />

          {/* Odd Ray Intersection */}
          <line
            x1="28"
            y1="19"
            x2="40"
            y2="19"
            stroke="#FF5500"
            strokeWidth="1.25"
            strokeDasharray="3 2"
            style={{ animation: 'sentra-ray-sweep 1.4s linear infinite' }}
          />
          <circle cx="28" cy="19" r="3" fill="#FF5500" />
          <circle
            cx="28"
            cy="19"
            r="3"
            stroke="#FF5500"
            strokeWidth="1.2"
            style={{ animation: 'sentra-pulse-ring 1.5s ease-out infinite' }}
          />
        </svg>
      )}

      {step === 4 && (
        /* Stage 4: Dual-Crop RoI Encrypted & Queued */
        <svg viewBox="0 0 44 52" width="44" height="52" fill="none">
          <rect x="7" y="8" width="30" height="22" rx="2" stroke="#94A3B8" strokeWidth="1.25" />
          <g
            stroke="#FF5500"
            strokeWidth="1.6"
            strokeLinecap="round"
            style={{ transformOrigin: '22px 19px', animation: 'sentra-crop-lock 1.8s ease-in-out infinite' }}
          >
            <path d="M 15 16 L 15 12 L 19 12" />
            <path d="M 25 12 L 29 12 L 29 16" />
            <path d="M 15 22 L 15 26 L 19 26" />
            <path d="M 25 26 L 29 26 L 29 22" />
            <circle cx="22" cy="19" r="2" fill="#FF5500" stroke="none" />
          </g>
          <line x1="22" y1="30" x2="22" y2="36" stroke="#FF5500" strokeWidth="1.4" strokeDasharray="2 2" />
          <rect x="11" y="36" width="22" height="9" rx="2" fill="rgba(255,85,0,0.12)" stroke="#FF5500" strokeWidth="1.35" />
          <line x1="15" y1="40.5" x2="29" y2="40.5" stroke="#FF5500" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
      )}
    </div>
  );
};
