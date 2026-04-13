import { createApp } from "vue"
import "./style.css"
import App from "./App.vue"
import { useAppState } from "./composables/store"
import { i18n } from "./i18n"
import { router } from "./router"
import ui from "@nuxt/ui/vue-plugin"

const app = createApp(App)
app.use(router)
app.use(ui)
app.use(i18n)

const { locale: storedLocale } = useAppState().value
if (storedLocale === "zh-CN" || storedLocale === "en-US") {
  i18n.global.locale.value = storedLocale
}

app.mount("#app")
