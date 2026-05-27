export type PersonalityStyle = {
  voice?: string;
  writing_style?: string;
  preferred_structure?: string[];
  vocabulary_preferences?: string[];
  avoid_phrases?: string[];
  example_post_ids?: string[];
};

export type Profile = {
  id: string;
  user_id: string;
  name?: string;
  niche?: string;
  profession?: string;
  goal?: string;
  tone?: string;
  audience?: string;
  avoid?: string;
  user_values?: string[];
  platforms?: string[];
  raw_answers?: Record<string, unknown> & { personality?: PersonalityStyle };
  style_examples_count?: number;
  profile_confirmation_status?: 'draft' | 'needs_confirmation' | 'confirmed';
  audience_confirmation_status?: 'draft' | 'needs_confirmation' | 'confirmed';
  profile_confirmed_at?: string | null;
  audience_confirmed_at?: string | null;
  lifecycle_notes?: Record<string, unknown>;
};

export type LifecycleStep = {
  key: string;
  status: 'completed' | 'current' | 'upcoming';
  route?: string;
  action?: string;
};

export type LifecycleResponse = {
  current_state: string;
  completed_states: string[];
  steps: LifecycleStep[];
  next_action?: {
    type?: string;
    route?: string;
    message_key?: string;
  };
  confirmations: {
    profile: { status: 'draft' | 'needs_confirmation' | 'confirmed'; confirmed_at?: string | null };
    audience: { status: 'draft' | 'needs_confirmation' | 'confirmed'; confirmed_at?: string | null };
  };
  counts: Record<string, number | string | null>;
};

export type ContentPlanItem = {
  id: string;
  plan_id: string;
  trend_id?: number;
  platform: string;
  format: string;
  post_idea?: string;
  scheduled_date: string;
  scheduled_time: string;
  status: string;
  trend_topic?: string;
  trend_summary?: string;
  trend_keywords?: string[];
  generated_post_id?: string | null;
  generated_post_status?: string | null;
  generated_post_at?: string | null;
};

export type GeneratedPost = {
  id: string;
  plan_item_id?: string | null;
  trend_id?: number | null;
  platform: string;
  format: string;
  draft_text: string;
  final_text: string;
  status: string;
  llm_provider?: string | null;
  stats: Record<string, unknown>;
  generated_at: string;
  selected_asset?: PostAsset | null;
  assets_count?: number;
  active_schedule?: ScheduledPost | null;
};

export type PostMetrics = {
  id: string;
  generated_post_id: string;
  scheduled_post_id?: string | null;
  platform: string;
  metric_date: string;
  source: 'manual';
  impressions: number;
  reach: number;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number;
  clicks: number;
  reactions: number;
  engagement_rate: number;
  raw_metrics?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
};

export type PostMetricsInput = {
  scheduled_post_id?: string | null;
  platform?: string;
  metric_date: string;
  source?: 'manual';
  impressions: number;
  reach: number;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number;
  clicks: number;
  reactions: number;
  raw_metrics?: Record<string, unknown>;
};

export type PostAsset = {
  id: string;
  post_id: string;
  asset_type: string;
  provider?: string | null;
  status: string;
  image_prompt?: string | null;
  search_query?: string | null;
  preview_url?: string | null;
  source_url?: string | null;
  author?: string | null;
  alt_text?: string | null;
  local_path?: string | null;
  metadata?: Record<string, unknown>;
  is_selected: boolean;
  created_at: string;
};

export type SocialAccount = {
  id: string;
  platform: string;
  display_name: string;
  external_account_id?: string | null;
  account_url?: string | null;
  connection_status: string;
  scopes?: string[];
  created_at: string;
  updated_at?: string;
};

export type ScheduledPost = {
  id: string;
  generated_post_id: string;
  social_account_id?: string | null;
  selected_asset_id?: string | null;
  platform: string;
  scheduled_for: string;
  status: string;
  payload?: Record<string, unknown>;
  attempt_count?: number;
  last_attempt_at?: string | null;
  published_at?: string | null;
  external_post_id?: string | null;
  external_post_url?: string | null;
  error_message?: string | null;
  social_account?: SocialAccount | null;
  post_text?: string;
  post_status?: string;
  created_at: string;
  updated_at?: string;
};

export type PublisherRunResult = {
  processed: number;
  published: number;
  failed: number;
  skipped: number;
  dry_run: boolean;
};

export type AnalyticsPattern = {
  id?: number | string;
  topic?: string;
  platform?: string;
  format?: string;
  avg_engagement_rate?: number;
  metrics_rows?: number;
};

export type LowEngagementPost = {
  id: string;
  platform?: string;
  format?: string;
  trend_topic?: string;
  avg_engagement_rate?: number;
  latest_metric_date?: string;
};

export type RecommendationsResponse = {
  data_quality: 'none' | 'limited' | 'usable';
  metrics_source: 'manual';
  recommendations: string[];
  top_patterns: AnalyticsPattern[];
  weak_patterns: AnalyticsPattern[];
  best_platforms?: AnalyticsPattern[];
  best_formats?: AnalyticsPattern[];
  low_engagement_posts?: LowEngagementPost[];
  next_actions: string[];
};
