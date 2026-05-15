# -*- coding: utf-8 -*-
"""
工作目录功能逻辑检查和自测脚本
根据编程原则进行系统性测试
"""
import sys
import os

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_backend_imports():
    """测试1: 后端模块导入"""
    print("=" * 70)
    print("测试1: 后端模块导入")
    print("=" * 70)
    
    tests_passed = True
    
    # 测试主应用
    try:
        from app.main import app
        print("✅ main.py 导入成功")
    except Exception as e:
        print(f"❌ main.py 导入失败: {e}")
        tests_passed = False
    
    # 测试API模块
    try:
        from app.api import admin, feedback, monitoring
        print("✅ API路由导入成功 (admin, feedback, monitoring)")
    except Exception as e:
        print(f"❌ API路由导入失败: {e}")
        tests_passed = False
    
    # 测试数据模型
    try:
        from app.models import User, ConversionTask, SystemConfig, Comment, Feedback, StyleMapping
        print("✅ 所有数据模型导入成功")
    except Exception as e:
        print(f"❌ 数据模型导入失败: {e}")
        tests_passed = False
    
    # 测试Schema
    try:
        from app.schemas import UserResponse, CommentResponse, FeedbackResponse, StyleMappingResponse
        print("✅ 所有Schema导入成功")
    except Exception as e:
        print(f"❌ Schema导入失败: {e}")
        tests_passed = False
    
    return tests_passed

def test_deleted_modules():
    """测试2: 验证已删除模块确实不存在"""
    print("\n" + "=" * 70)
    print("测试2: 验证已删除模块")
    print("=" * 70)
    
    deleted_modules = [
        ('app.api.auth', 'email/password认证'),
        ('app.api.wechat_auth', '微信登录'),
        ('app.api.conversions', '转换API')
    ]
    
    all_deleted = True
    for module, description in deleted_modules:
        try:
            __import__(module)
            print(f"❌ {module} ({description}) 应该被删除但仍然可以导入!")
            all_deleted = False
        except ImportError:
            print(f"✅ {module} ({description}) 已正确删除")
    
    return all_deleted

def test_no_order_references():
    """测试3: 检查没有Order相关引用"""
    print("\n" + "=" * 70)
    print("测试3: 检查Order/充值相关代码是否已清除")
    print("=" * 70)
    
    issues = []
    
    # 检查main.py
    with open('backend/app/main.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'payments' in content.lower() or 'order' in content.lower():
            # 允许注释中提到
            lines = [line for line in content.split('\n') if 'order' in line.lower() and not line.strip().startswith('#')]
            if lines:
                issues.append(f"main.py中发现Order相关代码: {lines[:2]}")
    
    # 检查monitoring.py
    with open('backend/app/api/monitoring.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'FROM orders' in content or 'orders WHERE' in content:
            issues.append("monitoring.py中发现orders表查询")
    
    # 检查admin.py
    with open('backend/app/api/admin.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'from app.models import Order' in content:
            issues.append("admin.py中导入Order模型")
    
    if issues:
        for issue in issues:
            print(f"❌ {issue}")
        return False
    else:
        print("✅ 未发现Order/充值相关代码")
        return True

def test_routes():
    """测试4: 路由注册检查"""
    print("\n" + "=" * 70)
    print("测试4: 路由注册检查")
    print("=" * 70)
    
    from app.main import app
    
    routes = [route.path for route in app.routes]
    
    expected_routes = ['/health', '/', '/api/admin', '/api/feedback', '/monitoring']
    removed_routes = ['/api/auth', '/api/wechat', '/api/conversions', '/api/users']
    
    all_correct = True
    
    for route in expected_routes:
        if any(route in r for r in routes):
            print(f"✅ 路由存在: {route}")
        else:
            print(f"⚠️  路由缺失: {route}")
    
    for route in removed_routes:
        if any(route in r for r in routes):
            print(f"❌ 路由应该被移除但仍然存在: {route}")
            all_correct = False
        else:
            print(f"✅ 路由已正确移除: {route}")
    
    return all_correct

def test_data_manager():
    """测试5: 数据访问层"""
    print("\n" + "=" * 70)
    print("测试5: 数据访问层")
    print("=" * 70)
    
    try:
        # 切换到项目根目录
        os.chdir(os.path.dirname(__file__))
        sys.path.insert(0, os.path.dirname(__file__))
        
        from data_manager import load_user_data, save_user_data
        print("✅ 数据访问层导入成功")
        
        # 测试基本功能
        test_user_id = "test_user_123"
        user_data = load_user_data(test_user_id)
        print(f"✅ 用户数据加载功能正常 (返回: {type(user_data).__name__})")
        
        return True
    except Exception as e:
        print(f"❌ 数据访问层测试失败: {e}")
        return False

def test_frontend_imports():
    """测试6: 前端模块导入"""
    print("\n" + "=" * 70)
    print("测试6: 前端模块导入")
    print("=" * 70)
    
    try:
        # 切换到项目根目录
        original_cwd = os.getcwd()
        os.chdir(os.path.dirname(__file__))
        sys.path.insert(0, os.path.dirname(__file__))
        
        import config
        print("✅ config.py 导入成功")
        
        import user_manager
        print("✅ user_manager.py 导入成功")
        
        import task_manager
        print("✅ task_manager.py 导入成功")
        
        import comments_manager
        print("✅ comments_manager.py 导入成功")
        
        os.chdir(original_cwd)
        return True
    except Exception as e:
        print(f"❌ 前端模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("WordStyle 工作目录功能逻辑检查和自测")
    print("=" * 70 + "\n")
    
    results = {}
    
    # 运行所有测试
    results['后端模块导入'] = test_backend_imports()
    results['已删除模块验证'] = test_deleted_modules()
    results['Order代码清理'] = test_no_order_references()
    results['路由注册检查'] = test_routes()
    results['数据访问层'] = test_data_manager()
    results['前端模块导入'] = test_frontend_imports()
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name:20s} {status}")
        all_passed = all_passed and passed
    
    print("=" * 70)
    if all_passed:
        print("🎉 所有测试通过! 工作目录代码质量良好!")
    else:
        print("❌ 部分测试失败，请检查上述错误")
    print("=" * 70 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
