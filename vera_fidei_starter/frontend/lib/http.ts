export const DEFAULT_REQUEST_TIMEOUT_MS = 15_000
export const LONG_REQUEST_TIMEOUT_MS = 30_000

export const DEFAULT_TIMEOUT_MESSAGE =
  'A solicitação demorou demais. Verifique sua conexão e tente novamente.'

export class RequestTimeoutError extends Error {
  readonly status = 408
  readonly timeoutMs: number

  constructor(message = DEFAULT_TIMEOUT_MESSAGE, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS) {
    super(message)
    this.name = 'RequestTimeoutError'
    this.timeoutMs = timeoutMs
  }
}

interface FetchWithTimeoutOptions {
  timeoutMs?: number
  timeoutMessage?: string
}

/**
 * Executa uma requisição HTTP limitada no tempo e preserva qualquer sinal de
 * cancelamento fornecido pelo chamador. Streams devem continuar em fetch()
 * direto; uploads grandes precisam informar um timeout longo e explícito.
 */
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  options: FetchWithTimeoutOptions = {},
): Promise<Response> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS
  const timeoutMessage = options.timeoutMessage ?? DEFAULT_TIMEOUT_MESSAGE
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return fetch(input, init)
  }

  const controller = new AbortController()
  const parentSignal = init.signal
  let timedOut = false
  let timeoutId: ReturnType<typeof setTimeout> | undefined
  let cleanedUp = false

  const cleanup = () => {
    if (cleanedUp) return
    cleanedUp = true
    if (timeoutId !== undefined) globalThis.clearTimeout(timeoutId)
    parentSignal?.removeEventListener('abort', abortFromParent)
  }

  const timeoutError = () => new RequestTimeoutError(timeoutMessage, timeoutMs)

  const abortFromParent = () => controller.abort(parentSignal?.reason)
  if (parentSignal?.aborted) {
    abortFromParent()
  } else {
    parentSignal?.addEventListener('abort', abortFromParent, { once: true })
  }

  const request = fetch(input, { ...init, signal: controller.signal })
  const timeout = new Promise<Response>((_, reject) => {
    timeoutId = globalThis.setTimeout(() => {
      timedOut = true
      const error = timeoutError()
      controller.abort(error)
      reject(error)
    }, timeoutMs)
  })

  try {
    const response = await Promise.race([request, timeout])

    // fetch() conclui quando os cabeçalhos chegam. Mantemos o temporizador até
    // json(), text(), blob(), formData() ou arrayBuffer() terminar, evitando que
    // um corpo interrompido deixe a interface presa em carregamento.
    const responseWithTimedBody = response as Response & {
      bytes?: () => Promise<Uint8Array>
    }
    const bodyMethods = ['arrayBuffer', 'blob', 'formData', 'json', 'text', 'bytes'] as const
    for (const method of bodyMethods) {
      const original = responseWithTimedBody[method]
      if (typeof original !== 'function') continue
      Object.defineProperty(responseWithTimedBody, method, {
        configurable: true,
        value: async () => {
          try {
            return await Promise.race([
              original.call(responseWithTimedBody),
              timeout,
            ])
          } catch (error) {
            if (timedOut) throw timeoutError()
            throw error
          } finally {
            cleanup()
          }
        },
      })
    }

    if (response.body === null) cleanup()
    return responseWithTimedBody
  } catch (error) {
    cleanup()
    if (timedOut && !(error instanceof RequestTimeoutError)) {
      throw timeoutError()
    }
    throw error
  }
}
