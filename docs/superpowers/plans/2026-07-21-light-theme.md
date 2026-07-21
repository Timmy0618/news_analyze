# 開燈模式（Light Theme）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在前端新增亮色主題並設為預設，保留原本的暗色 Signal Monitor 主題，header 提供 sun/moon 切換鈕，選擇記在 `localStorage`。

**Architecture:** UI 配色靠 `frontend/src/index.css` 的 Tailwind v4 `@theme` 色階映射。Tailwind v4 會把 `bg-gray-900` 編成 `var(--color-gray-900)`，所以把 `@theme` 改成亮色（預設），再用 `[data-theme="dark"]` scope 覆寫回暗色，所有 utility-class 元件即自動換色，不需改元件。三處寫死顏色的資料視覺化中：BiasPage 用 CSS 變數（DOM 讀 cascade，最省）；TopicStats 與 GraphPage 因 recharts contentStyle / canvas fillStyle 需要 JS 端色值字串，改由 App 傳入 `theme` prop 後在元件內選色盤。

**Tech Stack:** React 19、Tailwind v4（`@tailwindcss/vite`）、recharts、react-force-graph-2d、react-icons（`FiSun`/`FiMoon`）。全部已安裝，無新增相依。

## Global Constraints

- 亮色為預設；無 `localStorage.theme` 或值為 `light` 時 → 亮色。只在值為 `dark` 時套暗色。
- 不跟隨系統 `prefers-color-scheme`（使用者明確要求預設亮色）。
- 不新增任何相依套件；`FiSun`/`FiMoon` 來自已裝的 `react-icons/fi`。
- **無 JS 測試框架**：前端無 vitest/jest（`package.json` 無 `test` script），本任務不新增（為 theming 加測試框架屬過度設計）。每個 task 的驗證閘門為：`cd frontend && npm run build`（tsc 型別檢查 + vite build）通過、`npm run lint` 無錯、加上明確的瀏覽器手動檢查。
- 亮色文字對比需達 WCAG AA（一般文字 ≥ 4.5:1）；amber 純作裝飾（填色/邊框/圓點），文字用深古銅色。
- 所有工作在分支 `feat/light-theme` 上，逐 task commit。
- 顏色 token 值一律照本計畫表格逐字使用。

---

### Task 1: 亮色調色盤 + 暗色覆寫（index.css）

把 `@theme` 的顏色值改為亮色，新增 `[data-theme="dark"]` 覆寫回原暗色，`.eyebrow` 改 per-theme，並新增 BiasPage 用的 bias 色 CSS 變數（兩主題）。字體 token 不動。

**Files:**
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: CSS 變數 `--color-gray-{50..950}`、`--color-blue/indigo/purple/green/yellow/orange-*` 於 `:root`（亮色預設）與 `[data-theme="dark"]`（暗色）；bias 變數 `--bias-a-text`、`--bias-b-text`、`--bias-neutral-text`、`--bias-a-ink`、`--bias-b-ink`（Task 3 使用）。

- [ ] **Step 1: 改 `@theme` 顏色區塊為亮色**

把 `frontend/src/index.css` 中從 `--color-gray-950:` 到 `/* red (errors) left at Tailwind defaults */` 的整段（目前的暗色值，約第 25–71 行）替換為以下亮色值（保留上方 `--font-sans` / `--font-mono` 不動）：

