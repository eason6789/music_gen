import os
import uuid
import sys
import re
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import base64
from config import Config
import cos_client

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)


@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')


MINIMAX_API_KEY = Config.MINIMAX_API_KEY
MINIMAX_MUSIC_URL = 'https://api.minimaxi.com/v1/music_generation'
MINIMAX_LYRICS_URL = 'https://api.minimaxi.com/v1/lyrics_generation'
MINIMAX_COVER_PREPROCESS_URL = 'https://api.minimaxi.com/v1/music_cover_preprocess'


def _sanitize_filename(name):
    """清理文件名，移除非法字符"""
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = name.strip().replace(' ', '_')
    return name[:50] if name else 'music'


def _save_to_cos(audio_url):
    """下载 MiniMax OSS 音频并上传到 COS, 返回 COS URL"""
    try:
        print(f'[_save_to_cos] Downloading from: {audio_url[:80]}...', file=sys.stderr)
        cos_url, cos_key = cos_client.download_to_cos(audio_url)
        print(f'[_save_to_cos] Uploaded to COS: {cos_url[:80]}', file=sys.stderr)
        return cos_url
    except Exception as e:
        print(f'[_save_to_cos] FAILED: {e}', file=sys.stderr)
        return None


def _generate_lyrics(prompt, title=None):
    """调用 MiniMax 歌词生成 API"""
    lyrics_payload = {
        'mode': 'write_full_song',
        'prompt': prompt
    }
    if title:
        lyrics_payload['title'] = title

    resp = requests.post(
        MINIMAX_LYRICS_URL,
        headers={'Authorization': f'Bearer {MINIMAX_API_KEY}', 'Content-Type': 'application/json'},
        json=lyrics_payload,
        timeout=60,
        proxies={'http': None, 'https': None}
    )
    result = resp.json()

    if 'base_resp' in result and result['base_resp'].get('status_code') != 0:
        raise Exception(f"歌词生成失败: {result['base_resp'].get('status_msg', '未知错误')}")

    return {
        'song_title': result.get('song_title', ''),
        'style_tags': result.get('style_tags', ''),
        'lyrics': result.get('lyrics', '')
    }


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'music-gen-api'})


