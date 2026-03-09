import { useState, type FormEvent } from 'react';
import type { Brand, BrandCreate } from '../types';
import { uploadLogo, uploadProductImage } from '../api/brands';

interface Props {
  initial?: Brand;
  onSubmit: (data: BrandCreate) => void;
  loading: boolean;
}

const TONES = [
  'professional',
  'casual',
  'playful',
  'luxurious',
  'bold',
  'minimalist',
  'friendly',
  'authoritative',
];

export function BrandForm({ initial, onSubmit, loading }: Props) {
  const [name, setName] = useState(initial?.name ?? '');
  const [industry, setIndustry] = useState(initial?.industry ?? '');
  const [overview, setOverview] = useState(initial?.overview ?? '');
  const [tone, setTone] = useState(initial?.tone ?? 'professional');
  const [targetAudience, setTargetAudience] = useState(initial?.target_audience ?? '');
  const [productsServices, setProductsServices] = useState(initial?.products_services ?? '');
  const [logoPath, setLogoPath] = useState(initial?.logo_path ?? '');
  const [logoUrl, setLogoUrl] = useState(initial?.logo_path ? toDisplayUrl(initial.logo_path) : '');
  const [colors, setColors] = useState<string[]>(initial?.colors ?? []);
  const [productImages, setProductImages] = useState<string[]>(initial?.product_images ?? []);
  const [productUrls, setProductUrls] = useState<string[]>(() => {
    if (!initial?.product_images) return [];
    return initial.product_images.map((p) => toDisplayUrl(p));
  });
  const [uploading, setUploading] = useState(false);

  function toDisplayUrl(path: string): string {
    const genIdx = path.indexOf('/generated/');
    if (genIdx !== -1) return path.slice(genIdx);
    const uplIdx = path.indexOf('/uploads/');
    if (uplIdx !== -1) return path.slice(uplIdx);
    return path;
  }

  async function handleLogoUpload(file: File) {
    setUploading(true);
    try {
      const res = await uploadLogo(file);
      setLogoPath(res.logo_path);
      setLogoUrl(res.url);
      if (res.colors.length > 0) setColors(res.colors);
    } finally {
      setUploading(false);
    }
  }

  async function handleProductUpload(file: File) {
    setUploading(true);
    try {
      const res = await uploadProductImage(file);
      setProductImages((prev) => [...prev, res.image_path]);
      setProductUrls((prev) => [...prev, res.url]);
    } finally {
      setUploading(false);
    }
  }

  function removeProduct(index: number) {
    setProductImages((prev) => prev.filter((_, i) => i !== index));
    setProductUrls((prev) => prev.filter((_, i) => i !== index));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit({
      name,
      industry: industry || undefined,
      overview: overview || undefined,
      tone,
      target_audience: targetAudience || undefined,
      products_services: productsServices || undefined,
      logo_path: logoPath || undefined,
      colors,
      product_images: productImages,
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
        <input
          type="text"
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          maxLength={100}
          className="w-full rounded-lg border border-border bg-bg-page px-4 py-2.5 text-text-primary focus:border-accent focus:outline-none"
        />
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
        <input
          type="file"
          accept="image/*"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleLogoUpload(file);
          }}
          className="text-sm text-text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-accent file:px-4 file:py-2 file:text-sm file:text-white file:cursor-pointer"
        />
        {logoUrl && (
          <img
            src={logoUrl}
            alt="Logo preview"
            className="mt-2 h-16 rounded border border-border object-contain"
          />
        )}
      </div>

      {/* Colors */}
      {colors.length > 0 && (
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            Extracted Colors
          </label>
          <div className="flex gap-2">
            {colors.map((c, i) => (
              <div key={i} className="flex items-center gap-1 rounded border border-border px-2 py-1">
                <div className="h-5 w-5 rounded" style={{ backgroundColor: c }} />
                <span className="text-xs text-text-muted">{c}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Product Images */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">Product Images</label>
        <input
          type="file"
          accept="image/*"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleProductUpload(file);
          }}
          className="text-sm text-text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-bg-elevated file:px-4 file:py-2 file:text-sm file:text-text-primary file:cursor-pointer"
        />
        {productUrls.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {productUrls.map((url, i) => (
              <div key={i} className="group relative">
                <img
                  src={url}
                  alt={`Product ${i + 1}`}
                  className="h-20 w-20 rounded border border-border object-cover"
                />
                <button
                  type="button"
                  onClick={() => removeProduct(i)}
                  className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100"
                >
                  x
                </button>
              </div>
            ))}
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