```css
  /* ---- Neutral: warm PAPER base (light default) ------------------ */
  /* 950 保持深墨：唯一用途是 btnPrimary 在 amber 底上的文字色 */
  --color-gray-950: #141310;
  --color-gray-900: #f4efe3; /* app base (paper)                  */
  --color-gray-800: #ece6d8; /* panel surface                     */
  --color-gray-700: #e2dccb; /* raised: inputs, pills, hairline   */
  --color-gray-600: #d3cbb6; /* borders, list rails               */
  --color-gray-500: #8a8069; /* muted dividers / IDs / eyebrows   */
  --color-gray-400: #6b6250; /* secondary / meta (mono)           */
  --color-gray-300: #3a352b; /* primary body text (AA on paper)   */
  --color-gray-200: #2a261e;
  --color-gray-100: #1e1b15;
  --color-gray-50:  #141310; /* headings (ink)                    */

  /* ---- Signal: amber. Text roles darkened for AA on paper ------ */
  --color-blue-700: #6e4a06;
  --color-blue-600: #b7860b; /* primary button fill (dark text)   */
  --color-blue-500: #b7860b; /* signal / focus ring / active edge */
  --color-blue-400: #8a5e08; /* links, active, key figures        */
  --color-blue-300: #6e4a06; /* link hover                        */

  /* ---- Every other accent family collapses to amber ----------- */
  --color-indigo-600: #b7860b;
  --color-indigo-500: #b7860b;
  --color-purple-600: #b7860b;
  --color-purple-500: #b7860b;
  --color-purple-400: #8a5e08;
  --color-purple-300: #6e4a06;
  --color-green-600: #6e4a06;
  --color-green-500: #b7860b;
  --color-green-400: #8a5e08;

  /* ---- Warning + date highlight: amber family (light) --------- */
  --color-yellow-900: #fbf1d0; /* warn surface                    */
  --color-yellow-600: #d9a441; /* warn border                     */
  --color-yellow-400: #8a5e08; /* date highlight                  */
  --color-yellow-300: #6e4a06;
  --color-yellow-200: #5a3d05;

  /* ---- Bias "B side" / partisan: red (remaps orange) ---------- */
  --color-orange-600: #c0362f;
  --color-orange-500: #dc2626;
  --color-orange-400: #b91c1c;

  /* red (errors) left at Tailwind defaults */
```

- [ ] **Step 2: 新增暗色覆寫 + bias token + eyebrow per-theme**

在 `frontend/src/index.css` 的 `@theme { ... }` 區塊「之後、`@layer base` 之前」插入以下整段。`[data-theme="dark"]` 用原本的暗色值：

```css
/* =============================================================
   Dark theme override — the original Signal Monitor palette.
   Utilities read var(--color-*), so re-declaring the vars in this
   scope re-skins everything when data-theme="dark" is set.
   ============================================================= */
[data-theme="dark"] {
  --color-gray-950: #0c0b08;
  --color-gray-900: #141310;
  --color-gray-800: #1b1813;
  --color-gray-700: #26221a;
  --color-gray-600: #342f24;
  --color-gray-500: #6b6250;
  --color-gray-400: #a89e88;
  --color-gray-300: #c9c0ad;
  --color-gray-200: #ddd5c6;
  --color-gray-100: #ece6d8;
  --color-gray-50:  #f4efe3;

  --color-blue-700: #b7860b;
  --color-blue-600: #e0a020;
  --color-blue-500: #f0b429;
  --color-blue-400: #f5c451;
  --color-blue-300: #f8d585;

  --color-indigo-600: #e0a020;
  --color-indigo-500: #f0b429;
  --color-purple-600: #e0a020;
  --color-purple-500: #f0b429;
  --color-purple-400: #f5c451;
  --color-purple-300: #f8d585;
  --color-green-600: #b7860b;
  --color-green-500: #e0a020;
  --color-green-400: #f5c451;

  --color-yellow-900: #3a2a08;
  --color-yellow-600: #e0a020;
  --color-yellow-400: #f5c451;
  --color-yellow-300: #f8d585;
  --color-yellow-200: #fbe4ae;

  --color-orange-600: #c0362f;
  --color-orange-500: #e5484d;
  --color-orange-400: #f16a6e;
}

/* Bias partisan colors — flipped per theme; consumed via
   text-[var(--bias-*)] classes and inline style in BiasPage. */
:root {
  --bias-a-text: #1d4ed8;
  --bias-b-text: #b91c1c;
  --bias-neutral-text: #6b6250;
  --bias-a-ink: #1d4ed8;
  --bias-b-ink: #c0362f;
}
[data-theme="dark"] {
  --bias-a-text: #6ea8fe;
  --bias-b-text: #f16a6e;
  --bias-neutral-text: #a89e88;
  --bias-a-ink: #3b82f6;
  --bias-b-ink: #e5484d;
}
```

