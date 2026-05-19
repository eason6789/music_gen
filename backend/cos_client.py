import os
import uuid
import requests
from qcloud_cos import CosConfig, CosS3Client
from config import Config


_config = CosConfig(
    Region=Config.COS_REGION,
    SecretId=Config.COS_SECRET_ID,
    SecretKey=Config.COS_SECRET_KEY,
    Scheme='https'
)
_client = CosS3Client(_config)


def _generate_key(prefix='music', ext='mp3'):
    return f'music_gen/{prefix}/{uuid.uuid4().hex}.{ext}'


def upload_bytes(data, key=None, prefix='music', content_type='audio/mpeg'):
    """上传字节数据到 COS, 返回 (cos_url, key)"""
    if key is None:
        key = _generate_key(prefix)
    _client.put_object(
        Bucket=Config.COS_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
        ACL='public-read'
    )
    url = f'{Config.COS_BASE_URL}/{key}'
    return url, key


def upload_file(local_path, key=None, prefix='music'):
    """上传本地文件到 COS"""
    if key is None:
        key = _generate_key(prefix)
    _client.upload_file(
        Bucket=Config.COS_BUCKET,
        Key=key,
        LocalFilePath=local_path,
        ACL='public-read'
    )
    url = f'{Config.COS_BASE_URL}/{key}'
    return url, key


def download_to_cos(source_url, prefix='music', ext='mp3'):
    """从外部 URL 下载文件并上传到 COS, 返回 COS URL"""
    resp = requests.get(source_url, timeout=120, proxies={'http': None, 'https': None})
    resp.raise_for_status()
    key = _generate_key(prefix, ext)
    _client.put_object(
        Bucket=Config.COS_BUCKET,
        Key=key,
        Body=resp.content,
        ContentType='audio/mpeg',
        ACL='public-read'
    )
    return f'{Config.COS_BASE_URL}/{key}', key


def get_object_url(key):
    return f'{Config.COS_BASE_URL}/{key}'
