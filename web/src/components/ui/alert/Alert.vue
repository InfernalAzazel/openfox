<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const alertVariants = cva(
  "relative w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-card-foreground shadow-sm [&:has(>svg)]:pl-10 [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:size-4 [&>svg]:text-foreground",
  {
    variants: {
      variant: {
        default: "",
        destructive:
          "border-destructive/50 text-destructive [&>svg]:text-destructive *:data-[slot=alert-description]:text-destructive/90 dark:border-destructive",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

type AlertVariants = VariantProps<typeof alertVariants>

const props = defineProps<{
  class?: HTMLAttributes["class"]
  variant?: AlertVariants["variant"]
}>()
</script>

<template>
  <div
    data-slot="alert"
    role="alert"
    :class="cn(alertVariants({ variant: props.variant }), props.class)"
  >
    <slot />
  </div>
</template>
