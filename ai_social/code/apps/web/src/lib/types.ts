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

export interface RequirementConstraintBucket {
  creator_categories: string[];
  cities: string[];
  content_themes: string[];
  audience_traits: string[];
  exclusions: string[];
  min_fans_count?: number | null;
  budget_cap_per_creator?: number | null;
  notes: string[];
}

export interface ShortlistRequirement {
  brand?: string | null;
  product_name?: string | null;
  product_sku?: string | null;
  product_category?: string | null;
  platform: string;
  city?: string | null;
  target_audience: string[];
  kpi_goals: string[];
  budget_total?: number | null;
  content_style_tags: string[];
  tone_tags: string[];
  compliance_notes: string[];
  exclusions: string[];
  optional_notes: string[];
  keywords: string[];
  hard_constraints: RequirementConstraintBucket;
  preferred_constraints: RequirementConstraintBucket;
  negotiable_constraints: RequirementConstraintBucket;
}

export interface XingtuFilterConfig {
  keyword?: string | null;
  named_filters: Record<string, string[]>;
  creator_types: string[];
  content_categories: string[];
  cities: string[];
  price_min?: number | null;
  price_max?: number | null;
  fans_min?: number | null;
  fans_max?: number | null;
  female_ratio_min?: number | null;
  female_ratio_max?: number | null;
  sort_by?: string | null;
  extra_tags: string[];
}

export interface ShortlistSearchPlan {
  platform: string;
  filter_config: XingtuFilterConfig;
  generated_keywords: string[];
  hard_filter_summary: string[];
  ranking_priorities: string[];
  search_notes: string[];
  unapplied_constraints: string[];
  collection_limit: number;
  shortlist_limit: number;
}

export interface ExternalDocReference {
  doc_id: string;
  title: string;
  category: "operational" | "strategy" | "archive";
  relative_path: string;
  absolute_path: string;
  source_type: string;
  used_in_v1: boolean;
  usage_notes: string[];
}

export interface ExternalDocReferenceResponse {
  references: ExternalDocReference[];
}

export interface XingtuCreatorDetail {
  creator_name?: string | null;
  creator_id?: string | null;
  xingtu_link?: string | null;
  platform: string;
  creator_types: string[];
  city?: string | null;
  fans_count?: number | null;
  female_ratio?: number | null;
  core_female_ratio?: number | null;
  price?: number | null;
  rebate?: number | null;
  settlement_price_est?: number | null;
  avg_video_play_median?: number | null;
  avg_video_play_median_percentile?: number | null;
  expected_cpm?: number | null;
  average_completion_rate?: number | null;
  average_completion_rate_percentile?: number | null;
  average_interaction_rate?: number | null;
  average_interaction_rate_percentile?: number | null;
  monthly_connected_users?: number | null;
  monthly_deep_users?: number | null;
  median_commercial_play?: number | null;
  natural_cpm?: number | null;
  cpe?: number | null;
  commercial_completion_rate?: number | null;
  completion_cpm?: number | null;
  monthly_growth_rate?: number | null;
  broad_fan_ratio?: number | null;
  deep_fan_ratio?: number | null;
  recent_curve_summary?: string | null;
  recent_content_summary?: string | null;
  experience_tags: string[];
  raw_metrics: Record<string, string>;
  raw_sections: Record<string, string>;
}

export interface ShortlistScoreBreakdown {
  brief_match: number;
  audience_match: number;
  content_fit: number;
  quality_activity: number;
  commercial_signal: number;
  risk_penalty: number;
  total_score: number;
  explanation: string[];
}

export interface ShortlistCandidate {
  creator: XingtuCreatorDetail;
  score_breakdown: ShortlistScoreBreakdown;
  recommendation_reason: string;
  recommendation_level: string;
  risk_flags: string[];
}

export interface ShortlistRunMetadata {
  storage_state_path: string;
  account_name?: string | null;
  homepage_url?: string | null;
  creator_search_url?: string | null;
  rows_seen: number;
  creators_collected: number;
  creators_ranked: number;
  creators_filtered_out: number;
  filtered_out_reasons: Record<string, number>;
  collection_errors: string[];
}

export interface ShortlistParseResponse {
  structured_requirement: ShortlistRequirement;
  parser_notes: string[];
}

export interface ShortlistPlanResponse {
  structured_requirement: ShortlistRequirement;
  parser_notes: string[];
  search_plan: ShortlistSearchPlan;
  reference_docs: ExternalDocReference[];
}

export interface ShortlistRunResponse {
  raw_brief?: string | null;
  structured_requirement: ShortlistRequirement;
  parser_notes: string[];
  search_plan: ShortlistSearchPlan;
  collected_creators: XingtuCreatorDetail[];
  shortlist: ShortlistCandidate[];
  reference_docs: ExternalDocReference[];
  metadata: ShortlistRunMetadata;
  debug: Record<string, unknown>;
}

