import { NextRequest, NextResponse } from 'next/server';
import axios from 'axios';
import { parseUnitCount } from '@/lib/utils';
import type { ShoppingResult } from '@/lib/types';

const SERPAPI_KEY = process.env.SERPAPI_KEY ?? '';

function generateDemoData(query: string): ShoppingResult[] {
  const q = query.trim();
  const encoded = encodeURIComponent(q);
  const stores: { name: string; basePrice: number; packs: number[]; discount: number; searchUrl: string }[] = [
    { name: 'Amazon', basePrice: 8.49, packs: [1, 6], discount: 0.85, searchUrl: `https://www.amazon.com/s?k=${encoded}` },
    { name: 'Walmart', basePrice: 7.97, packs: [1, 2], discount: 0.88, searchUrl: `https://www.walmart.com/search?q=${encoded}` },
    { name: 'Target', basePrice: 8.99, packs: [1], discount: 1, searchUrl: `https://www.target.com/s?searchTerm=${encoded}` },
    { name: 'Walgreens', basePrice: 9.99, packs: [1], discount: 1, searchUrl: `https://www.walgreens.com/search/results.jsp?Ntt=${encoded}` },
    { name: 'CVS', basePrice: 10.49, packs: [1], discount: 1, searchUrl: `https://www.cvs.com/search?searchTerm=${encoded}` },
    { name: 'iHerb', basePrice: 7.49, packs: [1, 3], discount: 0.90, searchUrl: `https://www.iherb.com/search?kw=${encoded}` },
    { name: 'Dollar General', basePrice: 7.50, packs: [1], discount: 1, searchUrl: `https://www.dollargeneral.com/search?q=${encoded}` },
    { name: 'Costco', basePrice: 34.99, packs: [8], discount: 0.82, searchUrl: `https://www.costco.com/CatalogSearch?keyword=${encoded}` },
    { name: "Sam's Club", basePrice: 32.99, packs: [6], discount: 0.84, searchUrl: `https://www.samsclub.com/search?searchTerm=${encoded}` },
  ];

  const results: ShoppingResult[] = [];
  let id = 1;

  for (const s of stores) {
    for (const pack of s.packs) {
      const rawTotal = s.basePrice * pack * (pack > 1 ? s.discount : 1);
      const price = Math.round(rawTotal * 100) / 100;
      const unitPrice = Math.round((price / pack) * 100) / 100;
      results.push({
        id: String(id++),
        title: pack > 1 ? `${q} (Pack of ${pack})` : q,
        store: s.name,
        price,
        unitCount: pack,
        unitPrice,
        link: s.searchUrl,
        thumbnail: '',
      });
    }
  }

  return results;
}

export async function GET(req: NextRequest) {
  const query = req.nextUrl.searchParams.get('q') ?? '';
  if (!query.trim()) {
    return NextResponse.json({ error: 'Missing query' }, { status: 400 });
  }

  if (!SERPAPI_KEY) {
    return NextResponse.json({ results: generateDemoData(query), demo: true });
  }

  try {
    const { data } = await axios.get('https://serpapi.com/search', {
      params: { engine: 'google_shopping', q: query, api_key: SERPAPI_KEY, num: 30 },
      timeout: 15000,
    });

    const results: ShoppingResult[] = (data.shopping_results ?? []).map(
      (item: Record<string, unknown>, idx: number) => {
        const price = (item.extracted_price as number) ?? 0;
        const unitCount = parseUnitCount((item.title as string) ?? '');
        return {
          id: String(idx + 1),
          title: (item.title as string) ?? '',
          store: (item.source as string) ?? 'Unknown',
          price,
          unitCount,
          unitPrice: Math.round((price / unitCount) * 100) / 100,
          link: ((item.product_link as string) || (item.link as string)) ?? '',
          thumbnail: (item.thumbnail as string) ?? '',
        } satisfies ShoppingResult;
      }
    );

    return NextResponse.json({ results, demo: false });
  } catch (err) {
    console.error('SerpAPI error:', err);
    return NextResponse.json({ results: generateDemoData(query), demo: true });
  }
}
