export function parseUnitCount(title: string): number {
  const t = title.toLowerCase();
  const patterns = [
    /pack\s+of\s+(\d+)/,
    /(\d+)\s*[-–]?\s*pack/,
    /(\d+)\s*count/,
    /(\d+)\s*ct\.?(?:\s|,|$)/,
    /set\s+of\s+(\d+)/,
    /(\d+)\s*piece/,
    /(\d+)\s*bottles?/,
    /(\d+)\s*tubes?/,
    /(\d+)\s*jars?/,
  ];
  for (const re of patterns) {
    const m = t.match(re);
    if (m) {
      const n = parseInt(m[1]);
      if (n >= 2 && n <= 200) return n;
    }
  }
  return 1;
}

export function formatCurrency(n: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);
}

export function normalizeStore(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '');
}

// Maps common store display names → cashbackmonitor.com slug
export const STORE_SLUGS: Record<string, string> = {
  amazon: 'amazon',
  walmart: 'walmart',
  target: 'target',
  walgreens: 'walgreens',
  cvs: 'cvs-pharmacy',
  costco: 'costco',
  samsclub: 'sams-club',
  bjswholesale: 'bjs-wholesale-club',
  bjs: 'bjs-wholesale-club',
  ulta: 'ulta-beauty',
  iherb: 'iherb',
  vitaminshoppe: 'vitamin-shoppe',
  dollargeneral: 'dollar-general',
  kroger: 'kroger',
  rite: 'rite-aid',
  riteaid: 'rite-aid',
};

export function getStoreSlug(storeName: string): string | null {
  const key = normalizeStore(storeName);
  if (STORE_SLUGS[key]) return STORE_SLUGS[key];
  // partial match
  for (const [k, slug] of Object.entries(STORE_SLUGS)) {
    if (key.includes(k) || k.includes(key)) return slug;
  }
  return null;
}

// Fallback cashback data when scraping fails
export const FALLBACK_CASHBACK: Record<string, { rate: number; portal: string }> = {
  amazon: { rate: 5.0, portal: 'Rakuten' },
  walmart: { rate: 3.5, portal: 'Rakuten' },
  target: { rate: 4.0, portal: 'BeFrugal' },
  walgreens: { rate: 7.0, portal: 'TopCashback' },
  cvs: { rate: 5.0, portal: 'Rakuten' },
  iherb: { rate: 8.0, portal: 'TopCashback' },
  dollargeneral: { rate: 2.0, portal: 'Rakuten' },
  costco: { rate: 1.0, portal: 'BeFrugal' },
  ulta: { rate: 6.0, portal: 'TopCashback' },
  vitaminshoppe: { rate: 5.0, portal: 'Rakuten' },
  samsclub: { rate: 1.5, portal: 'Rakuten' },
};
