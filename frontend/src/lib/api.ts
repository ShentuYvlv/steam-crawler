const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";

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

async function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "GET" });
}

async function apiRequest<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers
    }
  });

  if (!response.ok) {
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
