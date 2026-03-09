import { create } from 'zustand';

interface AppState {
  token: string;
  selectedBrandId: string | null;
  setToken: (token: string) => void;
  setSelectedBrandId: (id: string | null) => void;
}

// Pre-generated test JWT (HS256 with "test-secret"):
// {"sub":"12345678-1234-1234-1234-123456789012","email":"test@example.com","name":"Test User","cognito:groups":["Hylancer"]}
const TEST_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3OC0xMjM0LTEyMzQtMTIzNC0xMjM0NTY3ODkwMTIiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJuYW1lIjoiVGVzdCBVc2VyIiwiY29nbml0bzpncm91cHMiOlsiSHlsYW5jZXIiXX0.pDAg_YWskv-Uxh7rnbgIDDuiPMXPbSNC8-lbv5xLVAQ';

export const useStore = create<AppState>()((set) => ({
  token: TEST_TOKEN,
  selectedBrandId: null,
  setToken: (token) => set({ token }),
  setSelectedBrandId: (id) => set({ selectedBrandId: id }),
}));
