# Render服务健康检查脚本 (PowerShell版本)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Render 服务健康检查" -ForegroundColor Cyan
Write-Host "检查时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$services = @{
    "后端API" = "https://wstest-backend.onrender.com"
    "用户页面" = "https://wsprj.onrender.com"
    "管理后台" = "https://wsprj-admin.onrender.com"
}

$results = @{}

foreach ($serviceName in $services.Keys) {
    $baseUrl = $services[$serviceName]
    
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "检查服务: $serviceName" -ForegroundColor Yellow
    Write-Host "URL: $baseUrl" -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host ""
    
    try {
        # 健康检查
        $healthUrl = "$baseUrl/health"
        Write-Host "[1/2] 健康检查: $healthUrl" -ForegroundColor White
        
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        
        if ($response.StatusCode -eq 200) {
            Write-Host "[OK] 状态码: $($response.StatusCode)" -ForegroundColor Green
            Write-Host "[OK] 响应: $($response.Content)" -ForegroundColor Green
            $results[$serviceName] = $true
        } else {
            Write-Host "[FAIL] 状态码: $($response.StatusCode)" -ForegroundColor Red
            Write-Host "[FAIL] 响应: $($response.Content.Substring(0, [Math]::Min(200, $response.Content.Length)))" -ForegroundColor Red
            $results[$serviceName] = $false
        }
        
    } catch {
        Write-Host "[FAIL] 请求失败: $($_.Exception.Message)" -ForegroundColor Red
        $results[$serviceName] = $false
    }
    
    Write-Host ""
}

# 总结
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "检查结果总结" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$allSuccess = $true
foreach ($serviceName in $results.Keys) {
    if ($results[$serviceName]) {
        Write-Host "$serviceName : [OK] 正常" -ForegroundColor Green
    } else {
        Write-Host "$serviceName : [FAIL] 异常" -ForegroundColor Red
        $allSuccess = $false
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan

if ($allSuccess) {
    Write-Host "[OK] 所有服务运行正常！" -ForegroundColor Green
} else {
    Write-Host "[FAIL] 部分服务异常，请检查Render Logs" -ForegroundColor Red
    Write-Host ""
    Write-Host "故障排查建议:" -ForegroundColor Yellow
    Write-Host "1. 登录 Render Dashboard: https://dashboard.render.com/" -ForegroundColor White
    Write-Host "2. 选择对应的服务" -ForegroundColor White
    Write-Host "3. 点击 'Logs' 标签查看错误信息" -ForegroundColor White
    Write-Host "4. 检查 'Environment' 标签确认环境变量配置" -ForegroundColor White
    Write-Host "5. 参考文档: docs/Render环境变量配置检查清单.md" -ForegroundColor White
}

Write-Host "============================================================" -ForegroundColor Cyan
