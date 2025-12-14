import { api, rootApi } from './api';
import { ModelScore, HealthStatus, LineageNode } from '../types/model';

export const modelService = {
  // Get all models - uses POST /artifacts at ROOT (not /api/v1)
  getAllModels: async (): Promise<ModelScore[]> => {
    // First get list of model artifacts (artifacts_bp is at root)
    const listResponse = await rootApi.post('/artifacts', [{ name: '*', types: ['model'] }]);
    const artifacts = listResponse.data; // Array of {name, id, type}
    
    // Then fetch ratings for each model (also at root)
    const modelsWithRatings = await Promise.all(
      artifacts.map(async (artifact: { name: string; id: string; type: string }) => {
        try {
          const ratingResponse = await rootApi.get(`/artifact/model/${artifact.id}/rate`);
          return {
            modelId: artifact.id,
            name: artifact.name || ratingResponse.data.name,
            ...ratingResponse.data,
          };
        } catch {
          // If rating fails, return basic info
          return {
            modelId: artifact.id,
            name: artifact.name,
            category: 'MODEL',
            net_score: null,
            license: null,
            bus_factor: null,
            code_quality: null,
            ramp_up_time: null,
          };
        }
      })
    );
    
    return modelsWithRatings;
  },

  getModelById: async (id: string): Promise<ModelScore> => {
    const response = await rootApi.get(`/artifact/model/${id}`);
    return response.data;
  },

  createModel: async (modelData: Partial<ModelScore>): Promise<ModelScore> => {
    const response = await rootApi.post('/artifact/model', modelData);
    return response.data;
  },

  updateModel: async (id: string, modelData: Partial<ModelScore>): Promise<ModelScore> => {
    const response = await rootApi.put(`/artifact/model/${id}`, modelData);
    return response.data;
  },

  deleteModel: async (id: string): Promise<void> => {
    // Backend expects DELETE /artifact/model/{id} at root
    await rootApi.delete(`/artifact/model/${id}`);
  },

  // Rate Model - get rating for a model
  rateModel: async (url: string): Promise<ModelScore> => {
    // First ingest (at root), then get rating
    const ingestResponse = await rootApi.post('/ingest', { url });
    const modelId = ingestResponse.data.id;
    const ratingResponse = await rootApi.get(`/artifact/model/${modelId}/rate`);
    return ratingResponse.data;
  },

  // Health Check (at root)
  getHealth: async (): Promise<HealthStatus> => {
    const response = await rootApi.get('/health');
    return response.data;
  },

  // Ingest Model (at root)
  ingestModel: async (url: string): Promise<any> => {
    const response = await rootApi.post('/ingest', { url });
    return response.data;
  },

  // Enumerate with filters
  enumerateModels: async (filters?: {
    regex?: string;
    version?: string;
    page?: number;
    limit?: number;
  }): Promise<{ models: ModelScore[]; total: number }> => {
    const response = await api.get('/enumerate', { params: filters });
    return response.data;
  },

  // Lineage Graph (at root)
  getLineage: async (modelId: string): Promise<LineageNode> => {
    const response = await rootApi.get(`/artifact/model/${modelId}/lineage`);
    return response.data;
  },

  // Reset Registry (at root)
  resetRegistry: async (): Promise<void> => {
    await rootApi.delete('/reset');
  },
};