- [ ] **Step 3: `.eyebrow` 改 per-theme**

在 `frontend/src/index.css` 底部找到 `.eyebrow { ... }`，把其中的：

```css
  color: #9a9078; /* muted, but AA-legible on graphite (~5.5:1) */
```

改為（亮色預設較深，暗色沿用原值）：

```css
  color: #6b6250; /* muted, AA on paper */
```

並在 `.eyebrow { ... }` 規則「之後」新增一行覆寫：

```css
[data-theme="dark"] .eyebrow { color: #9a9078; }
```

- [ ] **Step 4: 型別/建置驗證**

Run: `cd frontend && npm run build && npm run lint`
Expected: build 成功（無 tsc 錯）、lint 無錯。

- [ ] **Step 5: 手動視覺驗證**

Run: `cd frontend && npm run dev`，瀏覽器開 dev URL。
Expected：整個 App 為亮色（暖紙底、深字），文字清楚可讀；在 devtools 對 `<html>` 加上 `data-theme="dark"` → 立即變回原暗色 Signal Monitor。移除屬性 → 回亮色。

- [ ] **Step 6: Commit**

```bash
cd /home/timmy/code/news_analyze
git add frontend/src/index.css
git commit -m "feat(frontend): 亮色調色盤為預設，暗色改由 data-theme 覆寫"
```

---

### Task 2: 主題狀態 + 切換鈕 + 持久化 + 無閃爍

新增 `useTheme` hook 與 no-FOUC inline script，App header 加 sun/moon 切換鈕，並把 `theme` 準備好供後續 viz task 取用。

**Files:**
- Create: `frontend/src/lib/theme.ts`
- Modify: `frontend/index.html`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces:
  - `type Theme = 'light' | 'dark'`
  - `useTheme(): { theme: Theme; toggle: () => void }` — 來自 `frontend/src/lib/theme.ts`；`toggle` 會切換並寫入 `localStorage.theme` 且設定 `document.documentElement.dataset.theme`。
  - App 內持有的 `theme: Theme`，Task 4/5 會以 `<TopicStats theme={theme} />`、`<GraphPage theme={theme} />` 形式傳下。

- [ ] **Step 1: 建立 `frontend/src/lib/theme.ts`**

```ts
import { useCallback, useState } from 'react'

export type Theme = 'light' | 'dark'

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem('theme', theme)
  } catch {
    // localStorage 不可用（隱私模式等）時忽略；主題仍於本次 session 生效
  }
}

// Single source of truth: initial value comes from the attribute the
// index.html inline script already set before paint (default light).
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(currentTheme)
  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next: Theme = prev === 'dark' ? 'light' : 'dark'
      applyTheme(next)
      return next
    })
  }, [])
  return { theme, toggle }
}
```

- [ ] **Step 2: index.html 加 no-FOUC script**

在 `frontend/index.html` 的 `<title>...</title>`（第 7 行）之後、`</head>` 之前插入：

```html
    <script>
      // Apply stored theme before paint to avoid a flash. Default = light.
      try {
        var t = localStorage.getItem('theme');
        if (t) document.documentElement.dataset.theme = t;
      } catch (e) {}
    </script>
```

- [ ] **Step 3: App 匯入 icon 與 hook**

在 `frontend/src/App.tsx` 第 3 行的 import 尾端加入 `FiSun, FiMoon`：

```tsx
import { FiBarChart2, FiSearch, FiBookOpen, FiShare2, FiAlertTriangle, FiSun, FiMoon } from 'react-icons/fi'
```

在第 10 行（`import { supabase, supabaseConfigured } ...`）之後新增：

```tsx
import { useTheme } from './lib/theme'
```

- [ ] **Step 4: 新增切換鈕元件**

