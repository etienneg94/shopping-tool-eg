'use client';

import { useState, useEffect, useCallback } from 'react';
import type { ShoppingResult, EnrichedResult, CapitalOneOffer } from '@/lib/types';
import { formatCurrency } from '@/lib/utils';

type SortKey = 'effectiveUnitPrice' | 'unitPrice' | 'cashbackRate' | 'price';

const MEDAL = ['🥇', '🥈', '🥉'];

export default function Home() {
  const [query, setQuery] = useState('got2b gel');
  const [inputValue, setInputValue] = useState('got2b gel');
  const [results, setResults] = useState<ShoppingResult[]>([]);
  const [cashbackRates, setCashbackRates] = useState<Record<string, number>>({});
  const [cashbackPortals, setCashbackPortals] = useState<Record<string, string>>({});
  const [capitalOneOffers, setCapitalOneOffers] = useState<CapitalOneOffer[]>([]);
  const [sortBy, setSortBy] = useState<SortKey>('effectiveUnitPrice');
  const [loading, setLoading] = useState(false);
  const [cashbackLoading, setCashbackLoading] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [useMaxRate, setUseMaxRate] = useState(true);

  // New offer form state
  const [offerStore, setOfferStore] = useState('');
  const [offerMin, setOfferMin] = useState('');
  const [offerMax, setOfferMax] = useState('');
  const [offerError, setOfferError] = useState('');

  const fetchPrices = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setResults([]);
    setCashbackRates({});
    setCashbackPortals({});
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      setResults(data.results ?? []);
      setIsDemo(data.demo ?? false);
    } catch {
      console.error('Search failed');
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-search on mount with default query
  useEffect(() => { fetchPrices(query); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch cashback rates whenever results change
  useEffect(() => {
    if (results.length === 0) return;
    const stores = Array.from(new Set(results.map((r) => r.store)));
    setCashbackLoading(true);
    fetch(`/api/cashback?stores=${encodeURIComponent(stores.join(','))}`)
      .then((r) => r.json())
      .then((data) => {
        setCashbackRates(data.rates ?? {});
        setCashbackPortals(data.portals ?? {});
      })
      .finally(() => setCashbackLoading(false));
  }, [results]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setQuery(inputValue);
    fetchPrices(inputValue);
  };

  const addOffer = () => {
    setOfferError('');
    const store = offerStore.trim();
    if (!store) { setOfferError('Store name required'); return; }
    const min = parseFloat(offerMin);
    const max = parseFloat(offerMax || offerMin);
    if (isNaN(min) || isNaN(max) || min < 0 || max < 0 || min > max) {
      setOfferError('Enter a valid rate or range (e.g. 5 or 5–8)');
      return;
    }
    setCapitalOneOffers((prev) => [
      ...prev.filter((o) => o.store.toLowerCase() !== store.toLowerCase()),
      { id: Date.now().toString(), store, minRate: min, maxRate: max },
    ]);
    setOfferStore('');
    setOfferMin('');
    setOfferMax('');
  };

  const removeOffer = (id: string) =>
    setCapitalOneOffers((prev) => prev.filter((o) => o.id !== id));

  // Enrich results with cashback
  const enriched: EnrichedResult[] = results.map((r) => {
    const offer = capitalOneOffers.find(
      (o) => o.store.toLowerCase() === r.store.toLowerCase()
    );
    let cashbackRate: number;
    let cashbackPortal: string;
    let cashbackSource: EnrichedResult['cashbackSource'];

    if (offer) {
      cashbackRate = useMaxRate ? offer.maxRate : offer.minRate;
      cashbackPortal = `Capital One Shopping (${offer.minRate === offer.maxRate ? `${offer.minRate}%` : `${offer.minRate}–${offer.maxRate}%`})`;
      cashbackSource = 'capitalone';
    } else if (cashbackRates[r.store] > 0) {
      cashbackRate = cashbackRates[r.store];
      cashbackPortal = cashbackPortals[r.store] || 'CashbackMonitor';
      cashbackSource = 'cashbackmonitor';
    } else {
      cashbackRate = 0;
      cashbackPortal = '';
      cashbackSource = 'none';
    }

    const multiplier = 1 - cashbackRate / 100;
    return {
      ...r,
      cashbackRate,
      cashbackPortal,
      cashbackSource,
      effectivePrice: Math.round(r.price * multiplier * 100) / 100,
      effectiveUnitPrice: Math.round(r.unitPrice * multiplier * 100) / 100,
    };
  });

  const sorted = [...enriched].sort((a, b) => {
    if (sortBy === 'effectiveUnitPrice') return a.effectiveUnitPrice - b.effectiveUnitPrice;
    if (sortBy === 'unitPrice') return a.unitPrice - b.unitPrice;
    if (sortBy === 'cashbackRate') return b.cashbackRate - a.cashbackRate;
    if (sortBy === 'price') return a.price - b.price;
    return 0;
  });

  const uniqueStores = Array.from(new Set(results.map((r) => r.store))).sort();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gray-900 text-white py-6 px-4 shadow-lg">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold tracking-tight">Smart Shopping Price Tracker</h1>
          <p className="text-gray-400 text-sm mt-1">
            Compare prices across stores with bulk pricing and cashback analysis
          </p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Search */}
        <form onSubmit={handleSearch} className="flex gap-3">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Search for a product…"
            className="flex-1 rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </form>

        {isDemo && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <strong>Demo mode</strong> — no SerpAPI key found. Showing sample prices. Add{' '}
            <code className="rounded bg-amber-100 px-1">SERPAPI_KEY</code> to{' '}
            <code className="rounded bg-amber-100 px-1">.env.local</code> for live data.
          </div>
        )}

        {/* Results table */}
        {results.length > 0 && (
          <section className="rounded-2xl bg-white shadow-sm border border-gray-100 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-gray-900">
                  {results.length} results for &ldquo;{query}&rdquo;
                </h2>
                {cashbackLoading && (
                  <span className="text-xs text-gray-400 animate-pulse">Loading cashback…</span>
                )}
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-500">Sort by:</span>
                {(
                  [
                    ['effectiveUnitPrice', 'Best deal/unit'],
                    ['unitPrice', 'Price/unit'],
                    ['cashbackRate', 'Cashback %'],
                    ['price', 'Total price'],
                  ] as [SortKey, string][]
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setSortBy(key)}
                    className={`rounded-lg px-3 py-1.5 font-medium transition-colors ${
                      sortBy === key
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
                    <th className="px-4 py-3 text-left w-8">#</th>
                    <th className="px-4 py-3 text-left">Store</th>
                    <th className="px-4 py-3 text-left">Product</th>
                    <th className="px-4 py-3 text-right">Total Price</th>
                    <th className="px-4 py-3 text-center">Pack</th>
                    <th className="px-4 py-3 text-right">Price / Unit</th>
                    <th className="px-4 py-3 text-center">Cashback</th>
                    <th className="px-4 py-3 text-right font-bold text-gray-700">Eff. Price / Unit</th>
                    <th className="px-4 py-3 text-center"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {sorted.map((r, idx) => {
                    const isTop = idx < 3;
                    const isBest = idx === 0;
                    return (
                      <tr
                        key={r.id}
                        className={`transition-colors hover:bg-gray-50 ${
                          isBest ? 'bg-green-50' : ''
                        }`}
                      >
                        <td className="px-4 py-3 text-center">
                          {isTop ? (
                            <span className="text-lg">{MEDAL[idx]}</span>
                          ) : (
                            <span className="text-gray-400">{idx + 1}</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-medium text-gray-900">{r.store}</span>
                        </td>
                        <td className="px-4 py-3 max-w-xs">
                          <span
                            className="text-gray-700 truncate block"
                            title={r.title}
                          >
                            {r.title}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right text-gray-700">
                          {formatCurrency(r.price)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {r.unitCount > 1 ? (
                            <span className="rounded-full bg-blue-100 text-blue-700 px-2 py-0.5 text-xs font-semibold">
                              {r.unitCount}-pack
                            </span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-700">
                          {formatCurrency(r.unitPrice)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {r.cashbackRate > 0 ? (
                            <div className="flex flex-col items-center gap-0.5">
                              <span
                                className={`font-semibold ${
                                  r.cashbackSource === 'capitalone'
                                    ? 'text-purple-700'
                                    : 'text-green-700'
                                }`}
                              >
                                {r.cashbackRate}%
                              </span>
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                                  r.cashbackSource === 'capitalone'
                                    ? 'bg-purple-100 text-purple-600'
                                    : 'bg-green-100 text-green-600'
                                }`}
                              >
                                {r.cashbackSource === 'capitalone' ? 'Capital One' : 'CashbackMonitor'}
                              </span>
                            </div>
                          ) : (
                            <span className="text-gray-400 text-xs">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span
                            className={`text-base font-bold ${
                              isBest ? 'text-green-700' : 'text-gray-900'
                            }`}
                          >
                            {formatCurrency(r.effectiveUnitPrice)}
                          </span>
                          {r.cashbackRate > 0 && (
                            <div className="text-[10px] text-gray-400">
                              saves {formatCurrency(r.unitPrice - r.effectiveUnitPrice)}/unit
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {r.link !== '#' && (
                            <a
                              href={r.link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:text-blue-700 text-xs font-medium"
                            >
                              View →
                            </a>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {loading && (
          <div className="text-center py-16 text-gray-400">Searching for prices…</div>
        )}

        {/* Capital One Shopping Overrides */}
        {results.length > 0 && (
          <section className="rounded-2xl bg-white shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 bg-purple-50">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-purple-100 p-2">
                  <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                  </svg>
                </div>
                <div>
                  <h2 className="font-semibold text-gray-900">Capital One Shopping Offers</h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Override cashback rates with offers you received — supports ranges like 6–8%
                  </p>
                </div>
              </div>
            </div>

            <div className="px-6 py-5 space-y-4">
              {/* Rate mode toggle */}
              <div className="flex items-center gap-3 text-sm">
                <span className="text-gray-600">When a range is given, use:</span>
                <button
                  onClick={() => setUseMaxRate(true)}
                  className={`rounded-lg px-3 py-1.5 font-medium transition-colors ${
                    useMaxRate ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Max rate (optimistic)
                </button>
                <button
                  onClick={() => setUseMaxRate(false)}
                  className={`rounded-lg px-3 py-1.5 font-medium transition-colors ${
                    !useMaxRate ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Min rate (conservative)
                </button>
              </div>

              {/* Add offer form */}
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Add an offer
                </p>
                <div className="flex flex-wrap gap-3 items-end">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500">Store</label>
                    <select
                      value={offerStore}
                      onChange={(e) => setOfferStore(e.target.value)}
                      className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 min-w-[160px]"
                    >
                      <option value="">Select a store…</option>
                      {uniqueStores.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500">Min rate %</label>
                    <input
                      type="number"
                      min="0"
                      max="50"
                      step="0.1"
                      placeholder="e.g. 5"
                      value={offerMin}
                      onChange={(e) => setOfferMin(e.target.value)}
                      className="w-24 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500">Max rate % (optional)</label>
                    <input
                      type="number"
                      min="0"
                      max="50"
                      step="0.1"
                      placeholder="e.g. 8"
                      value={offerMax}
                      onChange={(e) => setOfferMax(e.target.value)}
                      className="w-24 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                  </div>
                  <button
                    onClick={addOffer}
                    className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-700 transition-colors"
                  >
                    Add Override
                  </button>
                </div>
                {offerError && (
                  <p className="mt-2 text-xs text-red-600">{offerError}</p>
                )}
              </div>

              {/* Current overrides */}
              {capitalOneOffers.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">
                  No overrides yet — add an offer above
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {capitalOneOffers.map((o) => (
                    <div
                      key={o.id}
                      className="flex items-center gap-2 rounded-full bg-purple-50 border border-purple-200 px-3 py-1.5 text-sm"
                    >
                      <span className="font-medium text-purple-900">{o.store}</span>
                      <span className="text-purple-700">
                        {o.minRate === o.maxRate
                          ? `${o.minRate}%`
                          : `${o.minRate}–${o.maxRate}%`}
                      </span>
                      <button
                        onClick={() => removeOffer(o.id)}
                        className="text-purple-400 hover:text-purple-700 transition-colors"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>
        )}

        {/* Legend */}
        {results.length > 0 && (
          <div className="flex flex-wrap gap-4 text-xs text-gray-500 pb-4">
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-green-400"></span>
              CashbackMonitor rate
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-purple-400"></span>
              Capital One Shopping override
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-blue-400"></span>
              Bulk / multi-pack
            </div>
            <span className="ml-auto">
              Eff. Price / Unit = (Unit Price) × (1 − Cashback%)
            </span>
          </div>
        )}
      </main>
    </div>
  );
}
