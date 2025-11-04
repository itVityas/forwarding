import requests
import base64
import json
import os

from flask import Flask, request, Response, jsonify
from dotenv import load_dotenv


app = Flask(__name__)


def add_authentication(headers):
    """Добавляет аутентификацию к заголовкам"""
    load_dotenv()
    username = os.getenv('USERNAME')
    password = os.getenv('PASSWORD')
    print(username, password)
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers['Authorization'] = f'Basic {credentials}'
    return headers


def get_target_config(request_data):
    """Извлекает конфигурацию целевого сервера из JSON"""
    try:
        if request_data:
            data = json.loads(request_data.decode())

            # Получаем целевой URL из JSON
            target_url = data.get('target_url')
            if not target_url:
                return None, "Missing 'target_url' in JSON data"

            method = data.get('method', 'GET').upper()

            # Получаем данные для проксирования
            proxy_data = data.get('data', {})
            proxy_headers = data.get('headers', {})

            return {
                'target_url': target_url,
                'method': method,
                'proxy_data': proxy_data,
                'proxy_headers': proxy_headers
            }, None

    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return None, f"Error parsing request: {str(e)}"

    return None, "Invalid request data"


@app.route('/proxy', methods=['POST'])
def proxy():
    """
    Проксирует запрос на целевой URL из JSON
    Пример JSON тела запроса:
    {
        "target_url": "https://api.target.com/endpoint",
        "auth": {
            "username": "user",
            "password": "pass"
        },
        "headers": {
            "Content-Type": "application/json",
            "X-Custom-Header": "value"
        },
        "data": {
            "key": "value",
            "another_key": "another_value"
        }
    }
    """
    # Получаем конфигурацию из JSON
    config, error = get_target_config(request.get_data())
    if error:
        return jsonify({'error': error}), 400

    method = config['method']
    target_url = config['target_url']
    proxy_data = config['proxy_data']
    proxy_headers = config['proxy_headers']

    # Базовые заголовки
    headers = {key: value for key, value in request.headers if key.lower() not in ['host', 'content-length']}

    # Добавляем кастомные заголовки из JSON
    headers.update(proxy_headers)

    # Добавляем аутентификацию
    headers = add_authentication(headers)

    try:
        # Отправляем запрос к целевому серверу
        response = requests.request(
            method=method,
            url=target_url,
            headers=headers,
            json=proxy_data,  # Отправляем как JSON
            params=request.args,
            allow_redirects=False,
            timeout=30
        )

        # Формируем ответ
        response_data = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'data': response.json() if response.content else None
        }

        return jsonify(response_data), response.status_code

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Target server timeout'}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot connect to target server'}), 502
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Request error: {str(e)}'}), 500
    except json.JSONDecodeError:
        # Если ответ не JSON, возвращаем как текст
        return Response(response.content, status=response.status_code, headers=dict(response.headers))


@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья прокси"""
    return jsonify({'status': 'healthy', 'service': 'http_proxy'})


if __name__ == '__main__':
    # import uvicorn
    # uvicorn.run(app, host='0.0.0.0', port=5000)
    app.run(host='0.0.0.0', port=5000, debug=True)
