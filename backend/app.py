import os
import uuid
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import base64
from config import Config

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# 本地开发时从 / 提供前端页面
@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

# MiniMax API 配置
MINIMAX_API_KEY = Config.MINIMAX_API_KEY
MINIMAX_API_URL = 'https://api.minimaxi.com/v1/music_generation'
MINIMAX_COVER_PREPROCESS_URL = 'https://api.minimaxi.com/v1/music_cover_preprocess'


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': 'music-gen-api'})


@app.route('/api/generate', methods=['POST'])
def generate_music():
    """
    生成音乐
    请求体:
    - mode: "description" | "lyrics" | "cover"
    - description: string (mode=description时)
    - prompt_length: "500" | "1000" (mode=description时)
    - song_name: string (mode=lyrics时, 可选)
    - lyrics: string (mode=lyrics时, 必填)
    - audio_base64: string (mode=cover时, 必填)
    - prompt: string (mode=cover时, 必填)
    """
    try:
        data = request.get_json()
        mode = data.get('mode')

        headers = {
            'Authorization': f'Bearer {MINIMAX_API_KEY}',
            'Content-Type': 'application/json'
        }

        if mode == 'description':
            # 描述模式: 根据用户描述生成纯音乐/背景音乐
            description = data.get('description', '')

            if not description:
                return jsonify({'error': '请输入描述'}), 400

            if len(description) > 500:
                description = description[:500]

            payload = {
                'model': 'music-2.6',
                'prompt': description,
                'is_instrumental': False,
                'lyrics': '♪\n',
                'output_format': 'url',
                'audio_setting': {
                    'sample_rate': 44100,
                    'bitrate': 256000,
                    'format': 'mp3'
                }
            }

        elif mode == 'lyrics':
            # 模式2: 歌词生成
            song_name = data.get('song_name', '')
            lyrics = data.get('lyrics', '')

            if not lyrics:
                return jsonify({'error': '歌词是必填的'}), 400

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
            # 模式3: AI翻唱 — 两步流程: 先预处理, 再生成
            audio_base64 = data.get('audio_base64', '')
            prompt = data.get('prompt', '')
            lyrics = data.get('lyrics')

            if not audio_base64:
                return jsonify({'error': '请上传原曲音频'}), 400

            if not prompt:
                return jsonify({'error': '请输入目标翻唱风格描述'}), 400

            # 第一步: 音频预处理
            preprocess_payload = {
                'model': 'music-cover',
                'audio_base64': audio_base64
            }

            preprocess_resp = requests.post(
                MINIMAX_COVER_PREPROCESS_URL,
                headers=headers,
                json=preprocess_payload,
                timeout=30,
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

            # 第二步: 翻唱生成
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

            # 使用用户提供的歌词，否则使用自动提取的歌词
            if lyrics:
                payload['lyrics'] = lyrics
            elif formatted_lyrics:
                payload['lyrics'] = formatted_lyrics

        else:
            return jsonify({'error': '无效的mode，请使用 description、lyrics 或 cover'}), 400

        # 调用MiniMax API
        response = requests.post(
            MINIMAX_API_URL,
            headers=headers,
            json=payload,
            timeout=90,  # 音乐生成通常 25-60 秒,90s 足够
            proxies={'http': None, 'https': None}  # 绕过系统代理,避免proxy连接错误
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

        # 检查返回的状态
        music_data = result.get('data', {})
        status = music_data.get('status')

        if status == 2:
            # 生成完成，返回音频URL
            audio_url = music_data.get('audio')
            return jsonify({
                'success': True,
                'audio_url': audio_url,
                'extra_info': result.get('extra_info', {})
            })
        elif status == 1:
            # 生成中
            trace_id = result.get('trace_id')
            return jsonify({
                'success': True,
                'status': 'processing',
                'trace_id': trace_id,
                'message': '音乐正在生成中，请稍后查询'
            })
        else:
            return jsonify({'error': f'未知状态: {status}'}), 500

    except requests.Timeout:
        return jsonify({'error': '请求超时，请稍后重试'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=False)