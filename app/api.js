export async function apiRequest(path, options = {}) {
  const fetchOptions = {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
  };

  if (options.body) {
    fetchOptions.body = JSON.stringify(options.body);
  }

  let response;
  try {
    response = await fetch(path, fetchOptions);
  } catch {
    throw new Error("サーバーに接続できませんでした。時間をおいてもう一度お試しください。");
  }

  if (!response.ok) {
    const message = await readErrorMessage(response);
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  if (response.status === 204) return null;
  return response.json();
}

async function readErrorMessage(response) {
  try {
    const data = await response.json();
    return data.error || "リクエストに失敗しました。";
  } catch {
    return "リクエストに失敗しました。";
  }
}
