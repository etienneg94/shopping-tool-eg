export interface ShoppingResult {
  id: string;
  title: string;
  store: string;
  price: number;
  unitCount: number;
  unitPrice: number;
  link: string;
  thumbnail?: string;
}

export interface CashbackData {
  rates: Record<string, number>;   // store → best rate %
  portals: Record<string, string>; // store → portal name
}

export interface CapitalOneOffer {
  id: string;
  store: string;
  minRate: number;
  maxRate: number;
}

export interface EnrichedResult extends ShoppingResult {
  cashbackRate: number;
  cashbackPortal: string;
  cashbackSource: 'cashbackmonitor' | 'capitalone' | 'none';
  effectivePrice: number;
  effectiveUnitPrice: number;
}
