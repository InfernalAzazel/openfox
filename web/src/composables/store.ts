import { createGlobalState, useStorage } from "@vueuse/core"

/** 与 vue-i18n locale 一致 */
export type AppLocale = "en-US" | "zh-CN"

export const useAppState = createGlobalState(() =>
  useStorage<{
    access_token: string
    /** Agent OS 根地址，如 `http://127.0.0.1:7777`（无尾斜杠） */
    os_base_url: string
    /** 界面语言；旧数据无此字段时由 useStorage 与默认值合并得到 */
    locale: AppLocale
  }>("openfox", {
    access_token: "",
    os_base_url: "",
    locale: "en-US",
  }),
)
