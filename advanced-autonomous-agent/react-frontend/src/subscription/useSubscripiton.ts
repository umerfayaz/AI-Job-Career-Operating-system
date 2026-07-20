
import { useState, useEffect} from "react";
import {
    getUsage,
    getCurrentPlan,
    getPlans,
    hasFeature,
} from "./api"
import { CurrentPlanResponse, FeatureAccessResponse, PlanResponse, UsageResponse } from "./types";

export function useSubscription () {

const [usage, setUsage] = useState<UsageResponse | null>(null);
const [currentPlan, setCurrentPlan] = useState<CurrentPlanResponse | null>(null);
const [plans, setPlans] = useState<PlanResponse[]>([]);
const [featureResponse, setFeatureResponse] = useState<FeatureAccessResponse | null>(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);

async function loadUsage() {
    try {

        const data = await getUsage();
        setUsage(data);
    }catch (err: any) {

        setError(err?. detail ?? "Failed to load usage")
    }
}

async function loadCurrentPlan() {
    try {
        const data = await getCurrentPlan();
        setCurrentPlan(data);
    } catch (err: any) {
        setError(err?. detail ?? "Failed to load Current Plan")
    }
}

async function loadPlans() {
    try {
        const data = await getPlans();
        setPlans(data);
    }catch (err: any) {
        setError(err?. detail ?? "Failed to load Plan")
    }

}

async function loadFeature(feature: string) {
    try {
        const data = await hasFeature(feature);
        setFeatureResponse(data);
    }catch (err: any) {
        setError(err?. detail ?? "Failed to load Feature")
    }
}


async function refresh() {
    setError(null);
    setLoading(true);

    try {
        await Promise.all ([
            loadUsage(),
            loadCurrentPlan(),
            loadPlans()
        ]);
    } finally {
        setLoading(false);
    }
}

useEffect(() => {
    refresh();
}, [])

return {
    usage, 
    currentPlan, 
    plans, 
    featureResponse, 
    loading, 
    error, 
    refresh, 
    loadUsage, 
    loadCurrentPlan, 
    loadPlans, 
    loadFeature
};

}
