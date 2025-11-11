import { create } from "zustand";

export interface SymbolSelection {
  symbol: string;
  name: string;
}

interface AppState {
  selection?: SymbolSelection;
  setSelection: (value?: SymbolSelection) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  selection: undefined,
  setSelection: (value) => set({ selection: value }),
  activeTab: "trade",
  setActiveTab: (tab) => set({ activeTab: tab }),
}));
