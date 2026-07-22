# 開燈模式（Light Theme）設計

**Date:** 2026-07-21
**Scope:** Frontend (`frontend/`) — add a light theme, make it the default, keep the existing dark "Signal Monitor" theme available via a toggle.

## Goal

前端新增亮色主題，**預設為亮色**，保留原本的暗色 Signal Monitor 主題，header 提供切換鈕，使用者選擇記在 `localStorage`。

## Core insight

整個 UI 的配色是靠在 `frontend/src/index.css` 的 `@theme` 區塊重新映射 Tailwind 色階達成的。在 Tailwind v4 中，`bg-gray-900` 會編譯成 `background-color: var(--color-gray-900)`。因此**只要在不同的主題 scope 底下重新定義這些 CSS 變數，所有用 utility class 的元件就會自動換色，不需要改任何元件**。這涵蓋約 95% 的 UI。

被否決的替代方案：把每個元件改寫成 `dark:` 前綴。那是數百處編輯，且與現有架構相衝突。不採用。

## Mechanism

1. `@theme` 區塊改放**亮色**調色盤（因為亮色是預設）。
2. 新增一段一般 CSS：`[data-theme="dark"] { ... }` 重新宣告目前的暗色色階；只有屬性存在時暗色才生效。
3. 切換鈕設定 `document.documentElement.dataset.theme` 並寫入 `localStorage`；沒有存值 → 亮色。
4. `index.html <head>` 內嵌一小段 script，在畫面繪製前套用已存的 `dark`，避免閃爍（FOUC）。

```html
<!-- index.html <head>, before the module script -->
<script>
  try { if (localStorage.getItem('theme') === 'dark') document.documentElement.dataset.theme = 'dark'; } catch (e) {}
</script>
```

## Light ramp（反轉 graphite 色階，保留暖調）

元件把 `gray-900` 當作底色、`gray-50` 當作標題，因此色階需反轉——暖紙底色、暖深墨字：

| token | dark（現況） | light（新增） | 用途 |
|---|---|---|---|
| gray-950 | #0c0b08 | #faf6ec | 最深/最淺背景 |
| gray-900 | #141310 | **#f4efe3** | app 底色（paper） |
| gray-800 | #1b1813 | #ece6d8 | panel surface |
| gray-700 | #26221a | #e2dccb | inputs / pills / hairline |
| gray-600 | #342f24 | #d3cbb6 | borders / list rails |
| gray-500 | #6b6250 | #8a8069 | muted dividers / IDs |
| gray-400 | #a89e88 | #6b6250 | secondary / meta |
| gray-300 | #c9c0ad | **#3a352b** | primary body text（AA on paper） |
| gray-200 | #ddd5c6 | #2a261e | |
| gray-100 | #ece6d8 | #1e1b15 | |
| gray-50  | #f4efe3 | **#141310** | headings（ink） |

## Accessibility — amber link 問題

亮色的 amber（`#f5c451`）當**文字**放在紙底上嚴重不符 WCAG。因此亮色模式下把 amber 依角色拆開：

- **裝飾用** amber（live-dot、focus ring、按鈕填色、邊框）→ 維持亮 `#e0a020`。
- **文字用** amber（連結、關鍵數字，即 `blue-400 / blue-300` token）→ 深古銅 `#8a5e08` / `#6e4a06`，AA ≥ 4.5:1。

亮色模式的 `blue-*`（amber remap）建議值：

| token | light 值 | 角色 |
|---|---|---|
| blue-700 | #6e4a06 | deep |
| blue-600 | #b7860b | 按鈕填色（深字） |
| blue-500 | #b7860b | signal / focus ring |
| blue-400 | #8a5e08 | 連結 / active / 關鍵數字 |
| blue-300 | #6e4a06 | 連結 hover |

`.eyebrow` 目前寫死 `#9a9078`，需 per-theme：亮色改深一階（例如 `#6b6250`），暗色維持 `#9a9078`（用 `[data-theme="dark"] .eyebrow` 覆寫）。

## 資料視覺化 theme-awareness（三處寫死顏色，選擇：全部隨主題適配）

新增一個小的 `useTheme()` hook 讓 JS 取得目前主題（讀同一個 `data-theme` 狀態）。主題切換時元件 re-render、force-graph 透過 prop 更新。

- **TopicStats**（recharts，`frontend/src/components/TopicStats.tsx`）
  - 亮色 `COLORS` ramp：改用較深/較飽和的暖色，避免淺 amber（`#f8d585`）在白底上看不見。
  - `TOOLTIP`：亮色改 `backgroundColor: #ffffff`、`border: 1px solid #d3cbb6`、深色文字。
  - `AXIS.fill`：亮色改深一階（`#6b6250`）。
- **GraphPage**（react-force-graph-2d canvas，`frontend/src/components/GraphPage.tsx`）
  - `backgroundColor` → 亮色 `#f4efe3`（原 `#141310`）。
  - 亮色 node `PALETTE`：較深暖色集。
  - link `rgba(...)` 高亮/淡出值依主題調整。
  - node label 文字色 per theme。
- **BiasPage**（`frontend/src/components/BiasPage.tsx`）
  - 保留 `#3b82f6` / `#e5484d` 填色（白底可讀）。
  - 換掉為暗底調亮的文字色：`#6ea8fe` → `#1d4ed8`、`#f16a6e` → `#dc2626`、neutral 文字 → `#6b6250`。

## Toggle UI

Header 狀態列放一個 sun/moon 圖示按鈕（`FiSun` / `FiMoon`，react-icons 已安裝）。需 `aria-label`；可鍵盤聚焦（沿用全域 focus ring）。狀態源自 App 層 `theme` state，初值與 `index.html` 的 script 讀同一個 `localStorage.theme`。

## 元件影響清單

| 檔案 | 變更 |
|---|---|
| `frontend/index.html` | 新增 no-FOUC inline script |
| `frontend/src/index.css` | `@theme` 改亮色；新增 `[data-theme="dark"]` 暗色覆寫；`.eyebrow` per-theme |
| `frontend/src/App.tsx`（或新 `useTheme` 模組） | `useTheme()` hook：state + localStorage + 設定 `data-theme`；header 切換鈕 |
| `frontend/src/components/TopicStats.tsx` | per-theme 圖表色 / tooltip / axis |
| `frontend/src/components/GraphPage.tsx` | per-theme canvas 背景 / node palette / link / label |
| `frontend/src/components/BiasPage.tsx` | per-theme 偏頗文字色 |

`useTheme` 放哪：因為 App 與三個 viz 元件都要用，最省的作法是一個小 hook（讀 `data-theme` + 訂閱變更），各元件自行呼叫；不需要 Context provider（YAGNI）。

## Verification

- `cd frontend && npm run build`（tsc + vite）需通過。
- 手動抽查關鍵對比配對（body text、連結、eyebrow、bias 文字）在紙底達 AA。
- 切換後重新整理：選擇保留、無閃爍。
- 三處 viz 在亮/暗下都不破版（force-graph 背景、圖表 tooltip、偏頗藍紅文字）。

## 非目標（YAGNI）

- 不跟隨系統 `prefers-color-scheme`（使用者明確要求預設亮色）。
- 不做第三種主題或自訂配色。
- 不改後端 / 資料層。
