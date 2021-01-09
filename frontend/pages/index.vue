<template>
  <div class="p-8 h-screen text-center">
    <h1 class="text-2xl font-light">QuestDB website status</h1>
    <h2 class="text-lg font-thin">service uptime in the past 60 minutes</h2>

    <div class="h-8 mt-12 flex justify-center" v-if="signals.length > 0">
      <div class="w-1/4" v-for="(signal, s) in signals" :key="s">
        <div class="flex mb-1 text-sm">
          <p class="flex-1 text-left font-normal">{{ signal.url }}</p>
          <p class="flex-1 text-right font-thin">{{ uptime(signal.records) }}% uptime</p>
        </div>
        <div class="grid grid-flow-col auto-cols-max gap-x-1">
          <div 
            v-for="(signal, r) in signal.records"
            :key="r"
            :class="`w-1 bg-${signal.available ? 'green' : 'yellow'}-700`"
          >&nbsp;</div>
        </div>
      </div>
    </div>

    <div v-else>
      <p>No signals found</p>
    </div>
  </div>
</template>

<script>
const LIMIT = 60;

async function fetchSignals($axios, limit) {
  const signals = await $axios.$get(`http://localhost:8000/signals?limit=${limit}`)
  return signals
}

export default { 
  data() {
    return {
      signals: []
    }
  },

  async asyncData({ $axios }) {
    const signals = await fetchSignals($axios, LIMIT)
    return { signals }
  },

  methods: {
    uptime: (records) => {
      let availableRecords = records.filter(record => record.available).length;
      return ((availableRecords / records.length) * 100).toFixed(2)
    }
  },

  mounted() {
    let that = this
    const axios = this.$axios;

    setInterval(() => {
      Promise.resolve(fetchSignals(axios, LIMIT)).then((signals) => {
        that.signals = signals
      });
    }, 1000 * LIMIT);
  }
}
</script>
