import { AlertTriangle, Crown, Zap } from "lucide-react";
import { useNavigate } from "react-router-dom";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface WorkflowLimitDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  limitInfo: {
    limit: number;
    used: number;
    remaining: number;
    workflow_type: string;
  } | null;
}

export default function WorkflowLimitDialog({
  open,
  onOpenChange,
  limitInfo,
}: WorkflowLimitDialogProps) {
  const navigate = useNavigate();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
            <AlertTriangle className="h-7 w-7 text-destructive" />
          </div>

          <DialogTitle className="text-center text-2xl">
            Daily Workflow Limit Reached
          </DialogTitle>

          <DialogDescription className="text-center">
            You've used all of today's workflow runs available on your current
            subscription.
          </DialogDescription>
        </DialogHeader>

        <Card className="mt-4 p-5 space-y-4">

          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              Daily Limit
            </span>

            <span className="font-semibold">
              {limitInfo?.limit ?? "-"}
            </span>
          </div>

          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              Used Today
            </span>

            <span className="font-semibold">
              {limitInfo?.used ?? "-"}
            </span>
          </div>

          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              Remaining
            </span>

            <span className="font-semibold text-destructive">
              {limitInfo?.remaining ?? 0}
            </span>
          </div>
        </Card>

        <Card className="mt-5 border-primary/30 bg-primary/5 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Crown className="h-5 w-5 text-primary" />

            <h3 className="font-semibold">
              Upgrade to Professional
            </h3>
          </div>

          <div className="space-y-2 text-sm text-muted-foreground">

            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary" />
              <span>25 workflow runs every day</span>
            </div>

            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary" />
              <span>Hybrid Retrieval Pipeline</span>
            </div>

            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary" />
              <span>Advanced AI Matching</span>
            </div>

            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary" />
              <span>Priority Processing</span>
            </div>

          </div>
        </Card>

        <div className="mt-6 flex gap-3">

          <Button
            variant="outline"
            className="flex-1"
            onClick={() => onOpenChange(false)}
          >
            Maybe Later
          </Button>

          <Button
            className="flex-1"
            onClick={() => {
              onOpenChange(false);
              navigate("/subscription");
            }}
          >
            Upgrade Plan
          </Button>

        </div>
      </DialogContent>
    </Dialog>
  );
}