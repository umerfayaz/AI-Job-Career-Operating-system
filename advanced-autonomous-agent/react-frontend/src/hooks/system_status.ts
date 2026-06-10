import {useQuery} from "@tanstack/react-query"
import { getSystemStatus } from "@/api/system"


export const useSystemStatus = () => {
    return useQuery({
        queryKey: ["system-status"],
        queryFn: getSystemStatus,
        refetchInterval: 5000,
    });
};

