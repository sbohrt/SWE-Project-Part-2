import { api } from './api';
import { ModelScore, HealthStatus, LineageNode } from '../types/model';

export const modelService = {
  // CRUD Operations
  getAllModels: async (): Promise<ModelScore[]> => {
    const response = await api.get('/models');
    return response.data;
  },

  getModelById: async (id: string): Promise<ModelScore> => {
    const response = await api.get(`/models/${id}`);
    return response.data;
  },

  createModel: async (modelData: Partial<ModelScore>): Promise<ModelScore> => {
    const response = await api.post('/models', modelData);
    return response.data;
  },

  updateModel: async (id: string, modelData: Partial<ModelScore>): Promise<ModelScore> => {
    const response = await api.put(`/models/${id}`, modelData);
    return response.data;
  },

  deleteModel: async (id: string): Promise<void> => {
    await api.delete(`/models/${id}`);
  },

  // Rate Model
  rateModel: async (url: string): Promise<ModelScore> => {
    const response = await api.post('/rate', { url });
    return response.data;
  },

  // Health Check
  getHealth: async (): Promise<HealthStatus> => {
    const response = await api.get('/health');
    return response.data;
  },

  // Ingest Model (placeholder - adjust based on your actual endpoint)
  ingestModel: async (url: string): Promise<ModelScore> => {
    const response = await api.post('/ingest', { url });
    return response.data;
  },

  // Enumerate artifacts with filters
  enumerateModels: async (filters?: {
    name?: string;
    types?: string[];
    offset?: number;
  }): Promise<{ models: ModelScore[]; offset: string }> => {
    // Build artifact query according to OpenAPI spec
    const query = [{
      name: filters?.name || '*',  // Default to wildcard for all
      ...(filters?.types && { types: filters.types })  // Optional type filter
    }];

    const params = filters?.offset ? { offset: filters.offset.toString() } : {};

    const response = await api.post('/artifacts', query, { params });

    return {
      models: response.data,
      offset: response.headers['offset'] || '0'
    };
  },

  // Lineage Graph (placeholder - adjust based on your actual endpoint)
  getLineage: async (modelId: string): Promise<LineageNode> => {
    const response = await api.get(`/lineage/${modelId}`);
    return response.data;
  },

  // Reset Registry (admin only)
  resetRegistry: async (): Promise<void> => {
    await api.post('/reset');
  },
};