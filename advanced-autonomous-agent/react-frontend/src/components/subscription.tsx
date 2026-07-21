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

import { UI_PLANS } from "@/subscription/planFeature";

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
        {plans.map((plan) => {
          const isCurrent = currentPlan?.plan === plan.id;
          const highlighted = plan.id === "professional";
          const uiFeatures = UI_PLANS[plan.id]?.features ?? plan.features

          return (
            <Card
              key={plan.id}
              className={cn(
                "flex h-full flex-col",
                highlighted &&
                  "border-primary/50 shadow-md ring-1 ring-primary/20",
                isCurrent && "border-green-500 ring-2 ring-green-500/30"
              )}
            >
              <CardHeader className="pb-4">
                {isCurrent && (
                  <span className="mb-2 w-fit rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium">
                    Current Plan
                  </span>
                )}

                <CardTitle className="text-xl">
                  {plan.display_name}
                </CardTitle>

                <CardDescription>
                  <div className="flex items-end gap-1">
                    <span className="text-3xl font-bold text-foreground">
                      ${plan.price}
                    </span>

                    <span className="text-sm text-muted-foreground">
                      {plan.billing_period === "Free"
                        ? "Forever"
                        : `/ ${plan.billing_period}`}
                    </span>
                  </div>

                  <p className="mt-2 text-sm text-muted-foreground">
                    {plan.description}
                  </p>
                </CardDescription>
              </CardHeader>

              <CardContent className="flex-1">
                <ul className="space-y-3">
                  {uiFeatures.map((feature) => (
                    <li
                      key={feature}
                      className="flex items-start gap-3 text-sm"
                    >
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>

              <CardFooter className="mt-auto">
                <Button
                  className="w-full"
                  variant={isCurrent ? "secondary" : "default"}
                  disabled={isCurrent}
                >
                  {isCurrent ? "Current Plan" : "Upgrade"}
                </Button>
              </CardFooter>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
