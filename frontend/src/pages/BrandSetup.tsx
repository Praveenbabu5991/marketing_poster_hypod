import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { BrandForm } from '../components/BrandForm';
import { createBrand, getBrand, updateBrand } from '../api/brands';
import { useStore } from '../store/useStore';
import type { Brand, BrandCreate } from '../types';

export function BrandSetup() {
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);
  const [brand, setBrand] = useState<Brand | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(isEdit);
  const navigate = useNavigate();
  const setSelectedBrandId = useStore((s) => s.setSelectedBrandId);

  useEffect(() => {
    if (id) {
      setFetching(true);
      getBrand(id)
        .then(setBrand)
        .catch(console.error)
        .finally(() => setFetching(false));
    }
  }, [id]);

  async function handleSubmit(data: BrandCreate) {
    setLoading(true);
    try {
      if (isEdit && id) {
        await updateBrand(id, data);
        navigate('/');
      } else {
        const created = await createBrand(data);
        setSelectedBrandId(created.id);
        navigate('/');
      }
    } catch (err) {
      console.error('Failed to save brand:', err);
    } finally {
      setLoading(false);
    }
  }

  if (fetching) {
    return (
      <div className="flex flex-1 items-center justify-center text-text-muted">Loading brand...</div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <h1 className="mb-6 text-2xl font-bold text-text-primary">
        {isEdit ? 'Edit Brand' : 'Create Brand'}
      </h1>
      <div className="mx-auto max-w-2xl">
        <BrandForm initial={brand ?? undefined} onSubmit={handleSubmit} loading={loading} />
      </div>
    </div>
  );
}
