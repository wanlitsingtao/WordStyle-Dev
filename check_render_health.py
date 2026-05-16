# -*- coding: utf-8 -*-
"""
Render 服务健康检查脚本

用途：验证Render部署的三个服务是否正常运行
"""
import requests
import json
from datetime import datetime

# 服务地址配置
SERVICES = {
    "后端API": "https://wstest-backend.onrender.com",
    "用户页面": "https://wsprj.onrender.com",
    "管理后台": "https://wsprj-admin.onrender.com"
}

def check_health(service_name, base_url):
    """检查服务健康状态"""
    print(f"\n{'='*60}")
    print(f"检查服务: {service_name}")
    print(f"URL: {base_url}")
    print(f"{'='*60}")
    
    try:
        # 1. 健康检查
        health_url = f"{base_url}/health"
        print(f"\n[1/3] 健康检查: {health_url}")
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            print(f"[OK] 状态码: {response.status_code}")
            print(f"[OK] 响应: {response.json()}")
        else:
            print(f"[FAIL] 状态码: {response.status_code}")
            print(f"[FAIL] 响应: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"[FAIL] 请求超时（>10秒）")
        return False
    except requests.exceptions.ConnectionError:
        print(f"[FAIL] 连接失败（服务可能未启动或地址错误）")
        return False
    except Exception as e:
        print(f"[FAIL] 错误: {str(e)}")
        return False
    
    try:
        # 2. API文档检查（仅后端）
        if service_name == "后端API":
            print(f"\n[2/3] API文档: {base_url}/docs")
            response = requests.get(f"{base_url}/docs", timeout=10)
            
            if response.status_code == 200:
                print(f"[OK] Swagger UI可访问")
            else:
                print(f"[WARN] API文档返回状态码: {response.status_code}")
        
        # 3. 测试claim-free接口（仅后端）
        if service_name == "后端API":
            print(f"\n[3/3] 测试免费额度接口")
            test_user_id = "test-health-check-user"
            claim_url = f"{base_url}/api/admin/users/{test_user_id}/claim-free"
            response = requests.post(claim_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] 接口调用成功")
                print(f"   响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                # 检查是否包含expected字段
                if 'paragraphs' in data:
                    print(f"[OK] 返回包含paragraphs字段: {data['paragraphs']}")
                else:
                    print(f"[WARN] 响应缺少paragraphs字段")
            else:
                print(f"[FAIL] 接口调用失败，状态码: {response.status_code}")
                print(f"   响应: {response.text[:200]}")
                
    except Exception as e:
        print(f"[WARN] 额外检查失败: {str(e)}")
    
    return True

def check_frontend_data_source(service_name, base_url):
    """检查前端数据源配置（需要手动访问浏览器）"""
    print(f"\n💡 提示: 请在浏览器中访问 {base_url}")
    print(f"   检查页面顶部是否显示: '数据源: API (https://wstest-backend.onrender.com)'")
    print(f"   如果显示 '数据源: local'，说明环境变量配置有问题")

def main():
    """主函数"""
    print("="*60)
    print("Render 服务健康检查")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {}
    
    # 检查所有服务
    for service_name, base_url in SERVICES.items():
        success = check_health(service_name, base_url)
        results[service_name] = success
        
        # 前端服务需要额外检查
        if service_name != "后端API":
            check_frontend_data_source(service_name, base_url)
    
    # 总结
    print(f"\n{'='*60}")
    print("检查结果总结")
    print(f"{'='*60}")
    
    all_success = True
    for service_name, success in results.items():
        status = "[OK] 正常" if success else "[FAIL] 异常"
        print(f"{service_name}: {status}")
        if not success:
            all_success = False
    
    print(f"\n{'='*60}")
    if all_success:
        print("[OK] 所有服务运行正常！")
    else:
        print("[FAIL] 部分服务异常，请检查Render Logs")
    print(f"{'='*60}")
    
    # 提供故障排查建议
    if not all_success:
        print("\n🔧 故障排查建议:")
        print("1. 登录 Render Dashboard: https://dashboard.render.com/")
        print("2. 选择对应的服务")
        print("3. 点击 'Logs' 标签查看错误信息")
        print("4. 检查 'Environment' 标签确认环境变量配置")
        print("5. 参考文档: docs/Render环境变量配置检查清单.md")

if __name__ == "__main__":
    main()
