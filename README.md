# project-6s

過期文件、重複產物和失效測試會讓接手者難以判斷該用哪個版本。用 `$project-6s` 讓 Codex 整理整個專案，也可以只整理文件、素材或測試。

Codex 先把正式來源歸位，找出哪些文件沿用這次變更的內容，更新後再處理舊檔。最後逐份核對文件與所選版本是否一致，並照文件跑一次受影響的操作。刪除、封存與驗證的做法見 [技能說明](skills/project-6s/SKILL.md)。

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

採 [MIT 授權](LICENSE)。