在 `frontend/src/App.tsx` 的 `StatusStrip` 函式定義（第 72 行 `}` 結尾）之後新增：

```tsx
function ThemeToggle({ theme, onToggle }: { theme: 'light' | 'dark'; onToggle: () => void }) {
  const toDark = theme === 'light'
  return (
    <button
      onClick={onToggle}
      aria-label={toDark ? '切換為暗色模式' : '切換為亮色模式'}
      title={toDark ? '暗色模式' : '亮色模式'}
      className="p-1.5 rounded-sm text-gray-400 hover:text-gray-50 hover:bg-gray-700 transition-colors"
    >
      {toDark ? <FiMoon size={16} aria-hidden /> : <FiSun size={16} aria-hidden />}
    </button>
  )
}
```

- [ ] **Step 5: 在 App 使用 hook 並把鈕放進 header**

在 `frontend/src/App.tsx` 的 `export default function App() {` 內，把：

```tsx
export default function App() {
  const [tab, setTab] = useState<TabId>('stats')
```

改為：

```tsx
export default function App() {
  const [tab, setTab] = useState<TabId>('stats')
  const { theme, toggle } = useTheme()
```

再把 header 內的：

```tsx
          <StatusStrip />
```

改為（切換鈕放在狀態列右側）：

```tsx
          <div className="flex items-center gap-4">
            <StatusStrip />
            <ThemeToggle theme={theme} onToggle={toggle} />
          </div>
```

> 註：`theme` 目前在 App 已就緒；Task 4/5 會把它作為 prop 傳給 `TopicStats` 與 `GraphPage`。本 task 先不接（避免動到還沒改的元件簽名）。若 lint 因 `theme` 暫未使用而報 `no-unused-vars`，本 step 已透過 `<ThemeToggle theme={theme} .../>` 使用它，故不會觸發。

- [ ] **Step 6: 型別/建置驗證**

Run: `cd frontend && npm run build && npm run lint`
Expected: 通過、無錯。

- [ ] **Step 7: 手動驗證持久化與無閃爍**

Run: `cd frontend && npm run dev`
Expected：
1. 首次載入為亮色，header 右側顯示月亮圖示（點了會切暗）。
2. 點擊 → 立即變暗色，圖示變太陽。
3. 重新整理頁面 → 維持暗色，且**載入瞬間無亮色閃爍**。
4. 再點 → 回亮色；重新整理維持亮色。
5. `localStorage` 內 `theme` 隨切換更新。

- [ ] **Step 8: Commit**

```bash
cd /home/timmy/code/news_analyze
git add frontend/src/lib/theme.ts frontend/index.html frontend/src/App.tsx
git commit -m "feat(frontend): 主題切換鈕 + localStorage 持久化 + 無閃爍載入"
```

---

### Task 3: BiasPage 偏頗色 per-theme（CSS 變數）

把 BiasPage 寫死的藍/紅偏頗色改為引用 Task 1 定義的 CSS 變數，讓它隨主題自動適配。不需 `theme` prop（DOM 直接讀 cascade）。

**Files:**
- Modify: `frontend/src/components/BiasPage.tsx`

**Interfaces:**
- Consumes: Task 1 的 `--bias-a-text`、`--bias-b-text`、`--bias-neutral-text`、`--bias-a-ink`、`--bias-b-ink`。

- [ ] **Step 1: 改常數為 CSS 變數引用**

在 `frontend/src/components/BiasPage.tsx` 把第 11–14 行：

```tsx
const BIAS_A = '#3b82f6'
const BIAS_A_TEXT = 'text-[#6ea8fe]'
const BIAS_B = '#e5484d'
const BIAS_B_TEXT = 'text-[#f16a6e]'
```

改為：

```tsx
// 偏頗藍/紅隨主題切換：色值集中在 index.css 的 --bias-* 變數。
const BIAS_A = 'var(--bias-a-ink)'
const BIAS_A_TEXT = 'text-[var(--bias-a-text)]'
const BIAS_B = 'var(--bias-b-ink)'
const BIAS_B_TEXT = 'text-[var(--bias-b-text)]'
```

