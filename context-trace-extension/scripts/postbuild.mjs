// post-build：把 manifest.json 拷到 dist，合并 content.css，
// 把 popup/sidepanel html 移到 dist 根，并把引用路径里的 /assets 改成 assets/
// 生成占位 icons（用 1x1 PNG）

import { copyFileSync, mkdirSync, existsSync, writeFileSync, readFileSync, readdirSync, renameSync, rmSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')
const dist = resolve(root, 'dist')

if (!existsSync(dist)) {
  console.error('dist 目录不存在，请先跑 vite build')
  process.exit(1)
}

// 1. 移动 popup/sidepanel html 到 dist 根，并改写引用路径
function moveHtml(src, dst) {
  if (!existsSync(src)) return
  let html = readFileSync(src, 'utf-8')
  // /assets/foo.js → assets/foo.js
  html = html.replace(/(src|href)="\/(assets\/[^"]+)"/g, '$1="$2"')
  writeFileSync(dst, html)
  console.log(`✓ ${src} -> ${dst}`)
}

moveHtml(resolve(dist, 'src/popup/index.html'), resolve(dist, 'popup.html'))
moveHtml(resolve(dist, 'src/sidepanel/index.html'), resolve(dist, 'sidepanel.html'))

// 清理掉 src/ 目录
const srcDir = resolve(dist, 'src')
if (existsSync(srcDir)) {
  rmSync(srcDir, { recursive: true, force: true })
}

// 2. 复制 manifest.json
copyFileSync(resolve(root, 'manifest.json'), resolve(dist, 'manifest.json'))

// 3. 合并 content.css
const assets = readdirSync(resolve(dist, 'assets')).filter((f) => f.endsWith('.css'))
const contentCss = assets.find((f) => /popup|sidepanel|content|floater/.test(f)) || assets[0]
// 注意：content/index.ts 没 import css，所以这里 popup 的 css 是 content 浮窗的来源
// 实际上浮窗 css 在 src/content/floater.css，需要在 content/index.ts 中 import
// 检查 content.js 是否包含 css 字符串
const contentJs = readFileSync(resolve(dist, 'content.js'), 'utf-8')
// 实际上：Vite 在 build 时不会把不在 .ts 入口的 css 抽出来；我们让 content/index.ts 导入 css
// 找到 content/index.ts 引用的 css
// 简单做法：直接用 floater.css 内容生成 content.css
const floaterCss = readFileSync(resolve(root, 'src/content/floater.css'), 'utf-8')
writeFileSync(resolve(dist, 'content.css'), floaterCss)
console.log('✓ 生成 content.css (from src/content/floater.css)')

// 4. 生成占位 icons
const iconsDir = resolve(dist, 'icons')
mkdirSync(iconsDir, { recursive: true })
const tinyPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==',
  'base64'
)
;[16, 32, 48, 128].forEach((sz) => {
  writeFileSync(resolve(iconsDir, `icon${sz}.png`), tinyPng)
})
console.log('✓ 生成占位 icons (16/32/48/128)')

console.log('\n📦 dist/ 已就绪，加载方式：')
console.log('   打开 chrome://extensions/  →  打开「开发者模式」  →  「加载已解压的扩展程序」  →  选择 dist 目录')
