# project-6s

可重用的 Codex 專案整理技能，支援程式庫、素材、文件與測試的 6S。

採 [MIT 授權](LICENSE)。

核心原則：**現行文件只留最新有效狀態；確認無用的產物刪除，確有保存用途才封存，封存移出日常搜尋與模型讀取範圍。**

技能內容及完成條件見 [SKILL.md](skills/project-6s/SKILL.md)。測試整理的專用準則由主檔按需載入，不附批次刪檔腳本。

## 安裝

取得本儲存庫後，把 `skills/project-6s/` 複製到 Codex 的個人技能目錄。預設是 `~/.codex/skills/`；若有設定 `CODEX_HOME`，使用該目錄下的 `skills/`。

PowerShell（首次安裝）：

```powershell
gh repo clone shihchengwei-lab/project-6s
cd project-6s
$skillHome = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
New-Item -ItemType Directory -Path $skillHome -Force | Out-Null
Copy-Item -LiteralPath './skills/project-6s' -Destination $skillHome -Recurse
```

更新已安裝版本前，先確認沒有本機自訂變更，再替換技能目錄；來源以本儲存庫為準。

## 使用

```text
$project-6s 對目前專案做徹底的 6S，文件對齊已發布現況。
$project-6s 只整理測試，保留必要行為契約，刪除重複及假通過案例。
$project-6s 整理素材，必要原稿歸位；指定要保存的資料移到工作區外封存。
```

技能可正常自動選用；不依賴其他插件。6S 不自動 commit、push 或部署，也不保證瀏覽器／實機行為已驗收。需要這些動作時另行指定。
