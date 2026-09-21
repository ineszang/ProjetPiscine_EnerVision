export interface Recommendation {
  recommendation_id: number;
  alert_id: number;
  action: string;
  explanation: string;
  rule_reference: string;
  created_at: string;
}

export interface RecommendationGenerationReport {
  alerts_examined: number;
  recommendations_created: number;
  already_present: number;
}
