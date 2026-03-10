import { useState, type FormEvent } from 'react';
import type { Brand, BrandCreate } from '../types';
import { uploadLogo } from '../api/brands';

interface Props {
  initial?: Brand;
  onSubmit: (data: BrandCreate) => void;
  loading: boolean;
}

const INDUSTRIES = [
  'Technology',
  'Fashion & Apparel',
  'Food & Beverage',
  'Health & Wellness',
  'Beauty & Cosmetics',
  'Education',
  'Finance & Banking',
  'Real Estate',
  'Travel & Hospitality',
  'Automotive',
  'Entertainment & Media',
  'Sports & Fitness',
  'Home & Living',
  'E-commerce & Retail',
  'Non-Profit & Social',
  'Other',
];

const TONES = [
  'creative',
  'professional',
  'casual',
  'playful',
  'luxurious',
  'bold',
  'minimalist',
  'friendly',
  'authoritative',
];

const COLOR_PALETTES: { name: string; colors: string[] }[] = [
  { name: 'Sunset',     colors: ['#FF6B6B', '#FEC89A', '#FFD93D', '#C1FFD7'] },
  { name: 'Ocean',      colors: ['#0077B6', '#00B4D8', '#90E0EF', '#CAF0F8'] },
  { name: 'Forest',     colors: ['#2D6A4F', '#40916C', '#52B788', '#95D5B2'] },
  { name: 'Purple',     colors: ['#7209B7', '#9D4EDD', '#C77DFF', '#E0AAFF'] },
  { name: 'Coral',      colors: ['#FF6B6B', '#F472B6', '#FB7185', '#FECDD3'] },
  { name: 'Midnight',   colors: ['#1A1B2E', '#2D3154', '#6366F1', '#A5B4FC'] },
  { name: 'Golden',     colors: ['#B8860B', '#DAA520', '#FFD700', '#FFF8DC'] },
  { name: 'Monochrome', colors: ['#1A1A1A', '#4A4A4A', '#7A7A7A', '#DADADA'] },
];