- [ ] **Step 2: 改 VERDICT 的 neutral 文字色**

在同檔第 16–20 行的 `VERDICT`，把第 18 行 neutral 的 `text-[#a89e88]` 改為 `text-[var(--bias-neutral-text)]`。改完為：

```tsx
const VERDICT: Record<Verdict, { label: string; bar: string; text: string }> = {
  side_a:  { label: '偏A方', bar: 'bg-[#3b82f6]', text: BIAS_A_TEXT },
  neutral: { label: '中立',  bar: 'bg-[#6b6250]', text: 'text-[var(--bias-neutral-text)]' },
  side_b:  { label: '偏B方', bar: 'bg-[#e5484d]', text: BIAS_B_TEXT },
}
```

> `bar` 的 `bg-[#3b82f6]` / `bg-[#e5484d]` / `bg-[#6b6250]` 保持不變——飽和藍紅與中性灰在亮/暗底上皆可辨識，色塊不需對比達文字標準。

- [ ] **Step 3: 確認 inline 用法無需再改**

第 158、160 行使用 `style={{ color: BIAS_A }}` / `style={{ color: BIAS_B }}`；因 `BIAS_A`/`BIAS_B` 已改為 `var(--bias-a-ink)`/`var(--bias-b-ink)`，這兩行自動生效，**不需修改**。

- [ ] **Step 4: 型別/建置驗證**

Run: `cd frontend && npm run build && npm run lint`
Expected: 通過、無錯。

- [ ] **Step 5: 手動驗證**

Run: `cd frontend && npm run dev` → 切到「偏頗分析」分頁。
Expected：
1. 亮色下：偏A文字為深藍（`#1d4ed8`）、偏B為深紅（`#b91c1c`）、中立為 `#6b6250`，皆清楚可讀於紙底；A/B 主題名（ClusterCard 內）為深藍/深紅。
2. 切暗色：文字回到原本的亮藍（`#6ea8fe`）/亮紅（`#f16a6e`）/`#a89e88`。
3. 立場長條（bar）在兩主題皆為藍/灰/紅且清晰。

- [ ] **Step 6: Commit**

```bash
cd /home/timmy/code/news_analyze
git add frontend/src/components/BiasPage.tsx
git commit -m "feat(frontend): BiasPage 偏頗藍紅色隨主題切換"
```

---

### Task 4: TopicStats 圖表 per-theme

TopicStats（recharts）改接收 `theme` prop，依主題選圖表色盤、座標軸、tooltip、格線、折線色。App 傳入 `theme`。

**Files:**
- Modify: `frontend/src/components/TopicStats.tsx`
- Modify: `frontend/src/App.tsx:124`

**Interfaces:**
- Consumes: App 傳入的 `theme: 'light' | 'dark'`。
- Produces: `TopicStats` 元件簽名變更為 `TopicStats({ theme }: { theme: 'light' | 'dark' })`。

- [ ] **Step 1: 定義兩主題的圖表色盤**

在 `frontend/src/components/TopicStats.tsx` 把第 19–29 行（`const COLORS`、`const AXIS`、`const TOOLTIP` 三個模組常數）整段替換為：

```tsx
// Data-viz palettes per theme. Recharts/canvas need concrete color
// strings, so we pick by theme rather than via CSS vars.
interface VizPalette {
  colors: string[]
  axisFill: string
  axisStroke: string
  grid: string
  cursorStroke: string
  cursorFill: string
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
  line: string
}

const VIZ_DARK: VizPalette = {
  colors: ['#f0b429', '#d9822b', '#b5533a', '#6f9188', '#a89e88', '#f8d585'],
  axisFill: '#897f6b',
  axisStroke: '#342f24',
  grid: '#26221a',
  cursorStroke: '#342f24',
  cursorFill: 'rgba(240,180,41,0.06)',
  tooltipBg: '#1b1813',
  tooltipBorder: '#342f24',
  tooltipText: '#c9c0ad',
  line: '#f0b429',
}

const VIZ_LIGHT: VizPalette = {
  colors: ['#c77f0a', '#b5533a', '#4f7168', '#8a6d3b', '#9c5a2a', '#6e4a06'],
  axisFill: '#6b6250',
  axisStroke: '#d3cbb6',
  grid: '#e2dccb',
  cursorStroke: '#d3cbb6',
  cursorFill: 'rgba(183,134,11,0.10)',
  tooltipBg: '#ffffff',
  tooltipBorder: '#d3cbb6',
  tooltipText: '#141310',
  line: '#b7860b',
}
```

