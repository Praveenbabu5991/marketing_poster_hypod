import { create } from 'zustand';

export interface CreditsInfo {
  balance: number;
  plan: string;
  monthly_allowance: number;
  resets_at: string | null;
}

interface AppState {
  token: string;
  selectedBrandId: string | null;
  credits: CreditsInfo | null;
  setToken: (token: string) => void;
  setSelectedBrandId: (id: string | null) => void;
  setCredits: (credits: CreditsInfo | null) => void;
  refreshCredits: () => Promise<void>;
}

// Pre-generated test JWT (HS256 with "test-secret"):
// {"sub":"12345678-1234-1234-1234-123456789012","email":"test@example.com","name":"Test User","cognito:groups":["Hylancer","ADMIN"]}
const TEST_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3OC0xMjM0LTEyMzQtMTIzNC0xMjM0NTY3ODkwMTIiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJuYW1lIjoiVGVzdCBVc2VyIiwiY29nbml0bzpncm91cHMiOlsiSHlsYW5jZXIiLCJBRE1JTiJdfQ.eIRHIRZXObodv30TQ1r0YiznQpZ4WkxSj7L5MFmivpc';

export const useStore = create<AppState>()((set, get) => ({
  token: TEST_TOKEN,
  selectedBrandId: null,
  credits: null,
  setToken: (token) => set({ token }),
  setSelectedBrandId: (id) => set({ selectedBrandId: id }),
  setCredits: (credits) => set({ credits }),
  refreshCredits: async () => {
    const token = get().token;
    if (!token) return;
    try {
      const res = await fetch('/api/v1/credits/balance', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      set({
        credits: {
          balance: data.balance,
          plan: data.plan,
          monthly_allowance: data.monthly_allowance,
          resets_at: data.resets_at,
        },
      });
    } catch {
      /* non-fatal */
    }
  },
}));
