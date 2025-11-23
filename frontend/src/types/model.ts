export interface ModelScore {
  modelId: string;
  name: string;
  category: 'MODEL' | 'DATASET' | 'CODE';
  net_score: number;
  net_score_latency: number;
  ramp_up_time: number;
  ramp_up_time_latency: number;
  bus_factor: number;
  bus_factor_latency: number;
  performance_claims: number;
  performance_claims_latency: number;
  license: number;
  license_latency: number;
  size_score: {
    raspberry_pi: number;
    jetson_nano: number;
    desktop_pc: number;
    aws_server: number;
  };
  size_score_latency: number;
  dataset_and_code_score: number;
  dataset_and_code_score_latency: number;
  dataset_quality: number;
  dataset_quality_latency: number;
  code_quality: number;
  code_quality_latency: number;
}

export interface HealthStatus {
  status: string;
  timestamp?: string;
  metrics?: {
    uploads_last_hour?: number;
    downloads_last_hour?: number;
    errors_last_hour?: number;
  };
}

export interface LineageNode {
  modelId: string;
  name: string;
  children?: string[];
  parents?: string[];
}