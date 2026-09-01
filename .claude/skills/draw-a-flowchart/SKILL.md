---
name: draw-a-flowchart
description: 'Use when the user asks to draw, add, update or re-render a flowchart / diagram / 流程圖 for a repo, or when a doc change makes an existing diagram stale. Renders mermaid to a committed PNG with mermaid-cli driving the Google Chrome already in /Applications. 用 mermaid 畫流程圖，來源存成 img/imgNNN.png.mermaidchart.txt，圖檔輸出 img/imgNNN.png，兩個檔一起 commit。'
---

# draw-a-flowchart

畫流程圖的固定做法。**mermaid 原始碼是 source of truth，PNG 是產物**，兩個都進 git，
永遠同一個 commit。不要只改其中一個。

## 檔案慣例

```
img/img3.png.mermaidchart.txt   <- mermaid 原始碼，手改的就是這個
img/img3.png                    <- 從上面 render 出來，不要手動編輯
```

- 檔名就是 `<png 檔名>.mermaidchart.txt`。編號從 1 開始往上加：先 `ls img/` 看
  現有最大的號碼，新圖用下一個號。**不要重用舊號碼**，舊圖留著（README 會說明
  哪張是舊版）。
- 在 README.md 用 `![說明文字](img/img3.png)` 引用。
- 更新既有的圖 → 改同一組檔名，號碼不變。

## Render 的方法

mermaid-cli 裝在**這個 session 的 scratchpad**（不是全域、不是專案裡），
用系統上已經有的 Google Chrome，不要讓 puppeteer 另外下載 Chromium
（下載很慢，而且 scratchpad 每個 session 會清掉，裝全域反而髒）。

`PUPPETEER_SKIP_DOWNLOAD=true` 必須在 `npm install` **之前** export，事後補沒有用。

```bash
SP=<系統提示裡的 scratchpad 路徑>
mkdir -p $SP && cd $SP
export PUPPETEER_SKIP_DOWNLOAD=true
npm init -y >/dev/null 2>&1
npm install @mermaid-js/mermaid-cli 2>&1 | tail -3
npx --no-install mmdc --version
```

兩個設定檔，寫在 scratchpad：

```bash
cat > $SP/pptr.json <<'EOF'
{ "executablePath": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "args": ["--no-sandbox","--disable-setuid-sandbox"] }
EOF

cat > $SP/mermaid-cfg.json <<'EOF'
{ "theme": "base",
  "themeVariables": { "background": "#eef2ff", "primaryColor": "#ececff",
    "primaryBorderColor": "#9370db", "primaryTextColor": "#000000",
    "lineColor": "#333333", "clusterBkg": "#ffffff", "clusterBorder": "#cccccc",
    "fontFamily": "trebuchet ms, verdana, arial, sans-serif", "fontSize": "16px" },
  "flowchart": { "htmlLabels": true, "useMaxWidth": false, "curve": "basis", "wrappingWidth": 500 } }
EOF
```

這組 themeVariables 是刻意調成跟 mermaidchart.com 網站預設看起來一樣的
（早期的 img1.png 是直接在網站上截圖存下來的，後來的圖要跟它同一個風格）。

Render：

```bash
cp img/img3.png.mermaidchart.txt $SP/in3.mmd
cd $SP && npx --no-install mmdc -i in3.mmd -o out3.png \
  -p pptr.json -c mermaid-cfg.json -b '#eef2ff' -s 1 -w 1800 2>&1 | tail -5
```

- `-w` 是畫布寬度，不是最後尺寸；圖會自己縮到需要的大小。橫向三四個節點用
  `1800`，很寬的 pipeline 用 `2266`。
- `-s 1` 就夠了。`-s 2` 出來的檔案大一倍但 README 上看不出差別。
- `-b '#eef2ff'` 是背景色，要跟 `themeVariables.background` 一致。

滿意之後才蓋回 repo：

```bash
cp $SP/out3.png img/img3.png
```

## 一定要用眼睛看過

**render 完要用 Read tool 把 PNG 讀出來看**。mmdc 不會因為版面難看而報錯——
文字爆出框、節點疊在一起、subgraph 被撐得很長，它都會安靜地產生一張醜圖。
沒看過就交出去等於沒做。

看的時候檢查：

- 標籤有沒有在奇怪的地方換行（`wrappingWidth` 調大或自己插 `<br/>`）
- subgraph 有沒有被某個節點撐得很不成比例
- 箭頭方向對不對，跟文字說明一致嗎

不滿意就改 `.txt` 再 render 一次。這是正常流程，通常要跑兩三輪。

## Mermaid 寫法上的坑

- **用 `<br/>` 換行，不要用 `\n`。** `htmlLabels: true` 之下 `\n` 不會斷行。
- **`>` 要寫成 `&gt;`**，否則會被當成箭頭語法解析。`<` 同理用 `&lt;`。
- Windows 路徑裡的反斜線（`C:\Users\...`）在節點文字裡是安全的，不用跳脫。
- `&nbsp;` 用來在 subgraph 標題裡塞空白，例如 `subgraph nas["DS918 &nbsp; 192.168.123.163"]`。
- 節點裡可以放圖示：`N1["<img src='https://i.imgur.com/ecRBtpN.png'/>"]`。
  imgur 上已經有一組在用的圖示，**畫新圖時先看現有的 .mermaidchart.txt 沿用同一批
  URL**，不要每張圖找不同的圖示。
- **附註方塊（警告、說明）放在 subgraph 外面當獨立節點**，不要塞進 subgraph 裡。
  塞進去會把那個 subgraph 撐得很長，而且讀起來會變成「只跟這一個 subgraph 有關」。
  獨立節點會排在圖的下方，剛好是附註該在的位置。用 `style` 上色：

  ```
  WARN["<b>標題</b> <br/> 說明文字"]
  style WARN fill:#fff3cd,stroke:#e0a800,color:#000
  ```

- 實線粗箭頭 `==>` 用在主要流程，虛線 `-.->` 用在次要 / 不屬於本專案的部分。
  箭頭上的標籤用 `|"..."|`，裡面可以有 `<br/>` 和 `<b>`。

## 收尾

- `.mermaidchart.txt` 和 `.png` 一起 `git add`，同一個 commit。
- commit message 說明**圖為什麼改**（哪個事實變了），不是只寫「更新圖片」。
- scratchpad 裡的 `node_modules/` 不要進 repo（本來就在 scratchpad，不會被 git 看到）。
- 如果這次只是文件變了但圖還是對的，就明講「圖不用改」，不要為了有產出而重畫。

## 前置檢查

Chrome 不在 `/Applications/Google Chrome.app` 的話，先找找 Chromium 或 Edge，
把 `pptr.json` 的 `executablePath` 換掉；都沒有才退回讓 puppeteer 自己下載
（`npm install` 時不要 export `PUPPETEER_SKIP_DOWNLOAD`）。
