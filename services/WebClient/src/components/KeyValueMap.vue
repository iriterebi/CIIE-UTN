<script setup lang="ts">
import { computed, toRaw } from 'vue';

defineOptions({
  inheritAttrs: true
})


const props = defineProps<{
    map: Record<string, unknown>
}>()

const isNoObj = (obj: any) => (typeof obj !== 'object' || obj === null)
function toEntries(obj: any): [string, any] | any {
    obj = toRaw(obj)
    if (isNoObj(obj) || Array.isArray(obj)) return obj

    return Object.entries(obj).map(([KeyboardEvent, value]) => [
        KeyboardEvent,
        toEntries(value)
    ])
}

const stateAsEntries = computed((): [string, any] => toEntries(props.map))


</script>
<template>
    <section class="container">
        <template v-for="([key, value]) in stateAsEntries">
            <div class="keyvalue">
                <p class="key">{{ key }}</p>
                <p class="value" v-if="isNoObj(value)">{{ value }}</p>
                <KeyValueMap v-else :map="value" class="ml value" />
            </div>
        </template>
    </section>
</template>
<style scoped>
.ml {
    margin-left: 1rem;
}

.keyvalue {
    display: grid;
    grid-template-columns: auto 1fr;
    grid-gap: 1rem;
    align-items: center;
    margin-block: 0.125em;

    & > p {
        margin-bottom: 0;
    }
}

.key {
    font-weight: bold;
}

.value:not(.ml) {
    font-family: monospace;
}

.container {
    margin: 0;
}
</style>