@app.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '请上传音频文件'}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({'error': '文件名为空'}), 400

        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size == 0:
            return jsonify({'error': '文件为空'}), 400
        if file_size > 50 * 1024 * 1024:
            return jsonify({'error': '文件大小不能超过 50MB'}), 400

        audio_bytes = file.read()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        try:
            cos_url, cos_key = cos_client.upload_bytes(
                audio_bytes, prefix='uploads',
                content_type=file.content_type or 'audio/mpeg'
            )
        except Exception as e:
            return jsonify({'error': f'文件上传失败: {str(e)}'}), 500

        return jsonify({
            'success': True,
            'audio_base64': audio_b64,
            'cos_url': cos_url,
            'cos_key': cos_key,
            'file_size': file_size
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate', methods=['POST'])
def generate_music():
    try:
        if request.is_json:
            data = request.get_json()
        elif request.form:
            data = {k: v for k, v in request.form.items()}
            if 'file' in request.files:
                f = request.files['file']
                if f and f.filename:
                    f.seek(0, os.SEEK_END)
                    file_size = f.tell()
                    f.seek(0)
                    if file_size > 50 * 1024 * 1024:
                        return jsonify({'error': '文件大小不能超过 50MB'}), 400
                    audio_bytes = f.read()
                    data['audio_base64'] = base64.b64encode(audio_bytes).decode('utf-8')
        else:
            return jsonify({'error': '不支持的请求格式'}), 400

        mode = data.get('mode')
        headers = {
            'Authorization': f'Bearer {MINIMAX_API_KEY}',
            'Content-Type': 'application/json'
        }

        song_title = None
        generated_lyrics = None

        if mode == 'description':
            description = data.get('description', '')
            if not description:
                return jsonify({'error': '请输入描述'}), 400
            if len(description) > 500:
                description = description[:500]

            # Step 1: 调用歌词生成 API
            try:
                lyrics_result = _generate_lyrics(description)
                song_title = lyrics_result['song_title']
                style_tags = lyrics_result['style_tags']
                generated_lyrics = lyrics_result['lyrics']
                print(f'[generate] Lyrics API: title={song_title}, tags={style_tags}', file=sys.stderr)
            except Exception as e:
                print(f'[generate] Lyrics generation failed, falling back: {e}', file=sys.stderr)
                song_title = None
                style_tags = description
                generated_lyrics = None

            # Step 2: 音乐生成
            prompt = style_tags if style_tags else description
            payload = {
                'model': 'music-2.6',
                'prompt': prompt,
                'is_instrumental': False,
                'output_format': 'url',
                'audio_setting': {
                    'sample_rate': 44100,
                    'bitrate': 256000,
                    'format': 'mp3'
                }
            }
            if generated_lyrics:
                payload['lyrics'] = generated_lyrics
            else:
                payload['lyrics'] = '♪\n'

        elif mode == 'lyrics':
            song_name = data.get('song_name', '')
            lyrics = data.get('lyrics', '')
            if not lyrics:
                return jsonify({'error': '歌词是必填的'}), 400

            song_title = song_name if song_name else None
            generated_lyrics = lyrics

            prompt = song_name if song_name else ''
            payload = {
                'model': 'music-2.6',
                'prompt': prompt,
                'lyrics': lyrics,
                'is_instrumental': False,
                'output_format': 'url',
                'audio_setting': {
                    'sample_rate': 44100,
                    'bitrate': 256000,
                    'format': 'mp3'
                }
            }

        elif mode == 'cover':
            audio_base64 = data.get('audio_base64', '')
            prompt = data.get('prompt', '')
            lyrics = data.get('lyrics')

            if not audio_base64:
                return jsonify({'error': '请上传原曲音频'}), 400
            if not prompt:
                return jsonify({'error': '请输入目标翻唱风格描述'}), 400

            song_title = _sanitize_filename(prompt)

            preprocess_payload = {
                'model': 'music-cover',
                'audio_base64': audio_base64
            }

            preprocess_resp = requests.post(
                MINIMAX_COVER_PREPROCESS_URL,
                headers=headers,
                json=preprocess_payload,
                timeout=120,
                proxies={'http': None, 'https': None}
            )

            preprocess_result = preprocess_resp.json()
            if 'base_resp' in preprocess_result and preprocess_result['base_resp'].get('status_code') != 0:
                return jsonify({
                    'error': f'音频预处理失败: {preprocess_result["base_resp"].get("status_msg", "未知错误")}'
                }), 400

            cover_feature_id = preprocess_result.get('cover_feature_id')
            audio_duration = preprocess_result.get('audio_duration')
            formatted_lyrics = preprocess_result.get('formatted_lyrics', '')

            if not generated_lyrics:
                generated_lyrics = formatted_lyrics if formatted_lyrics else None

            payload = {
                'model': 'music-cover',
                'prompt': prompt,
                'cover_feature_id': cover_feature_id,
                'audio_duration': audio_duration,
                'output_format': 'url',
                'audio_setting': {
                    'sample_rate': 44100,
                    'bitrate': 256000,
                    'format': 'mp3'
                }
            }

            if lyrics:
                payload['lyrics'] = lyrics
                generated_lyrics = lyrics
            elif formatted_lyrics:
                payload['lyrics'] = formatted_lyrics

            # 保存原曲到 COS
            try:
                audio_bytes = base64.b64decode(audio_base64)
                cos_client.upload_bytes(audio_bytes, prefix='covers/original')
            except Exception as e:
                print(f'Failed to archive original audio to COS: {e}')

        else:
            return jsonify({'error': '无效的mode，请使用 description、lyrics 或 cover'}), 400

        # 调用 MiniMax 音乐生成 API
        response = requests.post(
            MINIMAX_MUSIC_URL,
            headers=headers,
            json=payload,
            timeout=180,
            proxies={'http': None, 'https': None}
        )

        result = response.json()

        if 'base_resp' in result and result['base_resp'].get('status_code') != 0:
            return jsonify({
                'error': f'MiniMax API错误: {result["base_resp"].get("status_msg", "未知错误")}'
            }), 400

        if response.status_code != 200:
            return jsonify({
                'error': f'MiniMax API错误: {result.get("base_resp", {}).get("status_msg", "未知错误")}'
            }), response.status_code

        music_data = result.get('data', {})
        gen_status = music_data.get('status')

        if gen_status == 2:
            audio_url = music_data.get('audio')
            print(f'[generate] MiniMax returned audio_url: {audio_url[:80] if audio_url else "EMPTY"}...', file=sys.stderr)
            cos_url = _save_to_cos(audio_url)

            resp_data = {
                'success': True,
                'audio_url': cos_url or audio_url,
                'extra_info': result.get('extra_info', {})
            }

            # 附加歌词和歌名
            if generated_lyrics:
                resp_data['lyrics'] = generated_lyrics
            if song_title:
                resp_data['song_title'] = song_title

            return jsonify(resp_data)
        elif gen_status == 1:
            return jsonify({
                'success': True,
                'status': 'processing',
                'trace_id': result.get('trace_id'),
                'message': '音乐正在生成中，请稍后查询'
            })
        else:
            return jsonify({'error': f'未知状态: {gen_status}'}), 500

    except requests.Timeout:
        return jsonify({'error': '请求超时，请稍后重试'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=False)
