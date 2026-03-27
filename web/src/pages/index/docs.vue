<script setup lang="ts">
import { useI18n } from "vue-i18n"
import AppPageScaffold from "@/components/AppPageScaffold.vue"

const { t } = useI18n()
</script>

<template>
  <AppPageScaffold>
    <p class="max-w-xl text-sm leading-relaxed text-foreground">
      {{ t("docs.intro") }}
      <a
        href="https://github.com/InfernalAzazel/openfox"
        class="font-medium text-[#E11D48] underline-offset-4 hover:underline"
        target="_blank"
        rel="noopener noreferrer"
      >github.com/InfernalAzazel/openfox</a>
    </p>
  </AppPageScaffold>
</template>