export function BrandForm({ initial, onSubmit, loading }: Props) {
  const [name, setName] = useState(initial?.name ?? '');
  const [industry, setIndustry] = useState(initial?.industry ?? '');
  const [overview, setOverview] = useState(initial?.overview ?? '');
  const [tone, setTone] = useState(initial?.tone ?? 'creative');
  const [targetAudience, setTargetAudience] = useState(initial?.target_audience ?? '');
  const [productsServices, setProductsServices] = useState(initial?.products_services ?? '');
  const [logoPath, setLogoPath] = useState(initial?.logo_path ?? '');
  const [logoUrl, setLogoUrl] = useState(initial?.logo_path ? toDisplayUrl(initial.logo_path) : '');
  const defaultPalette = COLOR_PALETTES[0]; // Sunset
  const [colors, setColors] = useState<string[]>(
    initial?.colors?.length ? initial.colors : defaultPalette.colors.map((c) => c.toLowerCase()),
  );
  const [primaryColor, setPrimaryColor] = useState(
    initial?.colors?.[0] ?? defaultPalette.colors[0].toLowerCase(),
  );
  const [secondaryColor, setSecondaryColor] = useState(
    initial?.colors?.[1] ?? defaultPalette.colors[1].toLowerCase(),
  );
  const [selectedPalette, setSelectedPalette] = useState<string | null>(
    initial?.colors?.length ? null : defaultPalette.name,
  );
  const [logoColors, setLogoColors] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);

  function toDisplayUrl(path: string): string {
    // Extract relative URL from absolute container paths like /app/uploads/logos/...
    // or already-relative paths like /uploads/logos/...
    const genIdx = path.lastIndexOf('/generated/');
    if (genIdx !== -1) return path.slice(genIdx);
    const uplIdx = path.lastIndexOf('/uploads/');
    if (uplIdx !== -1) return path.slice(uplIdx);
    return path;
  }

  async function handleLogoUpload(file: File) {
    setUploading(true);
    try {
      const res = await uploadLogo(file);
      setLogoPath(res.logo_path);
      setLogoUrl(res.url);
      if (res.colors.length > 0) {
        setLogoColors(res.colors);
        setSelectedPalette(null);
        // Auto-select first two as primary/secondary
        const p = res.colors[0];
        const s = res.colors[1] ?? res.colors[0];
        setPrimaryColor(p);
        setSecondaryColor(s);
        setColors([p, s, ...res.colors.slice(2)]);
      }
    } finally {
      setUploading(false);
    }
  }

  function handleLogoColorClick(hex: string) {
    let p = primaryColor;
    let s = secondaryColor;

    if (p === hex) {
      // Already primary → swap: make it secondary, promote secondary to primary
      p = s;
      s = hex;
    } else {
      // Set as secondary (primary stays, secondary changes)
      s = hex;
    }

    setPrimaryColor(p);
    setSecondaryColor(s);
    setSelectedPalette(null);
    const remaining = logoColors.filter((c) => c !== p && c !== s);
    setColors([p, s, ...remaining]);
  }

  function handlePaletteSelect(palette: typeof COLOR_PALETTES[number]) {
    setSelectedPalette(palette.name);
    const p = palette.colors[0].toLowerCase();
    const s = palette.colors[1].toLowerCase();
    setPrimaryColor(p);
    setSecondaryColor(s);
    setColors(palette.colors.map((c) => c.toLowerCase()));
  }

  function handlePrimaryChange(hex: string) {
    setPrimaryColor(hex);
    setSelectedPalette(null);
    setColors((prev) => {
      const next = [...prev];
      next[0] = hex;
      if (next.length < 2) next.push(secondaryColor);
      return next;
    });
  }

  function handleSecondaryChange(hex: string) {
    setSecondaryColor(hex);
    setSelectedPalette(null);
    setColors((prev) => {
      const next = [...prev];
      if (next.length < 1) next.push(primaryColor);
      if (next.length < 2) next.push(hex);
      else next[1] = hex;
      return next;
    });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const allColors = colors.length >= 2 ? [...colors] : [primaryColor, secondaryColor];
    onSubmit({
      name,
      industry: industry || undefined,
      overview: overview || undefined,
      tone,
      target_audience: targetAudience || undefined,
      products_services: productsServices || undefined,
      logo_path: logoPath || undefined,
      colors: allColors,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Name */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">
          Brand Name <span className="text-accent">*</span>
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          maxLength={255}
          className="w-full rounded-lg border border-border bg-bg-page px-4 py-2.5 text-text-primary focus:border-accent focus:outline-none"
        />
      </div>

      {/* Industry */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">Industry</label>
        <select
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="w-full rounded-lg border border-border bg-bg-page px-4 py-2.5 text-text-primary focus:border-accent focus:outline-none"
        >
          <option value="">Select industry...</option>
          {INDUSTRIES.map((ind) => (
            <option key={ind} value={ind}>
              {ind}
            </option>
          ))}
        </select>
      </div>

      {/* Overview */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">Overview</label>
        <textarea
          value={overview}
          onChange={(e) => setOverview(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-border bg-bg-page px-4 py-2.5 text-text-primary focus:border-accent focus:outline-none"
        />
      </div>

      {/* Tone */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">
          Tone <span className="text-accent">*</span>
        </label>
        <select
          value={tone}
          onChange={(e) => setTone(e.target.value)}
          className="w-full rounded-lg border border-border bg-bg-page px-4 py-2.5 text-text-primary focus:border-accent focus:outline-none"
        >
          {TONES.map((t) => (
            <option key={t} value={t}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Target Audience */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">Target Audience</label>
        <input
          type="text"
          value={targetAudience}
          onChange={(e) => setTargetAudience(e.target.value)}
          className="w-full rounded-lg border border-border bg-bg-page px-4 py-2.5 text-text-primary focus:border-accent focus:outline-none"
        />
      </div>

      {/* Products / Services */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">
          Products / Services
        </label>
        <textarea
          value={productsServices}
          onChange={(e) => setProductsServices(e.target.value)}
          rows={2}
          className="w-full rounded-lg border border-border bg-bg-page px-4 py-2.5 text-text-primary focus:border-accent focus:outline-none"
        />
      </div>

      {/* Logo Upload */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">Logo</label>
        {logoUrl ? (
          <div className="flex items-center gap-4">
            <div className="group relative">
              <img
                src={logoUrl}
                alt="Logo preview"
                className="h-16 rounded border border-border object-contain"
              />
              <button
                type="button"
                onClick={() => {
                  setLogoPath('');
                  setLogoUrl('');
                  setLogoColors([]);
                }}
                className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100"
              >
                x
              </button>
            </div>
            <label className="cursor-pointer rounded-lg border border-border bg-bg-elevated px-4 py-2 text-sm text-text-primary transition-colors hover:bg-bg-page">
              Change Logo
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleLogoUpload(file);
                }}
              />
            </label>
          </div>
        ) : (
          <input
            type="file"
            accept="image/*"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleLogoUpload(file);
            }}
            className="text-sm text-text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-accent file:px-4 file:py-2 file:text-sm file:text-white file:cursor-pointer"
          />
        )}
      </div>

      {/* Brand Colors */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">Brand Colors</label>

        {/* Colors extracted from logo */}
        {logoColors.length > 0 && (
          <div className="mb-3">
            <span className="text-xs text-text-muted">Colors from your logo — click to set primary & secondary:</span>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {logoColors.map((c, i) => {
                const isPrimary = primaryColor === c;
                const isSecondary = secondaryColor === c;
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleLogoColorClick(c)}
                    className={`relative flex flex-col items-center gap-1 rounded-lg border-2 p-2 transition-all ${
                      isPrimary
                        ? 'border-accent bg-bg-elevated shadow-sm'
                        : isSecondary
                          ? 'border-blue-400 bg-bg-elevated shadow-sm'
                          : 'border-border hover:border-text-muted'
                    }`}
                  >
                    <div
                      className="h-8 w-8 rounded-md"
                      style={{ backgroundColor: c }}
                    />
                    <span className="text-[10px] text-text-muted">{c}</span>
                    {isPrimary && (
                      <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-accent text-[8px] font-bold text-white">
                        P
                      </span>
                    )}
                    {isSecondary && (
                      <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-blue-400 text-[8px] font-bold text-white">
                        S
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Color Palette Presets */}
        <div className="mb-3">
          <span className="text-xs text-text-muted">{logoColors.length > 0 ? 'Or choose a preset palette:' : 'Choose a palette:'}</span>
          <div className="mt-1.5 grid grid-cols-4 gap-2">
            {COLOR_PALETTES.map((palette) => (
              <button
                key={palette.name}
                type="button"
                onClick={() => handlePaletteSelect(palette)}
                className={`flex flex-col items-center gap-1 rounded-lg border p-2 transition-colors ${
                  selectedPalette === palette.name
                    ? 'border-accent bg-bg-elevated'
                    : 'border-border hover:border-text-muted'
                }`}
              >
                <div className="flex gap-0.5">
                  {palette.colors.map((c, i) => (
                    <div
                      key={i}
                      className="h-5 w-5 rounded-sm"
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
                <span className="text-[10px] text-text-muted">{palette.name}</span>
              </button>
            ))}
          </div>
        </div>

        <span className="text-xs text-text-muted">Or pick custom colors:</span>
        <div className="mt-1.5 flex gap-6">
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={primaryColor}
              onChange={(e) => handlePrimaryChange(e.target.value)}
              className="h-10 w-10 cursor-pointer rounded border border-border bg-bg-page"
            />
            <div>
              <div className="text-xs font-medium text-text-primary">Primary</div>
              <div className="text-xs text-text-muted">{primaryColor}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={secondaryColor}
              onChange={(e) => handleSecondaryChange(e.target.value)}
              className="h-10 w-10 cursor-pointer rounded border border-border bg-bg-page"
            />
            <div>
              <div className="text-xs font-medium text-text-primary">Secondary</div>
              <div className="text-xs text-text-muted">{secondaryColor}</div>
            </div>
          </div>
        </div>
        {colors.length > 2 && (
          <div className="mt-2">
            <span className="text-xs text-text-muted">Full palette:</span>
            <div className="mt-1 flex gap-2">
              {colors.map((c, i) => (
                <div key={i} className="flex items-center gap-1 rounded border border-border px-2 py-1">
                  <div className="h-4 w-4 rounded" style={{ backgroundColor: c }} />
                  <span className="text-xs text-text-muted">{c}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={!name.trim() || loading || uploading}
        className="w-full rounded-lg bg-accent py-3 font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
      >
        {loading ? 'Saving...' : initial ? 'Update Brand' : 'Create Brand'}
      </button>
    </form>
  );
}
