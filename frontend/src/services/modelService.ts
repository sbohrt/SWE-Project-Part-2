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

  // Enumerate with filters (placeholder - adjust based on your actual endpoint)
  enumerateModels: async (filters?: {
    regex?: string;
    version?: string;
    page?: number;
    limit?: number;
  }): Promise<{ models: ModelScore[]; total: number }> => {
    const response = await api.get('/enumerate', { params: filters });
    return response.data;
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