- [ ] **Step 2: 元件接收 `theme` 並在內部組出 AXIS/TOOLTIP/COLORS**

在同檔把：

```tsx
export default function TopicStats() {
  const [daily, setDaily] = useState<DailyCount[]>([])
  const [bySite, setBySite] = useState<SourceCount[]>([])
```

改為：

```tsx
export default function TopicStats({ theme }: { theme: 'light' | 'dark' }) {
  const viz = theme === 'dark' ? VIZ_DARK : VIZ_LIGHT
  const COLORS = viz.colors
  const AXIS = { fill: viz.axisFill, fontSize: 11, fontFamily: 'ui-monospace, monospace' }
  const TOOLTIP = {
    backgroundColor: viz.tooltipBg,
    border: `1px solid ${viz.tooltipBorder}`,
    color: viz.tooltipText,
    borderRadius: 2,
    fontFamily: 'ui-monospace, monospace',
    fontSize: 12,
  }
  const [daily, setDaily] = useState<DailyCount[]>([])
  const [bySite, setBySite] = useState<SourceCount[]>([])
```

- [ ] **Step 3: 替換 JSX 內寫死的圖表色**

在同檔的兩張圖表 JSX（約第 110–133 行），把下列硬編碼值改為 `viz.*`：

每日折線圖：

```tsx
            <CartesianGrid strokeDasharray="2 4" stroke={viz.grid} />
            <XAxis dataKey="publish_date" tick={AXIS} stroke={viz.axisStroke} />
            <YAxis tick={AXIS} stroke={viz.axisStroke} />
            <Tooltip contentStyle={TOOLTIP} cursor={{ stroke: viz.cursorStroke }} />
            <Line type="monotone" dataKey="count" stroke={viz.line} dot={false} strokeWidth={2} name="篇數" />
```

各來源長條圖：

```tsx
            <CartesianGrid strokeDasharray="2 4" stroke={viz.grid} />
            <XAxis dataKey="source_site" tick={AXIS} stroke={viz.axisStroke} />
            <YAxis tick={AXIS} stroke={viz.axisStroke} />
            <Tooltip contentStyle={TOOLTIP} cursor={{ fill: viz.cursorFill }} />
            <Bar dataKey="count" name="篇數" radius={[2, 2, 0, 0]}>
              {bySite.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
```

- [ ] **Step 4: App 傳入 `theme`**

在 `frontend/src/App.tsx` 第 124 行把：

```tsx
        {tab === 'stats' && <TopicStats />}
```

改為：

```tsx
        {tab === 'stats' && <TopicStats theme={theme} />}
```

- [ ] **Step 5: 型別/建置驗證**

Run: `cd frontend && npm run build && npm run lint`
Expected: 通過、無錯。

- [ ] **Step 6: 手動驗證**

Run: `cd frontend && npm run dev` → 「主題統計」分頁。
Expected：
1. 亮色下：折線與長條為較深暖色、清楚可見於紙底；座標軸文字深灰可讀；hover tooltip 為白底深字、邊框淺灰。
2. 切暗色：回到原本的 amber 折線、暖色長條、深色 tooltip。
3. 兩主題下格線/座標軸皆不刺眼、資料清晰。

- [ ] **Step 7: Commit**

```bash
cd /home/timmy/code/news_analyze
git add frontend/src/components/TopicStats.tsx frontend/src/App.tsx
git commit -m "feat(frontend): TopicStats 圖表色隨主題切換"
```

