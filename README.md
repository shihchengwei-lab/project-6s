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

```powershell
python ./skills/project-6s/scripts/inventory.py . --base HEAD
```

腳本以 JSON 輸出檔案、適用的行號和依據。變更分開列出已提交、已加入下次提交、尚未加入的修改，以及 Git 未忽略的新檔。連結檢查涵蓋常見 Markdown 相對路徑，核對目的檔案是否存在。

比較基準只用來列出變更。即使變更清單為空，腳本仍會檢查現有的追蹤檔案與未被忽略的新檔，找出失效連結與同內容檔案。可直接從現況開始整理。沒有 Git 或尚未建立首次提交時，可直接使用技能手動盤點。

輸出的 `report_type` 固定為 `observations`。腳本直接向 Git 查詢變更，各筆結果反映各自的讀取時點。略過的路徑、無法讀取的檔案及偵測到讀取期間變動的檔案，會列入結果供逐項補查。結束碼 0 表示已輸出盤點，清理定案由執行者另行驗證。

### 找到重複檔案後怎麼處理？

在本儲存庫執行盤點，腳本會列出兩份內容相同的 MIT 授權。根目錄的授權適用於儲存庫，技能目錄內的授權會隨技能一起安裝，因此兩份都保留。[儲存庫授權](LICENSE) · [隨技能安裝的授權](skills/project-6s/LICENSE)

採 [MIT 授權](LICENSE)。
