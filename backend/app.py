import os
import uuid
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import tempfile
from config import Config

app = Flask(__name__)
CORS(app)

# MiniMax API 配置
MINIMAX_API_KEY = Config.MINIMAX_API_KEY
MINIMAX_API_URL = 'https://api.minimaxi.com/v1/music_generation'


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': 'music-gen-api'})


@app.route('/api/generate', methods=['POST'])
def generate_music():
    """
    生成音乐
    请求体:
    - mode: "description" | "lyrics"
    - description: string (mode=description时)
    - prompt_length: "500" | "1000" (mode=description时)
    - song_name: string (mode=lyrics时, 可选)
    - lyrics: string (mode=lyrics时, 必填)
    """
    try:
        data = request.get_json()
        mode = data.get('mode')

        if mode == 'description':
            # 模式1: 纯描述生成
            description = data.get('description', '')
            prompt_length = data.get('prompt_length', '500')

            if not description:
                return jsonify({'error': '请输入描述'}), 400

            # 限制描述长度
            max_len = int(prompt_length)
            if len(description) > max_len:
                description = description[:max_len]

            payload = {
                'model': 'music-2.6-free',
                'prompt': description,
                'is_instrumental': True,
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
                'model': 'music-2.6-free',
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
        else:
            return jsonify({'error': '无效的mode，请使用 description 或 lyrics'}), 400

        # 调用MiniMax API
        headers = {
            'Authorization': f'Bearer {MINIMAX_API_KEY}',
            'Content-Type': 'application/json'
        }

        response = requests.post(
            MINIMAX_API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        result = response.json()

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
            # 生成中，需要轮询
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


@app.route('/api/query/<trace_id>', methods=['GET'])
def query_music(trace_id):
    """查询音乐生成状态"""
    try:
        headers = {
            'Authorization': f'Bearer {MINIMAX_API_KEY}',
            'Content-Type': 'application/json'
        }

        # MiniMax的查询接口需要调用status接口
        # 这里简化处理，实际应该轮询
        return jsonify({
            'success': True,
            'trace_id': trace_id,
            'message': '请稍后刷新页面查看结果'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=False)