---

### Task 5: GraphPage 關聯圖譜 per-theme

GraphPage（react-force-graph-2d canvas）改接收 `theme` prop，依主題選節點色盤、畫布背景、連線與標籤色。App 傳入 `theme`。

**Files:**
- Modify: `frontend/src/components/GraphPage.tsx`
- Modify: `frontend/src/App.tsx:127`

**Interfaces:**
- Consumes: App 傳入的 `theme: 'light' | 'dark'`。
- Produces: `GraphPage` 元件簽名變更為 `GraphPage({ theme }: { theme: 'light' | 'dark' })`。

- [ ] **Step 1: 定義兩主題的圖譜色盤（模組層）**

在 `frontend/src/components/GraphPage.tsx` 把第 9 行：

```tsx
const PALETTE = ['#f0b429', '#d9822b', '#b5533a', '#6f9188', '#a89e88', '#f8d585', '#c19a3e', '#8f6f52']
```

替換為：

```tsx
interface GraphPalette {
  nodes: string[]
  bg: string
  focusStroke: string
  labelFocus: string
  labelDim: string
  linkBase: string
  linkActive: string
  linkDim: string
}

const GRAPH_DARK: GraphPalette = {
  nodes: ['#f0b429', '#d9822b', '#b5533a', '#6f9188', '#a89e88', '#f8d585', '#c19a3e', '#8f6f52'],
  bg: '#141310',
  focusStroke: '#f5c451',
  labelFocus: '#f5c451',
  labelDim: '#a89e88',
  linkBase: 'rgba(240,180,41,0.12)',
  linkActive: 'rgba(245,196,81,0.55)',
  linkDim: 'rgba(240,180,41,0.04)',
}

const GRAPH_LIGHT: GraphPalette = {
  nodes: ['#c77f0a', '#b5533a', '#4f7168', '#8a6d3b', '#9c5a2a', '#6e4a06', '#7a6a2e', '#5f4a38'],
  bg: '#f4efe3',
  focusStroke: '#b7860b',
  labelFocus: '#8a5e08',
  labelDim: '#6b6250',
  linkBase: 'rgba(183,134,11,0.16)',
  linkActive: 'rgba(138,94,8,0.55)',
  linkDim: 'rgba(183,134,11,0.05)',
}
```

- [ ] **Step 2: 元件接收 `theme` 並選色盤**

在同檔把：

```tsx
export default function GraphPage() {
```

改為：

```tsx
export default function GraphPage({ theme }: { theme: 'light' | 'dark' }) {
  const gviz = theme === 'dark' ? GRAPH_DARK : GRAPH_LIGHT
```

- [ ] **Step 3: 節點配色改用 `gviz.nodes`**

在同檔的來源→顏色映射（原第 66、70 行使用 `PALETTE`），改為 `gviz.nodes`。找到：

```tsx
      if (!(n.source_site in m)) m[n.source_site] = PALETTE[Object.keys(m).length % PALETTE.length]
```

改為：

```tsx
      if (!(n.source_site in m)) m[n.source_site] = gviz.nodes[Object.keys(m).length % gviz.nodes.length]
```

找到：

```tsx
  const colorForSource = useCallback((site: string) => sourceColorMap[site] ?? PALETTE[0], [sourceColorMap])
```

改為：

```tsx
  const colorForSource = useCallback((site: string) => sourceColorMap[site] ?? gviz.nodes[0], [sourceColorMap, gviz])
```

> 同時把 `sourceColorMap` 的 `useMemo` 依賴陣列補上 `gviz`（原本依賴 graph 資料）——切主題時節點需重新配色。找到建立 `sourceColorMap` 的 `useMemo(..., [deps])`，在其依賴陣列末端加入 `gviz`。

- [ ] **Step 4: drawNode 內的 focus/label 色改用 `gviz`**

在 `drawNode`（約第 128–158 行）把兩處寫死色替換：

```tsx
        ctx.strokeStyle = gviz.focusStroke
```

