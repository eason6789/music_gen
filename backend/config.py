import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # MiniMax API 配置
    MINIMAX_API_KEY = os.getenv('MINIMAX_API_KEY')
    if not MINIMAX_API_KEY:
        raise RuntimeError("MINIMAX_API_KEY environment variable is required")
    MINIMAX_API_BASE = 'https://api.minimax.io/v1'

    # 腾讯云COS配置
    COS_SECRET_ID = os.getenv('COS_SECRET_ID')
    COS_SECRET_KEY = os.getenv('COS_SECRET_KEY')
    if not COS_SECRET_ID or not COS_SECRET_KEY:
        raise RuntimeError("COS_SECRET_ID and COS_SECRET_KEY environment variables are required")
    COS_REGION = os.getenv('COS_REGION', 'ap-guangzhou')
    COS_BUCKET = os.getenv('COS_BUCKET', 'single-az-1251416377')
    COS_BASE_URL = f'https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com'

    # 上传目录
    UPLOAD_FOLDER = '/tmp/music_gen'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max