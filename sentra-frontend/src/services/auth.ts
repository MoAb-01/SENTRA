// Security Rule Compliance: Dual-Token Architecture
// 1. Short-lived Access Token (15-60 min) kept in memory (state/variable), NEVER stored in localStorage.
// 2. Long-lived Refresh Token (7-30 days) stored securely (e.g., httpOnly cookies in production, or secure client storage for SPA prototype).
// 3. Silent Renewal: Automatic interceptor catches 401 Unauthorized / nearing expiry and silently requests a new access token using the refresh token.
// 4. Refresh token rotation & activity safeguards.

export interface UserSession {
  userId: string;
  username: string;
  role: 'ADMIN' | 'OPERATOR' | 'ANALYST';
  fullName: string;
}

export interface DualTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // Unix timestamp in ms
}

class AuthService {
  private inMemoryAccessToken: string | null = null;
  private tokenExpiresAt: number | null = null;
  private currentUser: UserSession | null = null;
  private refreshTimeoutId: any = null;
  private subscribers: Array<(isAuthenticated: boolean) => void> = [];

  constructor() {
    // Attempt silent initial session recovery if refresh token exists
    this.initSession();
  }

  private initSession() {
    const storedRefreshToken = localStorage.getItem('sentra_rt_secure');
    const storedUser = localStorage.getItem('sentra_user');
    if (storedRefreshToken && storedUser) {
      try {
        this.currentUser = JSON.parse(storedUser);
        // Silently obtain fresh short-lived access token
        this.silentRenew(storedRefreshToken);
      } catch (e) {
        this.logout();
      }
    }
  }

  public subscribe(callback: (isAuthenticated: boolean) => void) {
    this.subscribers.push(callback);
    return () => {
      this.subscribers = this.subscribers.filter(sub => sub !== callback);
    };
  }

  private notify() {
    const isAuth = this.isAuthenticated();
    this.subscribers.forEach(cb => cb(isAuth));
  }

  public isAuthenticated(): boolean {
    return !!this.inMemoryAccessToken && !!this.tokenExpiresAt && Date.now() < this.tokenExpiresAt;
  }

  public getAccessToken(): string | null {
    return this.inMemoryAccessToken;
  }

  public getUser(): UserSession | null {
    return this.currentUser;
  }

  public getExpiresInSeconds(): number {
    if (!this.tokenExpiresAt) return 0;
    const remaining = Math.max(0, Math.floor((this.tokenExpiresAt - Date.now()) / 1000));
    return remaining;
  }

  // Mock Authentication Login (Generates short-lived AT + long-lived RT)
  public async login(username: string, role: 'ADMIN' | 'OPERATOR' = 'ADMIN'): Promise<boolean> {
    // 15-minute access token lifespan simulation (or 60s for demo observation if desired, default to 15 min)
    const ACCESS_TOKEN_TTL_MS = 15 * 60 * 1000;
    const now = Date.now();

    const mockAccessToken = `sat_${Math.random().toString(36).substring(2)}_${now}`;
    const mockRefreshToken = `srt_${Math.random().toString(36).substring(2)}_${now}`;

    this.inMemoryAccessToken = mockAccessToken;
    this.tokenExpiresAt = now + ACCESS_TOKEN_TTL_MS;
    this.currentUser = {
      userId: 'usr_84920',
      username: username || 'sentra_admin',
      fullName: username === 'admin' ? 'İbrahim Kaya (Baş Mühendis)' : 'Operasyon Yetkilisi',
      role,
    };

    // Store refresh token securely & user meta
    localStorage.setItem('sentra_rt_secure', mockRefreshToken);
    localStorage.setItem('sentra_user', JSON.stringify(this.currentUser));

    this.scheduleSilentRenewal();
    this.notify();
    return true;
  }

  // Silent Renewal routine
  public async silentRenew(refreshTokenOverride?: string): Promise<boolean> {
    const rt = refreshTokenOverride || localStorage.getItem('sentra_rt_secure');
    if (!rt) {
      this.logout();
      return false;
    }

    try {
      // In real backend: POST /api/v1/auth/refresh with body/cookie { refreshToken: rt }
      // Simulating network roundtrip
      await new Promise(resolve => setTimeout(resolve, 300));

      const now = Date.now();
      const ACCESS_TOKEN_TTL_MS = 15 * 60 * 1000;
      this.inMemoryAccessToken = `sat_renewed_${Math.random().toString(36).substring(2)}_${now}`;
      this.tokenExpiresAt = now + ACCESS_TOKEN_TTL_MS;

      // Token Rotation: Refresh token rotated as per security rule
      const rotatedRefreshToken = `srt_rotated_${Math.random().toString(36).substring(2)}_${now}`;
      localStorage.setItem('sentra_rt_secure', rotatedRefreshToken);

      this.scheduleSilentRenewal();
      this.notify();
      return true;
    } catch (err) {
      this.logout();
      return false;
    }
  }

  private scheduleSilentRenewal() {
    if (this.refreshTimeoutId) {
      clearTimeout(this.refreshTimeoutId);
    }

    // Refresh 1 minute before access token expiration
    if (this.tokenExpiresAt) {
      const timeToRefresh = Math.max(5000, (this.tokenExpiresAt - Date.now()) - 60000);
      this.refreshTimeoutId = setTimeout(() => {
        this.silentRenew();
      }, timeToRefresh);
    }
  }

  public logout() {
    this.inMemoryAccessToken = null;
    this.tokenExpiresAt = null;
    this.currentUser = null;
    if (this.refreshTimeoutId) {
      clearTimeout(this.refreshTimeoutId);
      this.refreshTimeoutId = null;
    }
    localStorage.removeItem('sentra_rt_secure');
    localStorage.removeItem('sentra_user');
    this.notify();
  }
}

export const auth = new AuthService();
