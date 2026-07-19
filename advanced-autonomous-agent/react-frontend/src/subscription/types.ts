

export interface UsageResponse {
    plan: string;
    status: string;
    used: number;
    daily_limit: number;
    remaining: number;
    autonomous_enabled: boolean;
    expires_at: string | null
}

export interface CurrentPlanResponse{
    plan: string;
    display_name: string;
    daily_frontend_runs: number;
    features: string[];
}

export interface PlanResponse {
    id: string;
    display_name: string;
    daily_frontend_runs: number;
    features: string[];
}

export interface FeatureAccessResponse {
    feature: string;
    has_access: boolean;
}

export interface FrontendAuthorizationResponse {
    authorized: boolean;
    plan: string;
    limit: number;
    used: number;
    remaining: number;
}

export interface AutonomousAuthorizationResponse {
    authorized: boolean;
    plan: string;
}
