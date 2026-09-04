import { API_BASE_URL, apiFetch } from "./config";

export async function getHealth() {
  const response = await apiFetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`Backend responded with status ${response.status}`);
  }

  return response.json();
}
