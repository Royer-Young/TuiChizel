/* =========================================================
   推敲 Tuiqiao · 前端逻辑
   技术栈：Vue3 (CDN) + ECharts (CDN)
   视图：
     - main：正式评价界面，请求本地后端 127.0.0.1:8000
     - demo：演示用例，使用固定示例数据，可从页面底部进入并返回
   ========================================================= */
const { createApp } = Vue;

const API_BASE = 'http://127.0.0.1:8000';

/* ---------- 内置示例数据（仅演示用，非真实评分） ---------- */
const DEMO = {
  sample: '面对要不要坚持，我总想起「虽千万人，吾往矣」。这一次，我也没回头。',
  result: {
    _mode: 'demo',
    scores: { 语言表达: 8, 思维品质: 8, 文化理解: 9 },
    comments: {
      语言表达: '用词准确，句式长短相间、疏密有致，行文连贯自然；"虽千万人，吾往矣"的引用与个人经历衔接顺畅，引语与情境贴合。',
      思维品质: '立意有个人判断——"没回头"三字透出取舍的自觉，行文按"典故—对照—决断"推进，逻辑层次清晰，有独立的价值取向。',
      文化理解: '能恰当化用经典表达来承载担当之意，引用未加解释但语境自足，属含蓄用典而非生硬堆砌，对中华优秀传统文化的理解与运用自然贴切。'
    },
    citations: ['K004', 'K007', 'T001'],
    overall: '全篇以含蓄的手法承载坚定之志，用典贴切、留白得当，是一篇兼具语言表现力与思想深度的习作。'
  },
  history: [
    { essay: 1, 语言表达: 7, 思维品质: 7, 文化理解: 7 },
    { essay: 2, 语言表达: 7, 思维品质: 8, 文化理解: 8 },
    { essay: 3, 语言表达: 8, 思维品质: 8, 文化理解: 8 },
    { essay: 4, 语言表达: 9, 思维品质: 8, 文化理解: 9 }
  ],
  citeMap: {
    K004: '课标 · 核心素养 · 语言运用与思维能力的关系',
    K007: '课标 · 学段要求 · 写作要有独立思考与判断',
    T001: '教材《岳阳楼记》· 家国情怀、士人担当'
  }
};

const DIM_META = [
  { key: '语言表达', color: '#2E7D6B', tag: '用词 · 句式 · 连贯', desc: '用词是否准确、句式是否多样、行文是否连贯、标点与书写是否规范' },
  { key: '思维品质', color: '#4A5F9E', tag: '立意 · 逻辑 · 判断', desc: '立意是否有深度、逻辑是否清晰、是否有独立的思考与判断' },
  { key: '文化理解', color: '#B5483B', tag: '三类文化 · 自然融入', desc: '是否恰当体现中华优秀传统文化、革命文化或社会主义先进文化，自然融入而非堆砌' }
];

