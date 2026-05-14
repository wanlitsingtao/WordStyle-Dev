"""
Supabase Storage 文件上传工具

提供文件上传、下载、删除等功能
"""
import os
from supabase import create_client, Client
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# 全局Supabase客户端（单例模式）
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    获取Supabase客户端（单例模式）
    
    Returns:
        Supabase客户端实例
    
    Raises:
        ValueError: 如果环境变量未配置
    """
    global _supabase_client
    
    if _supabase_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL 和 SUPABASE_KEY 必须在环境变量中配置\n"
                "请在 .env.production 文件中添加这两个变量"
            )
        
        _supabase_client = create_client(supabase_url, supabase_key)
        logger.info("Supabase客户端初始化成功")
    
    return _supabase_client


async def upload_file_to_supabase(
    file_path: str, 
    user_id: str, 
    bucket_name: str = "conversion-results"
) -> str:
    """
    上传文件到Supabase Storage
    
    Args:
        file_path: 本地文件路径
        user_id: 用户ID（用于组织文件目录）
        bucket_name: Storage Bucket名称
    
    Returns:
        文件的公开访问URL
    
    Raises:
        FileNotFoundError: 文件不存在
        Exception: 上传失败
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    client = get_supabase_client()
    
    # 生成存储路径（避免文件名冲突）
    filename = os.path.basename(file_path)
    import uuid
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    storage_path = f"{user_id}/{unique_filename}"
    
    try:
        # 读取文件内容
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        logger.info(f"开始上传文件: {filename} ({len(file_content)} bytes)")
        
        # 上传文件
        response = client.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_content,
            file_options={
                "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "cache-control": "3600",
                "upsert": "false"  # 不覆盖同名文件
            }
        )
        
        # 获取公开URL
        public_url = client.storage.from_(bucket_name).get_public_url(storage_path)
        
        logger.info(f"文件上传成功: {public_url}")
        return public_url
        
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise Exception(f"上传到Supabase失败: {str(e)}")


async def delete_file_from_supabase(
    storage_path: str, 
    bucket_name: str = "conversion-results"
) -> bool:
    """
    从Supabase Storage删除文件
    
    Args:
        storage_path: 存储路径（如：user_id/filename.docx）
        bucket_name: Storage Bucket名称
    
    Returns:
        是否删除成功
    """
    client = get_supabase_client()
    
    try:
        client.storage.from_(bucket_name).remove([storage_path])
        logger.info(f"文件删除成功: {storage_path}")
        return True
    except Exception as e:
        logger.error(f"文件删除失败: {e}")
        return False


async def list_user_files(
    user_id: str, 
    bucket_name: str = "conversion-results"
) -> List[str]:
    """
    列出用户的所有文件
    
    Args:
        user_id: 用户ID
        bucket_name: Storage Bucket名称
    
    Returns:
        文件路径列表
    """
    client = get_supabase_client()
    
    try:
        response = client.storage.from_(bucket_name).list(user_id)
        files = [f"{user_id}/{item['name']}" for item in response]
        return files
    except Exception as e:
        logger.error(f"列出文件失败: {e}")
        return []


async def get_file_url(
    storage_path: str, 
    bucket_name: str = "conversion-results",
    expires_in: int = 3600
) -> str:
    """
    获取文件的临时访问URL（带签名）
    
    Args:
        storage_path: 存储路径
        bucket_name: Storage Bucket名称
        expires_in: URL有效期（秒），默认1小时
    
    Returns:
        带签名的临时URL
    """
    client = get_supabase_client()
    
    try:
        url = client.storage.from_(bucket_name).create_signed_url(
            storage_path, 
            expires_in
        )
        return url
    except Exception as e:
        logger.error(f"生成签名URL失败: {e}")
        raise Exception(f"生成下载链接失败: {str(e)}")


# 测试代码
if __name__ == "__main__":
    import asyncio
    
    async def test_upload():
        """测试上传功能"""
        print("测试Supabase Storage工具...")
        
        # 创建一个测试文件
        test_file = "test_upload.docx"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("Test content")
        
        try:
            # 测试上传
            url = await upload_file_to_supabase(test_file, "test_user")
            print(f"✅ 上传成功: {url}")
            
            # 测试列出文件
            files = await list_user_files("test_user")
            print(f"✅ 文件列表: {files}")
            
            # 清理测试文件
            if files:
                await delete_file_from_supabase(files[0])
                print("✅ 清理完成")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
        finally:
            # 删除本地测试文件
            if os.path.exists(test_file):
                os.remove(test_file)
    
    # 运行测试
    asyncio.run(test_upload())
