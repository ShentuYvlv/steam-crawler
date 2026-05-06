const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";
const authTokenKey = "steam_admin_access_token";

export function getAccessToken() {
  return window.localStorage.getItem(authTokenKey);
}

export function setAccessToken(token: string) {
  window.localStorage.setItem(authTokenKey, token);
}

export function clearAccessToken() {
  window.localStorage.removeItem(authTokenKey);
}

export type User = {
  id: number;
  username: string;
  display_name: string | null;
  role: "admin" | "operator" | "viewer";
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type ReviewListItem = {
  id: number;
  app_id: number;
  recommendation_id: string;
  steam_id: string | null;
  persona_name: string | null;
  language: string | null;
  review_text: string;
  voted_up: boolean | null;
  votes_up: number;
  votes_funny: number;
  comment_count: number;
  playtime_forever: number | null;
  playtime_at_review: number | null;
  timestamp_created: string | null;
  sync_type: string;
  processing_status: string;
  reply_status: string;
};

export type ReviewDetail = ReviewListItem & {
  profile_url: string | null;
  review_url: string | null;
  weighted_vote_score: number | null;
  steam_purchase: boolean | null;
  received_for_free: boolean | null;
  refunded: boolean | null;
  written_during_early_access: boolean | null;
  playtime_last_two_weeks: number | null;
  num_games_owned: number | null;
  num_reviews: number | null;
  timestamp_updated: string | null;
  last_played: string | null;
  source_type: string;
  developer_response: string | null;
  developer_response_created_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ReviewListResponse = {
  items: ReviewListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type ReviewQuery = {
  app_id?: string;
  voted_up?: string;
  min_votes_up?: string;
  max_votes_up?: string;
  min_playtime?: string;
  max_playtime?: string;
  processing_status?: string;
  reply_status?: string;
  keyword?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
};

export type ReplyExample = {
  title: string;
  review: string;
  reply: string;
};

export type ReplyStrategy = {
  id: number;
  name: string;
  description: string | null;
  prompt_template: string;
  reply_rules: string | null;
  forbidden_terms: string[];
  good_examples: ReplyExample[];
  brand_voice: string | null;
  classification_strategy: string | null;
  model_name: string;
  temperature: number | null;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ReplyStrategyPayload = {
  name: string;
  description?: string | null;
  prompt_template: string;
  reply_rules?: string | null;
  forbidden_terms?: string[];
  good_examples?: ReplyExample[];
  brand_voice?: string | null;
  classification_strategy?: string | null;
  model_name?: string;
  temperature?: number | null;
  is_active?: boolean;
};

export type ReplyDraft = {
  id: number;
  review_id: number;
  strategy_id: number | null;
  strategy_version: number | null;
  content: string;
  status: string;
  model_name: string | null;
  prompt_snapshot: string | null;
  error_message: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ReplyRecord = {
  id: number;
  review_id: number;
  draft_id: number | null;
  recommendation_id: string;
  content: string;
  status: string;
  steam_response: string | null;
  error_message: string | null;
  sent_at: string | null;
  delete_status: string;
  delete_request_reason: string | null;
  delete_requested_at: string | null;
  created_at: string;
  updated_at: string;
  app_id?: number;
  review_text?: string;
  persona_name?: string | null;
  voted_up?: boolean | null;
};

export type SyncJob = {
  id: number;
  app_id: number | null;
  job_type: string;
  source_type: string;
  status: string;
  requested_limit: number | null;
  inserted_count: number;
  updated_count: number;
  skipped_count: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type TaskSchedule = {
  id: number;
  task_type: string;
  is_enabled: boolean;
  app_id: number | null;
  interval: string;
  hour: number | null;
  minute: number | null;
  options: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type StatsOverview = {
  total_reviews: number;
  positive_reviews: number;
  negative_reviews: number;
  replied_reviews: number;
  pending_reviews: number;
  ignored_reviews: number;
  positive_rate: number;
  reply_success_rate: number;
};

export type StatsTimeseriesItem = {
  date: string;
  new_reviews: number;
  sent_replies: number;
};

export type StatsTimeseries = {
  items: StatsTimeseriesItem[];
};

export async function login(payload: { username: string; password: string }): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchMe(): Promise<User> {
  return apiGet<User>("/auth/me");
}

export async function fetchUsers(): Promise<User[]> {
  return apiGet<User[]>("/users");
}

export async function createUser(payload: {
  username: string;
  password: string;
  display_name?: string | null;
  role: string;
  is_active: boolean;
}): Promise<User> {
  return apiRequest<User>("/users", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateUser(
  userId: number,
  payload: {
    password?: string;
    display_name?: string | null;
    role?: string;
    is_active?: boolean;
  }
): Promise<User> {
  return apiRequest<User>(`/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function fetchStatsOverview(): Promise<StatsOverview> {
  return apiGet<StatsOverview>("/stats/overview");
}

export async function fetchStatsTimeseries(days = 14): Promise<StatsTimeseries> {
  return apiGet<StatsTimeseries>(`/stats/timeseries?days=${days}`);
}

export async function fetchReviews(query: ReviewQuery): Promise<ReviewListResponse> {
  return apiGet<ReviewListResponse>(`/reviews${toQueryString(query)}`);
}

export async function fetchReviewDetail(reviewId: number): Promise<ReviewDetail> {
  return apiGet<ReviewDetail>(`/reviews/${reviewId}`);
}

export async function updateReviewStatus(
  reviewId: number,
  body: { processing_status?: string; reply_status?: string }
): Promise<{ updated_count: number }> {
  return apiRequest(`/reviews/${reviewId}/status`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
}

export async function bulkUpdateReviewStatus(
  reviewIds: number[],
  body: { processing_status?: string; reply_status?: string }
): Promise<{ updated_count: number }> {
  return apiRequest("/reviews/bulk-status", {
    method: "POST",
    body: JSON.stringify({ review_ids: reviewIds, ...body })
  });
}

export async function generateReplyDraft(reviewId: number): Promise<{ draft: ReplyDraft }> {
  return apiRequest<{ draft: ReplyDraft }>(`/reviews/${reviewId}/generate-reply`, {
    method: "POST"
  });
}

export async function bulkGenerateReplyDrafts(
  reviewIds: number[]
): Promise<{ accepted_count: number; review_ids: number[] }> {
  return apiRequest<{ accepted_count: number; review_ids: number[] }>("/reviews/bulk-generate-reply", {
    method: "POST",
    body: JSON.stringify({ review_ids: reviewIds })
  });
}

export async function fetchReplyDraft(draftId: number): Promise<ReplyDraft> {
  return apiGet<ReplyDraft>(`/reply-drafts/${draftId}`);
}

export async function fetchReviewReplyDrafts(reviewId: number): Promise<ReplyDraft[]> {
  return apiGet<ReplyDraft[]>(`/reviews/${reviewId}/reply-drafts`);
}

export async function updateReplyDraft(
  draftId: number,
  payload: { content?: string; status?: string }
): Promise<ReplyDraft> {
  return apiRequest<ReplyDraft>(`/reply-drafts/${draftId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function sendReviewReply(
  reviewId: number,
  payload: { draft_id?: number; content?: string; confirmed: boolean }
): Promise<{ record: ReplyRecord }> {
  return apiRequest<{ record: ReplyRecord }>(`/reviews/${reviewId}/send-reply`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function regenerateReplyDraft(reviewId: number): Promise<{ draft: ReplyDraft }> {
  return apiRequest<{ draft: ReplyDraft }>(`/reviews/${reviewId}/regenerate-reply`, {
    method: "POST"
  });
}

export async function fetchReplyRecords(): Promise<ReplyRecord[]> {
  return apiGet<ReplyRecord[]>("/reply-records");
}

export async function createReplyDeleteRequest(
  recordId: number,
  payload: { confirmed: boolean; reason?: string | null }
): Promise<ReplyRecord> {
  return apiRequest<ReplyRecord>(`/reply-records/${recordId}/delete-request`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchTasks(): Promise<SyncJob[]> {
  return apiGet<SyncJob[]>("/tasks");
}

export async function enqueueReviewSync(payload: {
  app_id: number;
  language?: string;
  filter?: string;
  review_type?: string;
  purchase_type?: string;
  use_review_quality?: boolean;
  per_page?: number;
}): Promise<SyncJob> {
  return apiRequest<SyncJob>("/tasks/reviews-sync", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchTaskSchedule(): Promise<TaskSchedule | null> {
  return apiGet<TaskSchedule | null>("/tasks/schedule");
}

export async function updateTaskSchedule(payload: {
  is_enabled: boolean;
  app_id?: number | null;
  interval: string;
  hour?: number | null;
  minute?: number | null;
  options?: Record<string, unknown>;
}): Promise<TaskSchedule> {
  return apiRequest<TaskSchedule>("/tasks/schedule", {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function fetchReplyStrategies(): Promise<ReplyStrategy[]> {
  return apiGet<ReplyStrategy[]>("/reply-strategies");
}

export async function fetchActiveReplyStrategy(): Promise<ReplyStrategy> {
  return apiGet<ReplyStrategy>("/reply-strategies/active");
}

export async function createReplyStrategy(payload: ReplyStrategyPayload): Promise<ReplyStrategy> {
  return apiRequest<ReplyStrategy>("/reply-strategies", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateReplyStrategy(
  strategyId: number,
  payload: Partial<ReplyStrategyPayload>
): Promise<ReplyStrategy> {
  return apiRequest<ReplyStrategy>(`/reply-strategies/${strategyId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function activateReplyStrategy(strategyId: number): Promise<ReplyStrategy> {
  return apiRequest<ReplyStrategy>(`/reply-strategies/${strategyId}/activate`, {
    method: "POST"
  });
}

async function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "GET" });
}

async function apiRequest<T>(path: string, init: RequestInit): Promise<T> {
  const token = getAccessToken();
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers
    }
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearAccessToken();
    }
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function toQueryString(query: ReviewQuery): string {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  const queryString = params.toString();
  return queryString ? `?${queryString}` : "";
}
