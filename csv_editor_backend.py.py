import os
import requests
import base64
from io import StringIO
import csv
from flask import Flask, render_template, request, jsonify

# --- НАСТРОЙКИ ---
REPO_OWNER = "He11born" # Замените на ваш логин
REPO_NAME = "changing_data_for_misis_bot" # Замените на имя репозитория
FILE_PATH = "разраб.csv"
CSV_DELIMITER = ';' # Используем точку с запятой, как в вашем файле
ID_COLUMN = 'ID номер' # Столбец для поиска записи
VALUE_COLUMN = 'Количество пропусков' # Столбец для изменения значения

# Получение токена из переменной окружения (обязательно для Render)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("!!! ВНИМАНИЕ: Переменная GITHUB_TOKEN не установлена. Используйте Render Environment Variables. !!!")

GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
# -----------------

app = Flask(__name__)
# ... (далее код функций)
# ... (начало файла app.py) ...

def get_csv_content():
    """Получает содержимое файла с GitHub и его SHA."""
    try:
        response = requests.get(GITHUB_API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        encoded_content = data['content']
        decoded_content = base64.b64decode(encoded_content).decode('utf-8')
        return decoded_content, data['sha']
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении файла: {e}")
        return None, None


def update_csv_file(new_content, current_sha, commit_message):
    """Обновляет файл на GitHub."""
    encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')

    payload = {
        "message": commit_message,
        "content": encoded_content,
        "sha": current_sha
    }

    try:
        response = requests.put(GITHUB_API_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        return True, f"Файл успешно обновлен. Коммит: {response.json()['commit']['sha'][:7]}"
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при записи файла: {e}")
        return False, f"Ошибка при записи файла: {e.response.text if e.response is not None else str(e)}"


# ... (после update_csv_file) ...

@app.route('/')
def index():
    """Главная страница: отображает форму и текущие данные."""
    csv_string, sha = get_csv_content()

    if not csv_string:
        return "Не удалось загрузить данные с GitHub. Проверьте токен/путь к файлу.", 500

    # Используем точку с запятой в качестве разделителя!
    data_reader = csv.DictReader(StringIO(csv_string), delimiter=CSV_DELIMITER)
    data_list = list(data_reader)

    # Передаем заголовки и данные во frontend
    return render_template('index.html',
                           data=data_list,
                           id_col=ID_COLUMN,
                           value_col=VALUE_COLUMN)


@app.route('/update', methods=['POST'])
def update_data():
    """Обработка POST-запроса на изменение данных."""
    data_to_update = request.get_json()
    record_id = data_to_update.get('id')
    new_value = data_to_update.get('value')

    if not record_id or new_value is None:  # new_value может быть 0, поэтому проверяем на None
        return jsonify({"success": False, "message": "Отсутствуют ID или значение."}), 400

    # 1. Получаем текущий файл и SHA
    csv_string, sha = get_csv_content()
    if not csv_string:
        return jsonify({"success": False, "message": "Не удалось загрузить данные для обновления."}), 500

    # 2. Изменяем данные в CSV
    input_file = StringIO(csv_string)
    output_file = StringIO()

    # Используем точку с запятой в качестве разделителя!
    reader = csv.DictReader(input_file, delimiter=CSV_DELIMITER)
    fieldnames = reader.fieldnames
    writer = csv.DictWriter(output_file, fieldnames=fieldnames, delimiter=CSV_DELIMITER)

    writer.writeheader()

    is_updated = False
    for row in reader:
        # Сравниваем по столбцу ID_COLUMN
        if row.get(ID_COLUMN) == record_id:
            # Обновляем столбец VALUE_COLUMN
            row[VALUE_COLUMN] = str(new_value)  # Приводим к строке для записи в CSV
            is_updated = True
        writer.writerow(row)

    if not is_updated:
        return jsonify({"success": False, "message": f"Запись с {ID_COLUMN} '{record_id}' не найдена."}), 404

    new_csv_string = output_file.getvalue()

    # 3. Записываем обновленный контент обратно на GitHub
    commit_msg = f"Обновление '{VALUE_COLUMN}' для {ID_COLUMN} '{record_id}' до значения '{new_value}'."
    success, message = update_csv_file(new_csv_string, sha, commit_msg)

    return jsonify({"success": success, "message": message})


if __name__ == '__main__':
    # Используем os.environ.get для установки порта на Render
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)