const app = createApp({
  data() {
    return {
      view: 'main',          // 'main' | 'demo'
      inputMode: 'new',      // 'new' | 'revise'
      essay: '',
      busy: false,
      result: null,
      errorMsg: '',
      // 过程数据
      thinkSeconds: 0,
      revisionCount: 0,
      adoptCount: 0,
      adoptRate: '—',
      dimCards: [],
      // 后端返回的检索依据（用于把 K/T/P 编号显示成出处）
      realRefs: [],
      // 成长曲线
      history: [],
      chartTab: 'line',
      chart: null,
      // 计时器
      timerRunning: false,
      _timer: null,
      _evalStart: 0,
      _mainState: null
    };
  },
  mounted() {
    this.loadRealHistory();
    this.$nextTick(() => this.updateThinkLabel());
    window.addEventListener('resize', this.resizeChart);
  },
  beforeUnmount() {
    clearInterval(this._timer);
    clearTimeout(this._rz);
    window.removeEventListener('resize', this.resizeChart);
  },
  methods: {
    /* ---------- 计时：点击开始评价 -> 结果返回 ---------- */
    updateThinkLabel() {
      const el = this.$refs.thinkEl;
      if (!el) return;
      if (this.timerRunning) {
        const sec = Math.max(0, Math.floor((Date.now() - this._evalStart) / 1000));
        el.textContent = sec + 's';
      } else {
        el.textContent = this.thinkSeconds + 's';
      }
    },
    startEvalClock() {
      clearInterval(this._timer);
      this._evalStart = Date.now();
      this.thinkSeconds = 0;
      this.timerRunning = true;
      this.updateThinkLabel();
      this._timer = setInterval(() => this.updateThinkLabel(), 1000);
    },
    stopEvalClock() {
      clearInterval(this._timer);
      this._timer = null;
      if (this.timerRunning) {
        this.thinkSeconds = Math.max(0, Math.round((Date.now() - this._evalStart) / 1000));
      }
      this.timerRunning = false;
      this.$nextTick(() => this.updateThinkLabel());
    },

    /* ---------- 新作文 / 修改本篇 ---------- */
    setInputMode(mode) {
      if (mode === 'new') {
        this.startNewEssay();
      } else {
        this.inputMode = 'revise';
      }
    },
    startNewEssay() {
      if (this.busy) return;
      // 演示用例始终保留示例作文，切换新建/修改不改变内容
      if (this.view === 'demo') {
        this.inputMode = 'new';
        return;
      }
      clearInterval(this._timer);
      this.timerRunning = false;
      this.essay = '';
      this.result = null;
      this.dimCards = [];
      this.realRefs = [];
      this.errorMsg = '';
      this.thinkSeconds = 0;
      this.revisionCount = 0;
      this.adoptCount = 0;
      this.adoptRate = '—';
      this.inputMode = 'new';
      this.$nextTick(() => {
        this.updateThinkLabel();
        this.drawCharts();
      });
    },
    onEssayInput() {
      if (this.busy) return;
      // 演示用例是静态的，输入不改变任何数值
      if (this.view === 'demo') return;
      // 输入本身不算修改，只有点“修改”按钮进入修改模式后才计数
      this.errorMsg = '';
      // 每次粘贴或修改都把本次评价计时归零
      this.thinkSeconds = 0;
      this.updateThinkLabel();
    },
    // 新建 / 修改按钮：演示用例中完全无反馈
    onNewClick(e) {
      if (this.view === 'demo' || this.busy) return;
      this.startNewEssay();
      this.flashButton(e);
    },
    onReviseClick(e) {
      if (this.view === 'demo' || this.busy) return;
      this.setInputMode('revise');
      this.flashButton(e);
    },
    // 点击时短暂变深，随后恢复白色
    flashButton(e) {
      const el = e && e.currentTarget;
      if (!el) return;
      clearTimeout(el._flashTimer);
      el.classList.add('flash');
      el._flashTimer = setTimeout(() => el.classList.remove('flash'), 160);
    },

    /* ---------- 演示用例 ---------- */
    openDemo() {
      if (this.view === 'demo' || this.busy) return;
      this._mainState = {
        essay: this.essay,
        result: this.result,
        dimCards: this.dimCards,
        history: this.history,
        errorMsg: this.errorMsg,
        thinkSeconds: this.thinkSeconds,
        revisionCount: this.revisionCount,
        adoptCount: this.adoptCount,
        adoptRate: this.adoptRate,
        realRefs: this.realRefs,
        inputMode: this.inputMode,
        chartTab: this.chartTab
      };
      clearInterval(this._timer);
      this.timerRunning = false;
      this.view = 'demo';
      this.essay = DEMO.sample;
      this.result = null;
      this.dimCards = [];
      this.errorMsg = '';
      this.realRefs = [];
      this.thinkSeconds = 0;
      this.revisionCount = 0;
      this.adoptCount = 0;
      this.adoptRate = '—';
      this.inputMode = 'revise';
      this.renderResult(DEMO.result);
      // 固定演示数据，便于展示过程性指标
      this.thinkSeconds = 2;
      this.revisionCount = 2;
      this.$nextTick(() => {
        this.updateThinkLabel();
        this.drawCharts();
      });
    },
    closeDemo() {
      if (this.busy) return;
      this.view = 'main';
      const s = this._mainState || {};
      this.essay = s.essay || '';
      this.result = s.result || null;
      this.dimCards = s.dimCards || [];
      this.history = s.history || [];
      this.errorMsg = s.errorMsg || '';
      this.thinkSeconds = s.thinkSeconds || 0;
      this.revisionCount = s.revisionCount || 0;
      this.adoptCount = s.adoptCount || 0;
      this.adoptRate = s.adoptRate || '—';
      this.realRefs = s.realRefs || [];
      this.inputMode = s.inputMode || 'new';
      this.chartTab = s.chartTab || 'line';
      clearInterval(this._timer);
      this.timerRunning = false;
      this.$nextTick(() => {
        this.updateThinkLabel();
        this.drawCharts();
      });
    },

    /* ---------- 评价主流程 ---------- */
    async evaluate() {
      // 演示用例是静态的：点击开始评价不产生任何反馈
      if (this.view === 'demo' || this.busy) return;
      const text = (this.essay || '').trim();
      if (!text) {
        this.errorMsg = '请先粘贴作文内容再评价。';
        return;
      }
      this.busy = true;
      this.errorMsg = '';
      // 修改次数：只有点“修改”进入修改模式后，每次开始评价 +1
      if (this.inputMode === 'revise') {
        this.revisionCount += 1;
      }
      this.startEvalClock();
      try {
        const payload = {
          text,
          student_id: 'test001',
          think_seconds: 0,
          revision_count: this.revisionCount,
          adopt_count: this.adoptCount
        };
        const resp = await fetch(API_BASE + '/api/evaluate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!resp.ok) {
          let detail = '接口返回 ' + resp.status;
          try {
            const err = await resp.json();
            if (err && err.detail) detail = err.detail;
          } catch (e) { /* ignore */ }
          throw new Error(detail);
        }
        const data = await resp.json();
        data._mode = 'real';
        this.renderResult(data);
        this.stopEvalClock();
        await this.loadRealHistory();
      } catch (e) {
        this.errorMsg = '出错了：' + e.message + '。请确认后端服务已启动后重试。';
        this.stopEvalClock();
      } finally {
        this.stopEvalClock();
        this.busy = false;
      }
    },

    /* ---------- 渲染结果 ---------- */
    renderResult(r) {
      // 先更新检索依据，后面解析“依据”时才能用上
      if (r.refs && Array.isArray(r.refs)) {
        this.realRefs = r.refs;
      } else if (r._mode === 'demo') {
        this.realRefs = [];
      }
      this.dimCards = DIM_META.map(m => {
        const score = (r.scores && r.scores[m.key]) != null ? r.scores[m.key] : 0;
        const comment = (r.comments && r.comments[m.key]) || '（该维度暂无评语）';
        const cite = this.resolveCite(r, m.key);
        return {
          key: m.key,
          name: m.key,
          color: m.color,
          tag: m.tag,
          desc: m.desc,
          score,
          comment,
          cite,
          adopted: false
        };
      });
      this.result = {
        overall: r.overall || '（未返回总评）',
        _mode: r._mode
      };
      this.loadHistory();
      this.drawCharts();
    },
    resolveCite(r, dim) {
      const src = (r.citations && r.citations.length)
        ? this.lookupCite(r.citations, dim)
        : '';
      return src || '（评语未关联知识库条目）';
    },
    lookupCite(citations, dim) {
      const map = { 语言表达: 0, 思维品质: 1, 文化理解: 2 };
      const i = map[dim] != null ? Math.min(map[dim], citations.length - 1) : 0;
      const id = citations[i];
      const ref = (this.realRefs || []).find(x => x.id === id);
      if (ref) return (ref.source ? ref.source + ' · ' : '') + (ref.title || id);
      if (DEMO.citeMap[id]) return DEMO.citeMap[id];
      return '条目 ' + id;
    },

    /* ---------- 采纳按钮 ---------- */
    adopt(key) {
      // 演示用例为静态数据，采纳按钮不产生任何变化
      if (this.view === 'demo') return;
      const card = this.dimCards.find(c => c.key === key);
      if (!card || card.adopted) return;
      card.adopted = true;
      this.adoptCount += 1;
      const total = this.dimCards.length || 1;
      this.adoptRate = (Math.round((this.adoptCount / total) * 100)) + '%';
    },

    /* ---------- 成长曲线数据 ---------- */
    async loadHistory() {
      if (this.view === 'demo') {
        this.history = DEMO.history.slice();
        this.drawCharts();
      }
    },
    async loadRealHistory() {
      try {
        const resp = await fetch(API_BASE + '/api/history/test001');
        if (!resp.ok) throw new Error('history ' + resp.status);
        const rows = await resp.json();
        if (this.view !== 'main') return;
        this.history = (Array.isArray(rows) ? rows : []).map((r, i) => ({
          essay: i + 1,
          语言表达: r.score_json ? JSON.parse(r.score_json).scores['语言表达'] : 0,
          思维品质: r.score_json ? JSON.parse(r.score_json).scores['思维品质'] : 0,
          文化理解: r.score_json ? JSON.parse(r.score_json).scores['文化理解'] : 0
        }));
      } catch (e) {
        this.history = [];
      }
      this.drawCharts();
    },

    /* ---------- ECharts：折线 + 雷达 ---------- */
    drawCharts() {
      const el = document.getElementById('growthChart');
      if (!el || typeof echarts === 'undefined') return;
      if (!this.history.length) {
        if (this.chart) this.chart.clear();
        return;
      }
      if (!this.chart) this.chart = echarts.init(el);
      const option = this.chartTab === 'line' ? this.lineOption() : this.radarOption();
      this.chart.setOption(option, true);
    },
    lineOption() {
      const essays = this.history.map(h => '第' + h.essay + '篇');
      const dims = ['语言表达', '思维品质', '文化理解'];
      return {
        animation: false,
        color: ['#2E7D6B', '#4A5F9E', '#B5483B'],
        tooltip: {
          trigger: 'item',
          hideDelay: 0,
          transitionDuration: 0,
          formatter: p => {
            const idx = p.dataIndex;
            const names = ['语言表达', '思维品质', '文化理解'];
            const colors = ['#2E7D6B', '#4A5F9E', '#B5483B'];
            // 同一篇作文上多条曲线得分相同时，浮框全部列出
            const hit = names
              .map((n, i) => ({ name: n, value: this.history[idx][n], color: colors[i] }))
              .filter(x => Number(x.value) === Number(p.value));
            const rows = (hit.length ? hit : [{ name: p.seriesName, value: p.value, color: p.color }])
              .map(x => `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${x.color};margin-right:6px"></span>${x.name}：${x.value} 分`);
            return `<b>${p.name}</b><br/>${rows.join('<br/>')}`;
          }
        },
        legend: { data: dims, top: 0, textStyle: { color: '#4A5560', fontSize: 12 } },
        grid: { left: 44, right: 20, top: 44, bottom: 32 },
        xAxis: {
          type: 'category', data: essays, boundaryGap: false,
          axisLine: { lineStyle: { color: '#D6CEC0' } },
          axisLabel: { color: '#4A5560' }
        },
        yAxis: {
          type: 'value', min: 0, max: 10, interval: 2,
          axisLine: { show: false }, axisTick: { show: false },
          splitLine: { lineStyle: { color: '#EDE7D9' } },
          axisLabel: { color: '#8A8F98' }
        },
        series: dims.map(d => ({
          name: d, type: 'line', smooth: true,
          symbolSize: 8, data: this.history.map(h => h[d])
        }))
      };
    },
    radarOption() {
      const latest = this.history[this.history.length - 1];
      const indicator = ['语言表达', '思维品质', '文化理解'].map(n => ({ name: n, max: 10 }));
      return {
        animation: false,
        color: ['#B5483B'],
        tooltip: {},
        radar: {
          indicator,
          radius: '62%',
          axisName: { color: '#242E38', fontSize: 13 },
          splitLine: { lineStyle: { color: '#E3DCCE' } },
          splitArea: { areaStyle: { color: ['#FFFFFF', '#F6F3EA'] } },
          axisLine: { lineStyle: { color: '#D6CEC0' } }
        },
        series: [{
          type: 'radar',
          data: [{
            value: [latest['语言表达'], latest['思维品质'], latest['文化理解']],
            name: '第' + latest.essay + '篇',
            areaStyle: { opacity: 0.25 },
            lineStyle: { width: 2 }
          }]
        }]
      };
    },
    resizeChart() {
      // 注意：直接调用 chart.resize() 在 echarts 5 会触发内部报错（orphan tween bug）。
      // 改为在窗口尺寸变化时销毁并重建图表，保证响应式且不报错。
      clearTimeout(this._rz);
      this._rz = setTimeout(() => {
        if (!this.chart) return;
        try { this.chart.dispose(); } catch (e) { /* ignore */ }
        this.chart = null;
        this.drawCharts();
      }, 200);
    }
  }
});

app.mount('#app');
