# -*- coding: utf-8 -*-
"""
快速测试后端 API - 使用 SQLite 数据库
无需安装 PostgreSQL，适合快速开发和测试
"""
import uvicorn
from app.main import app

if __name__ == "__main__":
    print("=" * 60)
    print("  WordStyle Pro Backend - 开发模式")
    print("=" * 60)
    print()
    print("📖 API 文档: http://localhost:8000/docs")
    print("🔍 ReDoc:    http://localhost:8000/redoc")
    print()
    print("⚠️  注意: 当前使用 SQLite 数据库（仅用于测试）")
    print("   生产环境请使用 PostgreSQL")
    print()
    print("按 Ctrl+C 停止服务器")
    print()
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