export type ScreenshotType =
  | "overview_pricing"
  | "value_personal_video"
  | "latest15_personal_chart"
  | "latest15_star_chart"
  | "unknown";

export interface ExtractedField {
  field_name: string;
  raw_value?: string | null;
  normalized_value?: unknown;
  confidence: number;
  source: "vlm" | "manual" | "fallback" | "derived" | "fixture";
  screenshot_type: ScreenshotType;
  evidence_text?: string | null;
}

export interface ChartPoint {
  date?: string | null;
  play?: number | null;
  image_name?: string | null;
}

export interface XingtuCpmInput {
  creator_name?: string | null;
  natural_plays: number[];
  sponsored_plays: number[];
  personal_chart_points: ChartPoint[];
  star_chart_points: ChartPoint[];
  post_count_30d?: number | null;
  post_count_30d_source?: "value_page" | "chart_dates" | "manual" | null;
  chart_date_count_30d_personal?: number | null;
  chart_date_count_30d_star?: number | null;
  chart_date_count_30d_total?: number | null;
  ad_mode_play?: number | null;
  ad_median_play?: number | null;
  ad_bucketed_mode_play?: number | null;
  price_20s?: number | null;
  price_20_60s?: number | null;
  price_60s_plus?: number | null;
  platform_expected_cpm?: number | null;
  platform_expected_play?: number | null;
  personal_chart_min_play?: number | null;
  personal_chart_max_play?: number | null;
  personal_chart_avg_play?: number | null;
  star_chart_min_play?: number | null;
  star_chart_max_play?: number | null;
  star_chart_avg_play?: number | null;
  sponsored_completion_rate?: number | null;
  monthly_fan_growth_rate?: number | null;
  monthly_connected_user_fan_ratio?: number | null;
  monthly_deep_user_fan_ratio?: number | null;
  creator_type?: string | null;
  cooperate_brands: string[];
}

export interface XingtuCpmParseResult {
  extraction_engine_used?: string | null;
  vlm_model_used?: string | null;
  vlm_raw_response_preview?: string | null;
  field_sources: Record<string, string>;
  conflicts: ExtractionConflict[];
  warnings: string[];
  detected_screenshot_types: ScreenshotType[];
  missing_required_screenshot_types: ScreenshotType[];
  extracted_fields_by_screenshot_type: Record<ScreenshotType, ExtractedField[]>;
  parsed_input: XingtuCpmInput;
  parser_notes: string[];
}

export interface ExtractionConflict {
  field_name: string;
  left_value?: unknown;
  right_value?: unknown;
  chosen_source: string;
  reason: string;
}

export interface PoolEstimate {
  center?: number | null;
  low?: number | null;
  high?: number | null;
  raw_center?: number | null;
  adjustment_factor: number;
  cluster_values: number[];
  explanation: string;
  source: string;
  confidence: number;
  sample_count: number;
  weighted_sample_count: number;
  is_estimated: boolean;
  outlier_count: number;
  age_weighted: boolean;
}

export interface CpmTierResult {
  price?: number | null;
  predicted_cpm?: number | null;
  natural_cpm?: number | null;
  reason?: string | null;
  commercial_cpm_play_basis_source?: string | null;
  natural_cpm_play_basis_source?: string | null;
}

export interface XingtuCpmAssessment {
  primary_pool: PoolEstimate;
  secondary_pool?: PoolEstimate | null;
  commercial_primary_pool?: PoolEstimate | null;
  commercial_secondary_pool?: PoolEstimate | null;
  commercial_cpm_play_basis?: number | null;
  natural_cpm_play_basis?: number | null;
  commercial_pool_center_for_cpm?: number | null;
  natural_pool_center_for_cpm?: number | null;
  commercial_level: string;
  ad_repr_play?: number | null;
  predicted_ad_play?: number | null;
  weighted_predicted_ad_play?: number | null;
  cpm_by_tier: Record<string, CpmTierResult>;
  confidence_score: number;
  review_flag: boolean;
  review_reasons: string[];
  explanations: string[];
  reference: Record<string, number | null>;
  debug: Record<string, unknown>;
  natural_trend_metrics?: TrendMetrics | null;
  commercial_trend_metrics?: TrendMetrics | null;
  overall_trend_metrics?: TrendMetrics | null;
  trend_metrics?: TrendMetrics | null;
  commercial_ability?: CommercialAbilityMetrics | null;
  base_predicted_play?: number | null;
  final_prediction_factors: Record<string, number>;
}

export interface TrendMetrics {
  trend_coefficient: number;
  trend_direction: string;
  first_half_median?: number | null;
  second_half_median?: number | null;
}

export interface CommercialAbilityMetrics {
  ability_score: number;
  ability_level: string;
  coefficient: number;
  explanation: string;
  historical_commercial_position?: string | null;
}

export interface XingtuCpmAnalyzeResponse {
  parse_result: XingtuCpmParseResult;
  assessment: XingtuCpmAssessment;
}
