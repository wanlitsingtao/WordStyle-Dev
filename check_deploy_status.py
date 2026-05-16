"""
检查Render部署状态和claim-free接口
"""
import requests
import time

print("="*70)
print("Render部署状态检查")
print("="*70)

# 1. 检查后端健康状态
print("\n1. 后端健康检查...")
try:
    r = requests.get('https://wstest-backend.onrender.com/health', timeout=10)
    print(f"   状态: {r.status_code}")
    if r.status_code == 200:
        print("   ✅ 后端服务正常运行")
    else:
        print(f"   ⚠️  后端返回异常状态码: {r.status_code}")
except Exception as e:
    print(f"   ❌ 后端无法访问: {e}")

# 2. 测试claim-free接口
print("\n2. 测试claim-free接口...")
try:
    # 使用一个测试用户ID
    test_user_id = "test_claim_free_check"
    r = requests.post(
        f'https://wstest-backend.onrender.com/api/users/{test_user_id}/claim-free',
        timeout=10
    )
    
    print(f"   状态码: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ 接口正常")
        print(f"   响应: {data}")
        
        if data.get('success'):
            print(f"   ✅ 成功领取 {data.get('paragraphs')} 个段落")
        elif '今日已领取' in data.get('message', ''):
            print(f"   ℹ️  今日已领取过（这是正常的）")
        else:
            print(f"   ⚠️  响应异常: {data}")
            
    elif r.status_code == 404:
        print(f"   ❌ 接口不存在（404）")
        print(f"   说明: Render尚未完成重新部署，或代码未更新")
        print(f"   建议: 等待2-3分钟后重试")
    else:
        print(f"   ⚠️   unexpected status: {r.status_code}")
        print(f"   响应: {r.text[:200]}")
        
except Exception as e:
    print(f"   ❌ 请求失败: {e}")

# 3. 检查Streamlit Cloud用户页面
print("\n3. 检查用户页面...")
try:
    r = requests.get('https://wstest-user.streamlit.app/', timeout=15)
    print(f"   状态: {r.status_code}")
    if r.status_code == 200:
        print("   ✅ 用户页面可访问")
        # 检查是否有temp_前缀的痕迹（这只是初步检查）
        if 'temp_' in r.text[:10000]:  # 只检查前10000字符
            print("   ⚠️  页面内容中发现temp_字样（可能需要进一步检查）")
        else:
            print("   ℹ️  页面内容正常（需手动访问确认用户ID）")
    else:
        print(f"   ⚠️  用户页面返回异常: {r.status_code}")
except Exception as e:
    print(f"   ❌ 用户页面无法访问: {e}")

print("\n" + "="*70)
print("下一步操作:")
print("1. 如果claim-free接口返回404，请等待Render重新部署（2-3分钟）")
print("2. 访问 https://wstest-user.streamlit.app/ 检查用户ID是否正常")
print("3. 查看Streamlit Cloud日志确认没有temp_前缀")
print("="*70)
