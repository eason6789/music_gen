import os

class Config:
    # MiniMax API 配置
    MINIMAX_API_KEY = os.getenv('MINIMAX_API_KEY', 'YOUR_MINIMAX_API_KEY')
    MINIMAX_API_BASE = 'https://api.minimax.io/v1'

    # 腾讯云COS配置
    COS_SECRET_ID = os.getenv('COS_SECRET_ID', 'YOUR_COS_SECRET_ID')
    COS_SECRET_KEY = os.getenv('COS_SECRET_KEY', 'YOUR_COS_SECRET_KEY')
    COS_REGION = os.getenv('COS_REGION', 'ap-guangzhou')
    COS_BUCKET = os.getenv('COS_BUCKET', 'musicgen-1-413453247')
    COS_BASE_URL = f'https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com'

    # 上传目录
    UPLOAD_FOLDER = '/tmp/music_gen'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max