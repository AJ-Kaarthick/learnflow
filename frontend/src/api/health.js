import { API_BASE_URL } from "./config";

export async function getHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`Backend responded with status ${response.status}`);
  }

  return response.json();
}
