type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

type RequestOptions<TBody> = {
  method?: HttpMethod;
  body?: TBody;
  userId?: number;
};

type ApiErrorPayload = {
  detail?: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const TRANSPORT_ERROR_STATUS = 0;
const INVALID_SUCCESS_STATUS = 502;

function mapTransportError(): ApiError {
  return new ApiError(
    TRANSPORT_ERROR_STATUS,
    "Falha de conexao. Verifique sua internet e tente novamente.",
  );
}

function invalidSuccessPayloadError(): ApiError {
  return new ApiError(INVALID_SUCCESS_STATUS, "Resposta de sucesso invalida do servidor.");
}

function mapApiError(status: number, detail?: string): ApiError {
  if (status === 400) {
    return new ApiError(400, detail ?? "Requisicao invalida.");
  }

  if (status === 404) {
    return new ApiError(404, detail ?? "Recurso nao encontrado.");
  }

  if (status === 403) {
    return new ApiError(403, detail ?? "Acesso negado.");
  }

  if (status === 503) {
    return new ApiError(503, "Servico indisponivel. Tente novamente em instantes.");
  }

  return new ApiError(status, detail ?? "Erro inesperado. Tente novamente.");
}

export async function request<TResponse, TBody = undefined>(
  path: string,
  options: RequestOptions<TBody> = {},
): Promise<TResponse> {
  const { method = "GET", body, userId } = options;
  const headers: Record<string, string> = {};

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  if (userId !== undefined) {
    headers["X-User-Id"] = String(userId);
  }

  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw mapTransportError();
  }

  let payload: unknown;
  const contentType = response.headers.get("Content-Type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      if (response.ok) {
        throw invalidSuccessPayloadError();
      }
    }
  }

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as ApiErrorPayload).detail
        : undefined;

    throw mapApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  if (!contentType.includes("application/json") || payload === undefined) {
    throw invalidSuccessPayloadError();
  }

  return payload as TResponse;
}
