import axios from "axios";

export const getSystemStatus = async () => {
    const token = localStorage.getItem("auth_token");

    const response = await axios.get(
        "/app/system/status",
        {
            headers: {
                Authorization: `Bearer ${token}`
            }
        }
    );

    return response.data;
};

