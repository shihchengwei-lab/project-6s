# project-6s · Codex 專案整理技能

用 `$project-6s` 整理 Codex 工作區。盤點失效的 Markdown 連結與重複檔案，更新過期文件，並檢查測試是否仍守住必要行為。可以整理整個儲存庫，也可以只處理文件、素材或測試。

A Codex skill for repository cleanup, documentation updates, and test review. Its read-only Python script finds broken Markdown links and duplicate files.

清理舊檔時，Codex 先在隔離副本驗證，再由能控制目標寫入的一方套用。無法控制寫入時，將已驗證的變更與批次紀錄交給維護者。需要封存的資料，確認封存可用後才移除原件。[清理與復原流程](skills/project-6s/SKILL.md#處理舊副本與產物)

文件對齊是 6S 的一部分。整理整個專案時，Codex 從 README 查到安裝、使用、維護與設計說明，對照文件應描述的版本，修正已過期的內容。只整理特定區域時，也會核對受影響的文件。

## 安裝

取得本儲存庫後，把 `skills/project-6s/` 複製到 Codex 的個人技能目錄。預設是 `~/.codex/skills/`；若有設定 `CODEX_HOME`，使用該目錄下的 `skills/`。

已安裝 GitHub CLI 時，可在 PowerShell 執行以下首次安裝指令。

```powershell
gh repo clone shihchengwei-lab/project-6s
cd project-6s
$skillHome = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
New-Item -ItemType Directory -Path $skillHome -Force | Out-Null
Copy-Item -LiteralPath './skills/project-6s' -Destination $skillHome -Recurse
```

更新時，用本儲存庫的版本替換已安裝的技能目錄。有本機自訂內容時，先確認要保留的改動。

## 使用

```text
$project-6s 整理目前專案，讓文件對齊已發布版本。
$project-6s 只整理測試，合併重複案例，修正程式出錯時仍會通過的測試。
$project-6s 整理素材，將正式原稿歸位，並把指定資料移到工作區外封存。
```

### 單獨執行盤點

腳本需要 Python 3.11 以上，以及至少有一筆提交的 Git 儲存庫。從本儲存庫根目錄執行。省略 `--base` 時以 `HEAD`（目前提交）為比較基準，也可指定其他提交、標籤或分支。

Markdown 連結檢查另外需要 [markdown-it-py](skills/project-6s/scripts/requirements.txt)。在同一個 Python 環境執行 `python -m pip install -r ./skills/project-6s/scripts/requirements.txt`。尚未安裝時，盤點會標記連結未檢查，仍可列出 Git 變更和重複檔案。

```powershell
python ./skills/project-6s/scripts/inventory.py . --base HEAD
```

腳本以 JSON 輸出檔案、適用的行號和依據。變更分開列出已提交、已加入下次提交、尚未加入的修改，以及 Git 未忽略的新檔。連結檢查從 CommonMark 的連結與圖片節點取出相對路徑，核對目標是否存在。行號指出節點所在的文字區塊開頭。

比較基準只用來列出變更。即使變更清單為空，腳本仍會檢查現有的追蹤檔案與未被忽略的新檔，找出失效連結與同內容檔案。可直接從現況開始整理。沒有 Git 或尚未建立首次提交時，可直接使用技能手動盤點。

輸出的 `report_type` 固定為 `observations`。腳本直接向 Git 查詢變更，各筆結果反映各自的讀取時點。略過的路徑、無法讀取的檔案及偵測到讀取期間變動的檔案，會列入結果供逐項補查。結束碼 0 表示已輸出盤點，清理定案由執行者另行驗證。

### 找到重複檔案後怎麼處理？

在本儲存庫執行盤點，腳本會列出兩份內容相同的 MIT 授權。根目錄的授權適用於儲存庫，技能目錄內的授權會隨技能一起安裝，因此兩份都保留。[儲存庫授權](LICENSE) · [隨技能安裝的授權](skills/project-6s/LICENSE)

### 建立與驗證清理批次

批次工具需要 Git 和 Python 3.11 以上。它以固定 Git 提交的完整樹為原狀，預設使用準備當下的 `HEAD`，也可用 `--revision` 選擇版本。準備與驗證都會核對原儲存庫的根目錄。用專案相對路徑列出要新增、修改或移除的檔案，再編輯輸出的 `candidate`。未提交的工作目錄改動留在原處。

```powershell
$batch = python ./skills/project-6s/scripts/batch.py prepare . "$env:TEMP/project-6s-batches" README.md | ConvertFrom-Json
# 在 $batch.candidate 內，將 README.md 的標題改為「project-6s · Codex 6S」
python ./skills/project-6s/scripts/batch.py verify $batch.batch --contains README.md "project-6s · Codex 6S"
```

每個有變動的檔案至少要指定一項內建檢查。`--exists` 核對檔案存在，`--absent` 核對路徑不存在，`--contains` 核對文字。發布前，工具會自動核對新增或修改的 `.md` 檔。若有檔案或目錄消失，也會掃描未改動的 `.md` 檔，確認原先可用的相對連結仍可用。用 `--links` 可要求完整核對其他指定的 `.md` 檔，包括原有斷連結。

連結檢查需要上節的 Markdown 解析器。工具依 CommonMark 取得連結與圖片，先化簡 URL 路徑中的 `.` 和 `..`，再按專案內的精確路徑核對目標。路徑以 `/` 結尾，或最後一段為 `.` 或 `..` 時，目標須為目錄。原始 HTML、外部網址、以 `/` 開頭的路徑、查詢字串與錨點均在範圍外。必查文件無法解析、相對網址無法對應到單一專案內路徑，或必要目標不存在時，驗證會停止。

批次保留實際檔名。需要檔案與目錄互換、只改名稱大小寫，或涉及名稱衝突、無法跨平台表示的檔名、符號連結、空目錄或自訂驗證命令時，使用技能的人工隔離流程。

驗證開始時會顯示執行 ID。結果放在批次的 `runs/<執行 ID>/`，檢查全數通過才會發布該次的 `handoff/`，其中有 `manifest.json`、原狀檔案 `before/` 和候選檔案 `after/`。清單以 `null` 表示原本缺席或預計移除。執行 Markdown 檢查時，清單也會記錄解析器版本、檢查過的文件、連結網址及實際核對的專案路徑。未改動文件只列原先可用且仍可用的連結。中斷後只核對該次執行目錄。目錄中尚無交接包時，可用原候選重跑，取得新的執行 ID。維護者依選定交接包套用與復原。[清理與復原流程](skills/project-6s/SKILL.md#處理舊副本與產物)

採 [MIT 授權](LICENSE)。
