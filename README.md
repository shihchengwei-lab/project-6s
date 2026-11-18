# project-6s

過期文件、重複產物和失效測試會讓接手者難以判斷該用哪個版本。用 `$project-6s` 讓 Codex 整理整個專案，也可以只整理文件、素材或測試。

盤點腳本列出版本變更、失效路徑、指向變更檔案的 Markdown 連結，以及內容相同的檔案。Codex 依用途判斷檔案去向，更新引用，在保留復原依據的情況下驗證，再永久移除舊檔。[技能說明](skills/project-6s/SKILL.md)

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

腳本固定本次的提交與 Git 暫存區，並核對掃描前後的檔案身分與修改時間。偵測到變動時，回傳 `unstable` 與結束碼 2，請在工作目錄穩定後重跑。符號連結、轉址及無法讀取的檔案會列在 `partial` 結果供補查。

採 [MIT 授權](LICENSE)。
