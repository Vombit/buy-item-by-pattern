import csv, re, os, pickle, json, threading, time
from steampy.client import SteamClient
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
from telegram.ext import Application, CommandHandler

import sub.steam as steam
bot_token = os.environ.get("TELEGRAM_TOKEN")

# авторизация стима
steam_client = None
def initSteam():
    global steam_client
    # создание файла для guard
    data = {
        "steamid": os.environ.get("steamid"),
        "shared_secret": os.environ.get("shared_secret"),
        "identity_secret": os.environ.get("identity_secret")
    }
    with open('data/steam_secret.json', 'w') as f:
        json.dump(data, f)
    # создание/проверка готовой сессии
    if(os.path.isfile("data/steamClient.pkl")):
        with open('data/steamClient.pkl', 'rb') as f: 
            steam_client = pickle.load(f) 
            print("Заргузка сессии")
    else:
        steam_client = SteamClient(os.environ.get("STEAM_API_KEY"))
        steam_client.login(os.environ.get("STEAM_LOGIN"), os.environ.get("STEAM_PASSOWORD"), "data/steam_secret.json")
        print("Сохранение сессии")
        with open('data/steamClient.pkl', 'wb') as f: 
            pickle.dump(steam_client, f) 
initSteam()

# система автоматической покупки
def infinite_loop():
    while True:
        # проверка сессии
        if not steam_client.is_session_alive():
            steam_client.login(os.environ.get("STEAM_LOGIN"), os.environ.get("STEAM_PASSOWORD"), "data/steam_secret.json")
            print("Обновление сессии")
            with open('data/steamClient.pkl', 'wb') as f: 
                pickle.dump(steam_client, f) 
                
        try:
            print('\nПроверка фильтров...')
            with open('data/filter.csv', 'r') as file:
                reader = csv.reader(file, delimiter=";")
                rows = list(reader)
            print('Фильтры загружены/обновлены')
            for index, item in enumerate(rows):
                print(f'\nПроверка предмета: {index+1} ({item[1]})')
                if int(item[0]) == 1:
                    print(f'Попытка покупки предмета: {index+1}')
                    name = item[1]
                    float_low = item[2]
                    float_max = item[3]
                    percent = item[4]
                    steam.main(name, float_low, float_max, percent)
                    time.sleep(20)
                else:
                    print(f'Предмет отключен! Переход к следующему')
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            print("Повторная попытка через 180 секунд...")
            time.sleep(180)
            continue
     
# функция telegram help
async def help(update, context):
    await update.message.reply_text("Доступные команды:\n1) `/add` - добавление фильтра;\n2) `/list` - отобразить все фильтры;\n3) `/remove` - удалить фильтр по номеру;\n4) `/change` - изменить фильтр заменив на новые параметры.", parse_mode="Markdown")

# функция telegram добавления данных в csv файл
async def add_data(update, context):
    data = update.message.text[5:].lstrip()
    items = data.split(';')
    pattern = r'^[01];.+;\d+\.\d+;\d+\.\d+;\d+\.\d+$'
    if re.match(pattern, data):
        with open('data/filter.csv', 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(items)
        await update.message.reply_text('Данные успешно добавлены в файл.')
    else:
        await update.message.reply_text('Ошибка, запрос должен выглядеть:\n `/add item`\n\nГде:\n-`item` имеет структуру: `1;name;0.0;1.0;0.5` (`1/0`(вкл/выкл);`название предмета`;`0.0`(мин float);`1.0`(макс float);`0.5`(процент где 1.0=100% и 0.0=0%)) \n\n Пример: \n`/add 0;P250 | Sand Dune (Field-Tested);0.0;0.2;0.1`', parse_mode="Markdown")
    
# функция telegram вывода всех строк из csv файла
async def list_data(update, context):
    with open('data/filter.csv', 'r', encoding='utf-8') as file:
        lines = csv.reader(file, delimiter=';')
        row_count = sum(1 for row in lines)
        file.seek(0)
        if row_count == 0:
            await update.message.reply_text('Фильтров не найдено!')
        else:
            batch = []
            for i, line in enumerate(lines):
                if line:
                    msg = f'\n{i+1}) '+';'.join(line)
                    batch.append(msg)
                    if len(batch) == 20:
                        await update.message.reply_text('\n'.join(batch))
                        batch = []
            if batch:
                await update.message.reply_text('\n'.join(batch))

# функция telegram удаления строки из csv файла
async def remove_data(update, context):
    line_num = update.message.text[8:].lstrip()
    if not line_num or not line_num.isnumeric():
        await update.message.reply_text('Укажите индекс:\n `/remove 1`', parse_mode="Markdown")
    else:
        line_num = int(line_num)
        with open('data/filter.csv', 'r', encoding='utf-8') as file:
            lines = list(csv.reader(file, delimiter=';'))
        with open('data/filter.csv', 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            for i, line in enumerate(lines):
                if i != line_num - 1:
                    writer.writerow(line)
        await update.message.reply_text('Строка успешно удалена из файла', parse_mode="Markdown")
        
# функция telegram изменения строки
async def change_data(update, context):
    er = 'Ошибка, запрос должен выглядеть:\n `/change i item`\n\nГде:\n-`i` индекс в списке;\n-`item` имеет структуру: `1;name;0.0;1.0;0.5` (`1/0`(вкл/выкл);`название предмета`;`0.0`(мин float);`1.0`(макс float);`0.5`(процент где 1.0=100% и 0.0=0%)) \n\n Пример: \n`/change 1 0;P250 | Sand Dune (Field-Tested);0.0;0.2;0.1`'
    data = update.message.text[8:].lstrip()
    index = data.find(' ')
    items = [data[:index], data[index+1:]]
    if len(items) < 2:
        await update.message.reply_text(er, parse_mode="Markdown")
    else:
        index_filter = items[0]
        item_data = items[1]
        pattern = r'^[01];.+;\d+\.\d+;\d+\.\d+;\d+\.\d+$'
        if not index_filter.isnumeric() or not re.match(pattern, item_data):
            await update.message.reply_text(er, parse_mode="Markdown")
        else:
            with open('data/filter.csv', 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=';')
                rows = list(reader)
                rows[int(index_filter)-1] = item_data.split(';')
            with open('data/filter.csv', 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file, delimiter=';')
                for row in rows:
                    writer.writerow(row)
            await update.message.reply_text('Данные успешно обновлены!', parse_mode="Markdown")

def main():
    app = Application.builder().token(bot_token).build()
    # инициализация команд
    app.add_handler(CommandHandler("add", add_data))
    app.add_handler(CommandHandler('remove', remove_data))
    app.add_handler(CommandHandler('list', list_data))
    app.add_handler(CommandHandler('change', change_data))
    app.add_handler(CommandHandler('help', help))
    # запуск бота
    print("Бот запущен!")
    
    # запуск в отдельном потоке основной системы
    thread = threading.Thread(target=infinite_loop)
    thread.start()
    app.run_polling()
    print("Бот выключен!")

if __name__ == "__main__":
    main()