與

```tsx
        ctx.fillStyle = focused ? gviz.labelFocus : gviz.labelDim
```

並把 `drawNode` 的 `useCallback` 依賴陣列（原 `[activeId, isLit, colorForSource]`）改為：

```tsx
    [activeId, isLit, colorForSource, gviz],
```

- [ ] **Step 5: 連線色與畫布背景改用 `gviz`**

在 `<ForceGraph2D>` 的 `linkColor`（約第 218–221 行）把：

```tsx
                if (!activeId) return 'rgba(240,180,41,0.12)'
                return s === activeId || t === activeId ? 'rgba(245,196,81,0.55)' : 'rgba(240,180,41,0.04)'
```

改為：

```tsx
                if (!activeId) return gviz.linkBase
                return s === activeId || t === activeId ? gviz.linkActive : gviz.linkDim
```

把（約第 227 行）：

```tsx
              backgroundColor="#141310"
```

改為：

```tsx
              backgroundColor={gviz.bg}
```

- [ ] **Step 6: App 傳入 `theme`**

在 `frontend/src/App.tsx` 第 127 行把：

```tsx
        {tab === 'graph' && <GraphPage />}
```

改為：

```tsx
        {tab === 'graph' && <GraphPage theme={theme} />}
```

- [ ] **Step 7: 型別/建置驗證**

Run: `cd frontend && npm run build && npm run lint`
Expected: 通過、無錯（注意 `gviz` 已被列入相關 `useCallback`/`useMemo` 依賴，無 `react-hooks/exhaustive-deps` 警告）。

- [ ] **Step 8: 手動驗證**

Run: `cd frontend && npm run dev` → 「關聯圖譜」分頁，按「建立圖譜」。
Expected：
1. 亮色下：畫布背景為紙色（`#f4efe3`），節點為較深暖色、清楚可見；點選節點後 focus 外框與鄰居連線可見、標籤文字深色可讀。
2. 切暗色：畫布回黑底（`#141310`）、原 amber 系節點與亮色標籤。
3. 切主題後圖譜節點顏色即時更新（不需重建）。

- [ ] **Step 9: Commit**

```bash
cd /home/timmy/code/news_analyze
git add frontend/src/components/GraphPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): GraphPage 關聯圖譜色隨主題切換"
```

---

## Self-Review

**Spec coverage:**
- 亮色為預設 → Task 1（`@theme` 改亮色）+ Task 2（無值時預設亮色）。✅
- 可切換暗色 + 持久化 + 無閃爍 → Task 2。✅
- 色階反轉 + amber 文字對比修正 → Task 1（表格值 + blue-* 文字深古銅、`gray-950` 保持深墨供按鈕文字）。✅
- `.eyebrow` per-theme → Task 1 Step 3。✅
- 資料視覺化三處全部隨主題適配 → BiasPage（Task 3）、TopicStats（Task 4）、GraphPage（Task 5）。✅
- 切換鈕 UI（sun/moon，aria-label，focus ring）→ Task 2 Step 4（`p-1.5` 按鈕沿用全域 `:focus-visible` amber ring）。✅
- 非目標（不跟系統偏好、不加相依、不加測試框架）→ Global Constraints。✅

**Placeholder scan:** 無 TBD/TODO；每個改動皆附完整程式碼與確切檔案/行號。✅

**Type consistency:** `theme: 'light' | 'dark'` 在 App、TopicStats、GraphPage 一致；`useTheme(): { theme, toggle }` 與 App 解構一致；`VizPalette`/`GraphPalette` 欄位與 JSX 引用一致（`viz.grid`、`gviz.bg` 等）；bias CSS 變數名（`--bias-a-text` 等）在 Task 1 定義、Task 3 引用一致。✅

**Deviation note（TDD）:** 前端無 JS 測試框架，本計畫以 `npm run build`（型別）+ `npm run lint` + 明確瀏覽器手動檢查作為每 task 閘門，已於 Global Constraints 說明；不新增框架符合 YAGNI。
