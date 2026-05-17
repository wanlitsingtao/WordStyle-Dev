# =====================================================
# WordStyle 代码同步脚本
# 用途: 将工作目录(WSprj)的代码同步到发布目录(WordStyle)
# 原则: 目录级同步 + 完整性验证
# =====================================================

param(
    [string]$SourceDir = "E:\LingMa\WSprj",
    [string]$TargetDir = "E:\LingMa\WordStyle"
)

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "WordStyle 代码同步工具" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# 检查源目录和目标目录是否存在
if (-not (Test-Path $SourceDir)) {
    Write-Host "❌ 错误: 源目录不存在: $SourceDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $TargetDir)) {
    Write-Host "❌ 错误: 目标目录不存在: $TargetDir" -ForegroundColor Red
    exit 1
}

Write-Host "源目录: $SourceDir" -ForegroundColor Green
Write-Host "目标目录: $TargetDir" -ForegroundColor Green
Write-Host ""

# =====================================================
# 步骤1: 撤销发布目录的未提交修改
# =====================================================
Write-Host "[1/6] 撤销发布目录的未提交修改..." -ForegroundColor Yellow
Set-Location $TargetDir

git restore . 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ 已撤销未提交的修改" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Git restore失败，继续执行" -ForegroundColor Yellow
}

# 删除临时文件
Remove-Item -Path "*_temp*", "*.log", "__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  ✅ 已清理临时文件" -ForegroundColor Green
Write-Host ""

# =====================================================
# 步骤2: 同步根目录Python文件
# =====================================================
Write-Host "[2/6] 同步根目录Python文件..." -ForegroundColor Yellow
Copy-Item -Path "$SourceDir\*.py" -Destination $TargetDir -Exclude "_*" -Force
Write-Host "  ✅ 根目录文件已同步" -ForegroundColor Green
Write-Host ""

# =====================================================
# 步骤3: 同步后端代码（整个app目录）
# =====================================================
Write-Host "[3/6] 同步后端代码..." -ForegroundColor Yellow
Copy-Item -Path "$SourceDir\backend\app\*" -Destination "$TargetDir\backend\app\" -Recurse -Force
Write-Host "  ✅ 后端代码已同步" -ForegroundColor Green
Write-Host ""

# =====================================================
# 步骤4: 同步Alembic迁移脚本（最关键！）
# =====================================================
Write-Host "[4/6] 同步Alembic迁移脚本..." -ForegroundColor Cyan
Copy-Item -Path "$SourceDir\backend\alembic\*" -Destination "$TargetDir\backend\alembic\" -Recurse -Force
Write-Host "  ✅ Alembic迁移脚本已同步" -ForegroundColor Green
Write-Host ""

# =====================================================
# 步骤5: 同步数据库脚本和配置文件
# =====================================================
Write-Host "[5/6] 同步数据库脚本和配置..." -ForegroundColor Yellow

# 数据库脚本
if (Test-Path "$SourceDir\dbscript") {
    Copy-Item -Path "$SourceDir\dbscript\*" -Destination "$TargetDir\dbscript\" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ 数据库脚本已同步" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  dbscript目录不存在，跳过" -ForegroundColor Yellow
}

# 配置文件
if (Test-Path "$SourceDir\.streamlit") {
    Copy-Item -Path "$SourceDir\.streamlit\*" -Destination "$TargetDir\.streamlit\" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ Streamlit配置已同步" -ForegroundColor Green
}

Write-Host ""

# =====================================================
# 步骤6: 验证同步结果
# =====================================================
Write-Host "[6/6] 验证同步结果..." -ForegroundColor Cyan
Write-Host ""

$ErrorCount = 0

# 6.1 验证Alembic迁移脚本数量
$source_versions = (Get-ChildItem "$SourceDir\backend\alembic\versions\*.py" -ErrorAction SilentlyContinue).Count
$target_versions = (Get-ChildItem "$TargetDir\backend\alembic\versions\*.py" -ErrorAction SilentlyContinue).Count

Write-Host "  检查Alembic迁移脚本:" -ForegroundColor White
Write-Host "    源目录: $source_versions 个文件" -ForegroundColor Gray
Write-Host "    目标目录: $target_versions 个文件" -ForegroundColor Gray

if ($source_versions -ne $target_versions) {
    Write-Host "    ❌ 迁移脚本数量不一致！" -ForegroundColor Red
    $ErrorCount++
} else {
    Write-Host "    ✅ 迁移脚本数量一致" -ForegroundColor Green
}
Write-Host ""

# 6.2 验证API模块数量
$source_api = (Get-ChildItem "$SourceDir\backend\app\api\*.py" -ErrorAction SilentlyContinue).Count
$target_api = (Get-ChildItem "$TargetDir\backend\app\api\*.py" -ErrorAction SilentlyContinue).Count

Write-Host "  检查API模块:" -ForegroundColor White
Write-Host "    源目录: $source_api 个文件" -ForegroundColor Gray
Write-Host "    目标目录: $target_api 个文件" -ForegroundColor Gray

if ($source_api -ne $target_api) {
    Write-Host "    ❌ API模块数量不一致！" -ForegroundColor Red
    $ErrorCount++
} else {
    Write-Host "    ✅ API模块数量一致" -ForegroundColor Green
}
Write-Host ""

# 6.3 验证关键文件哈希值
$key_files = @("backend/app/main.py", "backend/app/models.py", "data_manager.py", "app.py")

Write-Host "  检查关键文件完整性:" -ForegroundColor White
foreach ($file in $key_files) {
    $source_path = Join-Path $SourceDir $file
    $target_path = Join-Path $TargetDir $file
    
    if (Test-Path $source_path -and Test-Path $target_path) {
        $source_hash = (Get-FileHash $source_path -Algorithm MD5).Hash
        $target_hash = (Get-FileHash $target_path -Algorithm MD5).Hash
        
        if ($source_hash -eq $target_hash) {
            Write-Host "    ✅ $file" -ForegroundColor Green
        } else {
            Write-Host "    ❌ $file (内容不一致)" -ForegroundColor Red
            $ErrorCount++
        }
    } else {
        Write-Host "    ⚠️  $file (文件缺失)" -ForegroundColor Yellow
        $ErrorCount++
    }
}
Write-Host ""

# =====================================================
# 总结
# =====================================================
Write-Host "=" * 80 -ForegroundColor Cyan

if ($ErrorCount -eq 0) {
    Write-Host "✅ 同步完成！所有验证通过" -ForegroundColor Green
    Write-Host ""
    Write-Host "下一步操作:" -ForegroundColor Yellow
    Write-Host "  1. 在发布目录检查Git状态: git status" -ForegroundColor White
    Write-Host "  2. 提交更改: git add -A; git commit -m '同步工作目录代码'" -ForegroundColor White
    Write-Host "  3. 推送到GitHub: git push origin main" -ForegroundColor White
    Write-Host "  4. Render会自动重新部署" -ForegroundColor White
} else {
    Write-Host "❌ 同步完成，但发现 $ErrorCount 个问题" -ForegroundColor Red
    Write-Host ""
    Write-Host "请检查上述错误并手动修复" -ForegroundColor Yellow
    exit 1
}

Write-Host "=" * 80 -ForegroundColor Cyan
