import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import {
  useSubscription 
} from "@/subscription/useSubscripiton"

import {  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface Plan {
  id: string;
  name: string;
  price: string;
  priceDetail: string;
  badge?: string;
  features: string[];
  cta: string;
  ctaVariant: "default" | "outline" | "secondary";
  highlighted?: boolean;
}

const plans: Plan[] = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    priceDetail: "forever",
    badge: "Current Plan",
    features: [
        "3 Workflow Runs / Day",
        "Resume Analysis",
        "AI Job Matching",
        "ATS Optimization",
        "Resume-to-Job Compatibility Report",
        "Personalized Career Recommendations",
        "PDF Report Generation",
        "Basic Email Notifications",
        "Secure Resume Storage",
    ],
    cta: "Current Plan",
    ctaVariant: "secondary",
  },
  {
    id: "professional",
    name: "Professional",
    price: "$14",
    priceDetail: "/ month",
    features: [
        "25 Frontend Workflow Runs / Day",
        "Everything in Free",
        "Hybrid Retrieval Pipeline",
        "RAG Knowledge Retrieval",
        "AI Reranking Engine",
        "Higher Matching Accuracy",
        "Priority Workflow Execution",
        "Advanced Career Intelligence",
        "Enhanced Recommendation Engine",
        "Faster Processing",
        "Premium Support",
    ],
    cta: "Upgrade",
    ctaVariant: "default",
    highlighted: true,
  },
  {
    id: "autonomous",
    name: "Autonomous AI OS",
    price: "$30",
    priceDetail: "/ month",
    features: [
        "Everything in Professional",
        "Unlimited Workflow Runs",
        "24/7 Autonomous AI Agents",
        "Strategic Career Planner",
        "Continuous Job Discovery",
        "Intelligent Application Tracking",
        "Email Monitoring & Follow-ups",
        "AI Memory & Learning",
        "Policy-Governed Decisions",
        "Enterprise AI Automation",
    ],
    cta: "Upgrade",
    ctaVariant: "default",
  },
];

export default function SubscriptionPage() {
  const {
    usage,
    currentPlan,
    plans,
    loading
  } = useSubscription();

  if (loading) {
    return <div>loading ...</div>;
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Subscription
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-base text-muted-foreground">
          Upgrade your AI capabilities and unlock autonomous career automation.
        </p>
      </div>

      {usage && (
        <div className="mb-8 rounded-lg border p-6">
          <h2 className="text-xl font-semibold">
            Current Plan
          </h2>

          <p>{usage.plan}</p>

          <p>
            {usage.used} / {usage.daily_limit} workflow runs used
          </p>

          <p>
            Remaining: {usage.remaining}
          </p>
        </div>
      )}

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {plans.map((plan) => (
          <Card
            key={plan.id}
            className={cn(
              "flex h-full flex-col",
              plan.highlighted && "border-primary/50 shadow-md ring-1 ring-primary/20",
            )}
          >
            <CardHeader className="pb-4">
              {plan.badge && (
                <span className="mb-2 w-fit rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
                  {plan.badge}
                </span>
              )}
              <CardTitle className="text-xl">{plan.name}</CardTitle>
              <CardDescription className="flex items-baseline gap-1">
                <span className="text-3xl font-bold text-foreground">{plan.price}</span>
                <span className="text-sm text-muted-foreground">{plan.priceDetail}</span>
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1">
              <ul className="space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3 text-sm text-foreground">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter className="mt-auto pt-2">
              <Button variant={plan.ctaVariant} className="w-full" disabled={plan.id === "free"}>
                {plan.cta}
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
