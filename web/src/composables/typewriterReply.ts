/**
 * 将完整回复按字符逐步交给 UI（含中文等多字节字符），返回取消函数；取消时会立刻补全全文。
 */
export function runTypewriter(
  fullText: string,
  onUpdate: (visible: string) => void,
  options?: {
    msPerChar?: number
    onComplete?: () => void
  },
): () => void {
  const chars = Array.from(fullText)
  if (chars.length === 0) {
    onUpdate("")
    queueMicrotask(() => options?.onComplete?.())
    return () => {}
  }

  const ms = Math.max(4, options?.msPerChar ?? 22)
  let i = 0
  let cancelled = false
  let timer: ReturnType<typeof setTimeout> | null = null

  function flushFull() {
    onUpdate(fullText)
  }

  function scheduleNext() {
    timer = setTimeout(tick, ms)
  }

  function tick() {
    timer = null
    if (cancelled) return
    if (i >= chars.length) {
      options?.onComplete?.()
      return
    }
    i += 1
    onUpdate(chars.slice(0, i).join(""))
    scheduleNext()
  }

  scheduleNext()

  return () => {
    cancelled = true
    if (timer != null) clearTimeout(timer)
    flushFull()
  }
}
