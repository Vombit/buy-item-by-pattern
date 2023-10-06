from playwright.sync_api import Playwright, sync_playwright
from dotenv import load_dotenv, find_dotenv
from steampy.client import GameOptions
from steampy.models import Currency
from io import BytesIO
from PIL import Image
load_dotenv(find_dotenv())
import requests, time, os, re, statistics, pickle, json
steam_client = None
lots_per_page = os.environ.get("LOTS_PER_PAGE")

 
def find_items(page, name, image_url, avg_price, percent, float_low, float_max):
    item_page = page.query_selector_all('.market_listing_row.market_recent_listing_row')
    
    for _ in range(15):
        if (len(item_page) != lots_per_page):
            time.sleep(1)
            item_page = page.query_selector_all('.market_listing_row.market_recent_listing_row')
        else:
            break
        
    for item in item_page:
        try:
            item.hover(force=True)
            item.query_selector('.market_actionmenu_button').click()
            pop = page.query_selector('#market_action_popup_itemactions')
            item_url = pop.query_selector('.popup_menu_item').get_attribute('href')
            
            item_get = requests.get(f'https://skinstats.app/api?url={item_url}')
            item_float = item_get.json()['paintwear']
            
            item_price = int(float(re.search(r"\d+(\.\d+)?", item.query_selector('.market_listing_price.market_listing_price_with_fee').inner_text().replace(',', '.')).group()) * 100)
            item_price_without_fee = int(float(re.search(r"\d+(\.\d+)?", item.query_selector('.market_listing_price.market_listing_price_without_fee').inner_text().replace(',', '.')).group()) * 100)
            item_id = re.sub(r"\D", "", item.get_attribute('id'))
        
            # try buy item
            avg_prices = float(avg_price)*100
            max_price = int(avg_prices * (1 + float(percent)))
        
            print('Проверка предмета на соответствие...')
            if float(item['item_float']) >= float(float_low) and float(item['item_float']) <= float(float_max):
                if int(item['item_price']) <= int(max_price):
                    buy_item(name, item_id, item_price, item_price_without_fee, item_float, avg_prices, image_url)
                else:
                    print('Предмет не соответствует цене')
            else:
                print('Предмет не соответствует float')
            
        except Exception as e:
            print(e)
            continue
        
    return True


def get_item_data(name, float_low, float_max, percent):
    def main(playwright: Playwright):
        url = f'https://steamcommunity.com/market/listings/730/{name}'
        proxy = {
                'server': os.environ.get("PROXY"),
                'username': os.environ.get("USERNAME_PROXY"),
                'password': os.environ.get("PASSWORD_PROXY")
            }
        if not os.environ.get("PROXY"):
            browser = playwright.firefox.launch(headless=True)
        else:
            browser = playwright.firefox.launch(headless=True, proxy=proxy)

        context = browser.new_context()
        cookies = [{
            'name':'steamLoginSecure', 
            'value':steam_client._session.cookies.get_dict()['steamLoginSecure'], 
            'domain':'steamcommunity.com', 
            'path':'/', 
            'httpOnly':True, 
            'secure':True
             }]
        context.add_cookies(cookies)
        
        # пропуск загрузки картинок
        def intercept_request(route, request):
            if request.resource_type == 'image':
                route.abort()
            else:
                route.continue_()
        context.route('**/*', intercept_request)
        
        page = context.new_page()
        page.goto(url)
        time.sleep(3)
        page.evaluate(f'g_oSearchResults.m_cPageSize = {lots_per_page};g_oSearchResults.GoToPage(0, true);')
        
        # url image skin
        url = page.query_selector('.market_listing_largeimage > img').get_attribute('src')
        
        # find AVG price
        table = page.query_selector('.market_commodity_orders_table')
        rows = table.query_selector_all('tbody > tr')
        prices = []
        for row in rows[1:6]:
            cells = row.query_selector_all('td')
            price = cells[0].inner_text()
            price = re.sub('[^0-9.]', '', price)
            price = price.replace('.', '')
            price = price[:-2] + '.' + price[-2:]
            prices.append(price)
        prices = [float(price) for price in prices]
        avg_price = statistics.mean(prices)

        browser.close()
        
        find_items(page, name, url, avg_price, percent, float_low, float_max)
        
    with sync_playwright() as playwright:
        return main(playwright)

def buy_item(name, id, price, price_without_fee, item_float, avg_price, image_url):
    bot_token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    url = f'https://api.telegram.org/bot{bot_token}/sendPhoto'
    fee = int(price - price_without_fee)

    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    files= {"photo": img_io}
    
    message = f'{name}\n\nFloat: {item_float}\nAVG price: {round(float(avg_price/100), 3)} руб.\nPrice: {float(price/100)} руб.\n\n'
    
    print('Попытка купить предмет')
    try:
        response = steam_client.market.buy_item(name, id, price, fee, GameOptions.CS, Currency.RUB)
    except:
        print('Покупка не успешна!')
        payload = {'chat_id': chat_id,'caption': message + '❌ Fail ❌'}
        requests.post(url, files=files, data=payload)
        return False
    
    if response['wallet_info']['success'] == 1:
        print('Покупка успешна!')
        payload = {'chat_id': chat_id,'caption': message + '✅ Buy ✅'}
        requests.post(url, files=files, data=payload)
        return True
    else:
        print('Покупка не успешна!')
        payload = {'chat_id': chat_id,'caption': message + '❌ Fail ❌'}
        requests.post(url, files=files, data=payload)
        return False


def main(name, float_low, float_max, percent):
    global steam_client
    i = 5
    
    with open('data/steamClient.pkl', 'rb') as f: 
        steam_client = pickle.load(f)
        
    print('Проверка страницы предмета')
    for _ in range(i):
        try:
            get_item_data(name, float_low, float_max, percent)
            print('Страница проверена')
            break
        except:
            print(f'Произошла ошибка! \n Попытка через {i} секунд')
            time.sleep(i)
    else:
        print(f'Не удалось проверить предмет!')
        return False