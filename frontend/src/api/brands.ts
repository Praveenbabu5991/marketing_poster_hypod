import { fetchApi, uploadFile } from './client';
import type {
  Brand,
  BrandCreate,
  BrandUpdate,
  LogoUploadResponse,
  ProductImageUploadResponse,
} from '../types';

export function listBrands(): Promise<Brand[]> {
  return fetchApi<Brand[]>('/api/v1/brands');
}

export function getBrand(id: string): Promise<Brand> {
  return fetchApi<Brand>(`/api/v1/brands/${id}`);
}

export function createBrand(data: BrandCreate): Promise<Brand> {
  return fetchApi<Brand>('/api/v1/brands', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateBrand(id: string, data: BrandUpdate): Promise<Brand> {
  return fetchApi<Brand>(`/api/v1/brands/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteBrand(id: string): Promise<void> {
  return fetchApi<void>(`/api/v1/brands/${id}`, { method: 'DELETE' });
}

export async function uploadLogo(file: File): Promise<LogoUploadResponse> {
  const res = await uploadFile('/api/v1/upload/logo', file);
  return res.json();
}

export async function uploadProductImage(
  file: File,
): Promise<ProductImageUploadResponse> {
  const res = await uploadFile('/api/v1/upload/product-image', file);
  return res.json();
}
