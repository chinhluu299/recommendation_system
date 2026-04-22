import { clearStoredAuthUser, getAuthToken } from "./auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiResponse<T> = {
  data: T | null;
  message: string;
  code: number;
};

export type UserSummary = {
  id: number;
  external_user_id: string | null;
  full_name: string | null;
  interaction_count: number;
};

export type UserListResponse = {
  items: UserSummary[];
  total: number;
};

export type UserInteractedProduct = {
  product_id: number;
  title: string;
  brand: string | null;
  price: number | null;
  image_url: string | null;
  last_action_type: "view" | "purchase" | string;
  last_interacted_at: string;
  interaction_count: number;
  purchase_count: number;
};

export type UserInteractionsResponse = {
  items: UserInteractedProduct[];
  total: number;
};

export type UserTrendInsightResponse = {
  query: string;
  insight: string;
  interaction_count: number;
  purchase_count: number;
  top_brands: string[];
  top_categories: string[];
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  user_id: number;
  email: string | null;
  external_user_id: string | null;
};

export type ProductItem = {
  id: number;
  external_id: string | null;
  title: string;
  brand: string | null;
  description: string | null;
  category: string | null;
  price: number | null;
  image_url: string | null;
};

export type ProductSearchResponse = {
  items: ProductItem[];
  total: number;
  query: string;
  search_mode: "pipeline" | "ilike";
  pipeline_error: string | null;
  trace: ProductSearchTrace | null;
};

export type ProductDetailResponse = ProductItem & {
  created_at: string;
};

export type ProductSearchTraceStep = {
  id: string;
  title: string;
  payload: Record<string, unknown>;
};

export type ProductSearchTrace = {
  query: string;
  pipeline_mode: string;
  error: string | null;
  steps: ProductSearchTraceStep[];
};

export type RankingEvaluationResponse = {
  query: string;
  evaluated_count: number;
  query_fit_score: number;
  user_fit_score: number;
  score: number;
  verdict: string;
  summary: string;
  strengths: string[];
  risks: string[];
  used_llm: boolean;
};

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<ApiResponse<T>> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearStoredAuthUser();
    if (typeof window !== "undefined") {
      window.location.href = "/auth/signin";
    }
    throw new Error("Unauthorized");
  }

  return res.json() as Promise<ApiResponse<T>>;
}

export const api = {
  /** Danh sách users có ≥5 interactions (public) */
  getUsers: (limit = 50) =>
    apiFetch<UserListResponse>(`/api/v1/users?limit=${limit}`, {
      method: "GET",
    }),

  /** Danh sách sản phẩm user hiện tại đã từng tương tác */
  getMyInteractions: (limit = 20, actionType?: "view" | "purchase") => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (actionType) {
      query.set("action_type", actionType);
    }
    return apiFetch<UserInteractionsResponse>(
      `/api/v1/users/me/interactions?${query.toString()}`,
      { method: "GET" },
    );
  },

  /** Phân tích xu hướng user theo query bằng LLM */
  getMyInteractionTrendInsight: (query: string, lookbackLimit = 120) =>
    apiFetch<UserTrendInsightResponse>("/api/v1/users/me/interaction-trend-insight", {
      method: "POST",
      body: JSON.stringify({
        query,
        lookback_limit: lookbackLimit,
      }),
    }),

  /** Demo login — không cần password */
  loginAs: (external_user_id: string) =>
    apiFetch<AuthTokenResponse>("/api/v1/auth/login-as", {
      method: "POST",
      body: JSON.stringify({ external_user_id }),
    }),

  /** Tìm kiếm sản phẩm (cần auth) */
  searchProducts: (
    query: string,
    limit = 100,
    offset = 0,
    includeTrace = false,
  ) =>
    apiFetch<ProductSearchResponse>(
      `/api/v1/products/search?query=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}&include_trace=${includeTrace}`,
    ),

  /** Chi tiết sản phẩm theo product id (cần auth) */
  getProductDetail: (productId: number) =>
    apiFetch<ProductDetailResponse>(`/api/v1/products/${productId}`, {
      method: "GET",
    }),

  /** Đánh giá mức hợp lý của top ranking theo xu hướng user */
  evaluateRanking: (query: string, productIds: number[], topK = 40) =>
    apiFetch<RankingEvaluationResponse>("/api/v1/products/evaluate-ranking", {
      method: "POST",
      body: JSON.stringify({
        query,
        product_ids: productIds,
        top_k: topK,
      }),
    }),
};
