export interface BriefConstraints {
  min_fans_count?: number | null;
  min_female_ratio?: number | null;
  max_candidate_price?: number | null;
  required_creator_types: string[];
  notes: string[];
}

export interface CampaignBrief {
  campaign_id: string;
  campaign_name: string;
  platform: string;
  budget_total: number;
  creator_tier: string;
  creator_types: string[];
  city: string;
  event_date: string;
  post_dates: string[];
  content_tags: string[];
  style_tags: string[];
  constraints: BriefConstraints;
  keywords: string[];
}

export interface HardFilters {
  platform_match: boolean;
  min_fans_count?: number | null;
  min_female_ratio?: number | null;
  max_candidate_price?: number | null;
  max_price_share_of_budget?: number | null;
  require_creator_type_overlap: boolean;
}

export interface SoftPreferences {
  preferred_cities: string[];
  preferred_experience_tags: string[];
  preferred_content_tags: string[];
  preferred_style_tags: string[];
  growth_floor?: number | null;
}

export interface ScoreWeights {
  brief_match: number;
  content_fit: number;
  commercial_efficiency: number;
  audience_fit: number;
  growth_signal: number;
}

export interface StrategyTemplate {
  template_id: string;
  template_name: string;
  description: string;
  hard_filters: HardFilters;
  soft_preferences: SoftPreferences;
  score_weights: ScoreWeights;
  platform_mapping: Record<string, string[]>;
  manual_review_points: string[];
}

export interface ScoreBreakdown {
  brief_match: number;
  content_fit: number;
  audience_fit: number;
  commercial_efficiency: number;
  growth_signal: number;
  weighted_total: number;
  explanation: string[];
}

export interface CandidateCreator {
  creator_id: string;
  creator_name: string;
  platform: string;
  creator_types: string[];
  xingtu_link?: string | null;
  fans_count: number;
  female_ratio: number;
  core_female_ratio: number;
  price: number;
  rebate: number;
  settlement_price_est: number;
  median_commercial_play: number;
  natural_cpm: number;
  cpe: number;
  commercial_completion_rate: number;
  completion_cpm: number;
  monthly_growth_rate: number;
  broad_fan_ratio: number;
  deep_fan_ratio: number;
  recent_curve_summary: string;
  recent_content_summary: string;
  experience_tags: string[];
  content_tags: string[];
  style_tags: string[];
  city?: string | null;
  score_breakdown?: ScoreBreakdown | null;
  final_score: number;
  risk_notes: string[];
  recommendation_reason: string;
  recommendation_level: string;
}

export interface RetrievalPlan {
  selected_filters: Record<string, string | number | boolean | null>;
  generated_keywords: string[];
  hard_filter_summary: string[];
  ranking_priorities: string[];
}

export interface PipelineMetadata {
  template_id: string;
  total_candidates_loaded: number;
  candidates_after_filters: number;
  filtered_out: number;
  filter_reasons: Record<string, number>;
}

export interface BriefStructureResponse {
  structured_brief: CampaignBrief;
  parser_notes: string[];
}

export interface CandidatesRunResponse {
  brief: CampaignBrief;
  template: StrategyTemplate;
  retrieval_plan: RetrievalPlan;
  candidates: CandidateCreator[];
  metadata: PipelineMetadata;
}
