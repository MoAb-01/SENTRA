# SENTRA Frontend / Presentation Tier

A modern, responsive React + TypeScript frontend for the **SENTRA** platform, providing an operations portal and landing page interface with full multilingual support.

## Key Features

1. **Multilingual URL Endpoints**:
   - `/tr` & `/tr/portal`: Turkish interface
   - `/en` & `/en/portal`: English interface
   - `/ar` & `/ar/portal`: Arabic interface (with RTL layout support)
   - Dynamic language switching that reflects directly in the URL structure.

2. **Presentation & Operations Portal**:
   - Modern landing page adapted from initial design tokens (G-LAB Ar-Ge showcase, interactive cards, quick actions, responsive grid, angled brand footer).
   - Real-time **Operations & Control Desk** for grid edge telemetry, active incidents, substation metrics, and unit dispatch.

3. **Dual-Token Authentication Architecture** *(Security Standard Compliance)*:
   - **In-Memory Access Token**: Short-lived (15 min) token held strictly in memory, never in `localStorage`.
   - **Rotated Refresh Token**: Securely stored refresh token for silent renewals.
   - **Silent Renewal**: Background timer and 401 interception to silently renew the access token prior to expiration.
   - **Manual Rotation Trigger**: Quick administrative refresh action with token rotation safeguards.

## Getting Started

```bash
# Navigate to the frontend directory
cd sentra-frontend

# Install dependencies (already installed)
npm install

# Start Vite development server
npm run dev

# Build production bundle
npm run build
```
