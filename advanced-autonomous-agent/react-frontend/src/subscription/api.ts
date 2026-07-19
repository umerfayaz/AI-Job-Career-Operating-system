
import {
    UsageResponse,
    CurrentPlanResponse,
    PlanResponse,
    FeatureAccessResponse,
    FrontendAuthorizationResponse,
    AutonomousAuthorizationResponse,
} from "./types";

const BASE = import.meta.env.VITE_BACKEND_URL || "/api";

function getHeaders() {
    const token = localStorage.getItem("auth_token");

    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,

    };
}

// Helper function for all responses
async function parseResponse<T>(res: Response): Promise<T> {
    const data = await res.json();

    if(!res.ok){
        throw data;
    }
     return data;
} 

export async function getUsage(): Promise<UsageResponse> {
    const res = await fetch(`${BASE}/subscription/usage`, {
        headers: getHeaders(),
    });

    return parseResponse<UsageResponse>(res);
}

export async function getCurrentPlan(): Promise<CurrentPlanResponse> {
    const res = await fetch(`${BASE}/subscription/plan`, {
        headers: getHeaders(),
    });

    return parseResponse<CurrentPlanResponse>(res);
}

export async function getPlans(): Promise<PlanResponse[]> {
    const res = await fetch(`${BASE}/subscription/plans`, {
        headers: getHeaders(),
    });
    
    return parseResponse<PlanResponse[]>(res);
}

export async function hasFeature(feature: string): Promise<FeatureAccessResponse> {
    const res = await fetch(`${BASE}/subscription/feature/${feature}`, {
        headers: getHeaders(),
    })

    return parseResponse<FeatureAccessResponse>(res);
}

export async function authorizeFrontend(): Promise<FrontendAuthorizationResponse> {
    const res = await fetch(`${BASE}/subscription/authorize/frontend`, {
        method: "POST",
        headers: getHeaders(),
    })

    return parseResponse<FrontendAuthorizationResponse>(res);
}

export async function authorizeAutonomous(): Promise<AutonomousAuthorizationResponse> {
    const res = await fetch(`${BASE}/subscription/authorize/autonomous`, {
        method: "POST",
        headers: getHeaders(),
    })

    return parseResponse<AutonomousAuthorizationResponse>(res);
}





