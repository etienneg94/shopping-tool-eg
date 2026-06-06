import { NextRequest, NextResponse } from 'next/server';
import axios from 'axios';
import * as cheerio from 'cheerio';
import { getStoreSlug, normalizeStore, FALLBACK_CASHBACK } from '@/lib/utils';

// Simple in-memory cache: storeKey → { rate, portal, expires }
const cache = new Map<string, { rate: number; portal: string; expires: number }>();
const CACHE_TTL = 60 * 60 * 1000; // 1 hour

async function fetchCashbackRate(store: string): Promise<{ rate: number; portal: string }> {
  const key = normalizeStore(store);
  const cached = cache.get(key);
  if (cached && cached.expires > Date.now()) {
    return { rate: cached.rate, portal: cached.portal };
  }

  const slug = getStoreSlug(store);
  if (!slug) {
    return FALLBACK_CASHBACK[key] ?? { rate: 0, portal: '' };
  }

  try {
    const { data } = await axios.get(
      `https://www.cashbackmonitor.com/cashback/${slug}/`,
      {
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
            '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
          Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.5',
        },
        timeout: 10000,
      }
    );

    const $ = cheerio.load(data as string);
    let maxRate = 0;
    let bestPortal = '';

    // Generic extraction: scan page text for all "X%" patterns
    const bodyText = $.text();
    const pctPattern = /(\d+(?:\.\d+)?)\s*%/g;
    let m: RegExpExecArray | null;
    while ((m = pctPattern.exec(bodyText)) !== null) {
      const r = parseFloat(m[1]);
      if (r > maxRate && r <= 40) maxRate = r;
    }

    if (maxRate === 0) {
      const fb = FALLBACK_CASHBACK[key];
      if (fb) return fb;
    }

    const result = { rate: maxRate, portal: bestPortal };
    cache.set(key, { ...result, expires: Date.now() + CACHE_TTL });
    return result;
  } catch {
    const fb = FALLBACK_CASHBACK[key];
    if (fb) return fb;
    return { rate: 0, portal: '' };
  }
}

export async function GET(req: NextRequest) {
  const storesParam = req.nextUrl.searchParams.get('stores') ?? '';
  const stores = storesParam
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  if (stores.length === 0) {
    return NextResponse.json({ rates: {}, portals: {} });
  }

  const entries = await Promise.all(
    stores.map(async (store) => {
      const { rate, portal } = await fetchCashbackRate(store);
      return { store, rate, portal };
    })
  );

  const rates: Record<string, number> = {};
  const portals: Record<string, string> = {};
  for (const e of entries) {
    rates[e.store] = e.rate;
    portals[e.store] = e.portal;
  }

  return NextResponse.json({ rates, portals });
}
