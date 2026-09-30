<!-- designed by mew -->
<script setup lang="ts">
defineProps<{
  name:
    | 'arrow-up-right'
    | 'arrow-right'
    | 'arrow-left'
    | 'arrow-up'
    | 'arrow-down'
    | 'play'
    | 'pause'
    | 'search';
}>();
</script>

<template>
  <svg
    class="ui-icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-if="name === 'arrow-up-right'" d="M5 19 19 5M8 5h11v11" />
    <path v-else-if="name === 'arrow-right'" d="M4 12h16m-7-7 7 7-7 7" />
    <path v-else-if="name === 'arrow-left'" d="M20 12H4m7-7-7 7 7 7" />
    <path v-else-if="name === 'arrow-up'" d="M12 20V4m-7 7 7-7 7 7" />
    <path v-else-if="name === 'arrow-down'" d="M12 4v16m-7-7 7 7 7-7" />
    <path v-else-if="name === 'play'" d="m8 5 11 7-11 7V5Z" fill="currentColor" stroke="none" />
    <path v-else-if="name === 'pause'" d="M8 5v14m8-14v14" stroke-width="2.6" />
    <template v-else-if="name === 'search'">
      <circle cx="10.8" cy="10.8" r="6.4" />
      <path d="m15.5 15.5 5 5" />
    </template>
  </svg>
</template>

<style scoped>
.ui-icon {
  display: inline-block;
  width: 1em;
  height: 1em;
  flex: none;
  vertical-align: -0.12em;
  overflow: visible;
}
</style>
