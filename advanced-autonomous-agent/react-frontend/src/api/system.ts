import axios from "axios";

const BASE_URL =
  import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export const getSystemStatus = async () => {
  const token = localStorage.getItem("auth_token");

  const response = await axios.get(
    `${BASE_URL}/app/system/status`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );

  return response.data;
};
