from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Union
import requests
import math
import json
import redis
import time
from datetime import datetime
from enum import Enum

# Инициализация приложения FastAPI
app = FastAPI(
    title="LTC Exchange API",
    description="API для получения данных о биржах, торгующих Litecoin (LTC)",
    version="1.0.0"
)

# Настройка CORS для доступа с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация подключения к Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
CACHE_TTL = 180  # время жизни кэша - 3 минуты

# Обновляем класс перечисления для поддержки возможных критериев сортировки
class SortCriterion(str, Enum):
    ID = "id"  # Добавляем новый критерий сортировки по ID
    PRICE = "price"
    VOLUME = "volume"
    PLUS_DEPTH = "plus_depth"
    MINUS_DEPTH = "minus_depth"
    EXCHANGE = "exchange"

# Модели данных для типизации и документации
class ExchangeData(BaseModel):
    id: int
    exchange: str
    pair: str
    price: str
    plusTwoPercentDepth: str
    minusTwoPercentDepth: str
    volume24h: str
    volumePercentage: str
    lastUpdated: str
    icon: Optional[str] = None  # Дополнительное поле для иконки биржи

class ExchangeResponse(BaseModel):
    status: str
    data: List[ExchangeData]

class DepthData(BaseModel):
    exchange: str
    currentPrice: float
    plus2PercentDepth: str
    minus2PercentDepth: str

class DepthResponse(BaseModel):
    status: str
    data: DepthData

# Глобальное хранилище для пользовательских бирж
custom_exchanges: Dict[str, ExchangeData] = {}

class CustomExchangeInput(BaseModel):
    exchange: str
    pair: str = "LTC/USDT"
    price: float
    plusTwoPercentDepth: float
    minusTwoPercentDepth: float
    volume24h: float
    volumePercentage: float
    icon: Optional[str] = None

class CustomExchangeUpdateInput(BaseModel):
    pair: Optional[str] = None
    price: Optional[float] = None
    plusTwoPercentDepth: Optional[float] = None
    minusTwoPercentDepth: Optional[float] = None
    volume24h: Optional[float] = None
    volumePercentage: Optional[float] = None
    icon: Optional[str] = None

@app.post("/api/custom-exchanges", tags=["exchanges"])
async def add_custom_exchange(exchange_data: CustomExchangeInput):
    """
    Добавляет или обновляет пользовательскую биржу с указанными данными.
    Биржа будет отображаться в общем списке при запросе всех бирж.
    """
    global custom_exchanges
    
    exchange_id = exchange_data.exchange.lower()
    
    custom_exchanges[exchange_id] = ExchangeData(
        id=0,  # ID будет присвоен позже при объединении списков
        exchange=exchange_data.exchange,
        pair=exchange_data.pair,
        price=f"{exchange_data.price:.4f}",
        plusTwoPercentDepth=f"${math.floor(exchange_data.plusTwoPercentDepth):,}",
        minusTwoPercentDepth=f"${math.floor(exchange_data.minusTwoPercentDepth):,}",
        volume24h=f"${math.floor(exchange_data.volume24h):,}",
        volumePercentage=f"{exchange_data.volumePercentage:.2f}%",
        lastUpdated='User defined',
        icon=exchange_data.icon
    )
    
    return {
        "status": "success",
        "message": f"Биржа {exchange_data.exchange} успешно добавлена/обновлена"
    }

@app.get("/api/custom-exchanges", tags=["exchanges"])
async def get_custom_exchanges():
    """
    Возвращает список пользовательских бирж.
    """
    return {
        "status": "success",
        "data": list(custom_exchanges.values())
    }

@app.delete("/api/custom-exchanges/{exchange_name}", tags=["exchanges"])
async def delete_custom_exchange(exchange_name: str):
    """
    Удаляет пользовательскую биржу по имени.
    """
    global custom_exchanges
    
    exchange_id = exchange_name.lower()
    if exchange_id in custom_exchanges:
        del custom_exchanges[exchange_id]
        return {
            "status": "success",
            "message": f"Биржа {exchange_name} успешно удалена"
        }
    else:
        raise HTTPException(status_code=404, detail=f"Биржа {exchange_name} не найдена")

@app.patch("/api/custom-exchanges/{exchange_name}", tags=["exchanges"])
async def update_custom_exchange(exchange_name: str, exchange_data: CustomExchangeUpdateInput):
    """
    Обновляет отдельные параметры пользовательской биржи.
    Обновляются только те поля, которые указаны в запросе.
    """
    global custom_exchanges
    
    exchange_id = exchange_name.lower()
    if exchange_id not in custom_exchanges:
        raise HTTPException(status_code=404, detail=f"Биржа {exchange_name} не найдена")
    
    # Получаем текущие данные о бирже
    exchange = custom_exchanges[exchange_id]
    
    # Обновляем поля, которые были предоставлены
    if exchange_data.pair is not None:
        exchange.pair = exchange_data.pair
        
    if exchange_data.price is not None:
        exchange.price = f"{exchange_data.price:.4f}"
        
    if exchange_data.plusTwoPercentDepth is not None:
        exchange.plusTwoPercentDepth = f"${math.floor(exchange_data.plusTwoPercentDepth):,}"
        
    if exchange_data.minusTwoPercentDepth is not None:
        exchange.minusTwoPercentDepth = f"${math.floor(exchange_data.minusTwoPercentDepth):,}"
        
    if exchange_data.volume24h is not None:
        exchange.volume24h = f"${math.floor(exchange_data.volume24h):,}"
        
    if exchange_data.volumePercentage is not None:
        exchange.volumePercentage = f"{exchange_data.volumePercentage:.2f}%"
        
    if exchange_data.icon is not None:
        exchange.icon = exchange_data.icon
    
    # Обновляем временную метку
    exchange.lastUpdated = 'User updated'
    
    return {
        "status": "success",
        "message": f"Биржа {exchange_name} успешно обновлена",
        "data": exchange
    }

@app.get("/api/ltc-exchanges", response_model=ExchangeResponse, tags=["exchanges"])
async def get_ltc_exchanges(
    sort_by: Optional[SortCriterion] = None,
    descending: bool = True
):
    """
    Получает список бирж, торгующих парой LTC/USDT с возможностью сортировки по различным параметрам.
    
    - **sort_by**: Критерий сортировки (id, price, volume, plus_depth, minus_depth, exchange)
    - **descending**: Порядок сортировки (по умолчанию - по убыванию)
    """
    try:
        # Проверяем наличие данных в кэше Redis
        cache_key = f"ltc_exchanges_data:{sort_by}:{descending}"
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            # Улучшенное логирование
            print(f"CACHE HIT: Данные получены из кэша Redis с ключом {cache_key}")
            return json.loads(cached_data)
        else:
            print(f"CACHE MISS: Данные не найдены в кэше Redis с ключом {cache_key}")
        
        # Если данных в кэше нет, получаем их из API
        print("Получаем данные из API CoinGecko")
        
        # Получаем список бирж для сопоставления иконок
        exchanges_response = requests.get("https://api.coingecko.com/api/v3/exchanges")
        exchange_icon_mapping = {}
        if exchanges_response.status_code == 200:
            for ex in exchanges_response.json():
                exchange_icon_mapping[ex["id"]] = ex.get("image")
        
        # Получаем данные о Litecoin с CoinGecko
        response = requests.get('https://api.coingecko.com/api/v3/coins/litecoin/tickers')
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, 
                                detail=f"Ошибка API CoinGecko: {response.text}")
        
        data = response.json()
        exchanges = []
        
        for ticker in data['tickers']:
            # Фильтруем только пары LTC/USDT
            if ticker['target'] == 'USDT':
                base_volume_usd = ticker['converted_volume'].get('usd', 0)
                
                # Расчет значений глубины ордеров (примерные расчеты)
                plus_two_percent_depth = math.floor(base_volume_usd * 0.06)
                minus_two_percent_depth = math.floor(base_volume_usd * 0.05)
                
                # Получаем информацию о бирже и сопоставляем с иконкой
                market_info = ticker.get('market', {})
                exchange_identifier = market_info.get('identifier')
                icon_url = exchange_icon_mapping.get(exchange_identifier)
                
                exchange_data = ExchangeData(
                    id=0,  # Временный ID, переназначим позже
                    exchange=market_info.get('name', 'Unknown'),
                    pair='LTC/USDT',
                    price=f"{float(ticker['last']):.4f}",
                    plusTwoPercentDepth=f"${plus_two_percent_depth:,}",
                    minusTwoPercentDepth=f"${minus_two_percent_depth:,}",
                    volume24h=f"${math.floor(base_volume_usd):,}",
                    volumePercentage=f"{ticker.get('bid_ask_spread_percentage', 1.0):.2f}%",
                    lastUpdated='Recently',
                    icon=icon_url
                )
                
                exchanges.append(exchange_data)
        
        # Добавляем пользовательские биржи к основному списку
        for custom_exchange in custom_exchanges.values():
            # Копируем данные, чтобы избежать изменения оригинального объекта
            exchange_copy = ExchangeData(
                id=0,  # Временный ID, переназначим позже
                exchange=custom_exchange.exchange,
                pair=custom_exchange.pair,
                price=custom_exchange.price,
                plusTwoPercentDepth=custom_exchange.plusTwoPercentDepth,
                minusTwoPercentDepth=custom_exchange.minusTwoPercentDepth,
                volume24h=custom_exchange.volume24h,
                volumePercentage=custom_exchange.volumePercentage,
                lastUpdated=custom_exchange.lastUpdated,
                icon=custom_exchange.icon
            )
            exchanges.append(exchange_copy)
        
        # Выполняем сортировку в зависимости от параметров
        if sort_by:
            if sort_by == SortCriterion.ID:
                # Сортировка по ID
                exchanges.sort(key=lambda x: x.id, reverse=descending)  
            elif sort_by == SortCriterion.PRICE:
                exchanges.sort(key=lambda x: float(x.price.replace(',', '')), reverse=descending)
            elif sort_by == SortCriterion.VOLUME:
                exchanges.sort(key=lambda x: float(x.volume24h.replace('$', '').replace(',', '')), reverse=descending)
            elif sort_by == SortCriterion.PLUS_DEPTH:
                exchanges.sort(key=lambda x: float(x.plusTwoPercentDepth.replace('$', '').replace(',', '')), reverse=descending)
            elif sort_by == SortCriterion.MINUS_DEPTH:
                exchanges.sort(key=lambda x: float(x.minusTwoPercentDepth.replace('$', '').replace(',', '')), reverse=descending)
            elif sort_by == SortCriterion.EXCHANGE:
                exchanges.sort(key=lambda x: x.exchange.lower(), reverse=descending)
        else:
            # По умолчанию сортируем по объему торгов
            exchanges.sort(key=lambda x: float(x.volume24h.replace('$', '').replace(',', '')), reverse=True)
        
        # Присваиваем ID в зависимости от сортировки только если НЕ сортируем по ID
        # Если сортируем по ID, то ID уже должны быть установлены
        if sort_by != SortCriterion.ID:
            for i, exchange in enumerate(exchanges, start=1):
                exchange.id = i
                
        result = {
            'status': 'success',
            'data': exchanges
        }
        
        # Более подробное логирование при сохранении в кэш
        print(f"CACHE SET: Сохраняем данные в Redis с ключом {cache_key} и TTL {CACHE_TTL} секунд")
        redis_client.setex(cache_key, CACHE_TTL, json.dumps(result, default=lambda o: o.__dict__))
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении данных по LTC: {str(e)}")

@app.get("/api/ltc-exchanges-cmc", response_model=ExchangeResponse, tags=["exchanges"])
async def get_ltc_exchanges_cmc():
    """
    Альтернативный маршрут для получения данных через CoinMarketCap API.
    Требует API-ключ от CoinMarketCap.
    """
    try:
        # Вам потребуется API-ключ от CoinMarketCap
        CMC_API_KEY = 'ВАШ_API_КЛЮЧ'
        
        headers = {
            'X-CMC_PRO_API_KEY': CMC_API_KEY
        }
        
        params = {
            'symbol': 'LTC',
            'convert': 'USD'
        }
        
        response = requests.get(
            'https://pro-api.coinmarketcap.com/v1/cryptocurrency/market-pairs/latest',
            headers=headers,
            params=params
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, 
                                detail=f"Ошибка API CoinMarketCap: {response.text}")
        
        data = response.json()
        exchanges = []
        index = 1
        
        for pair in data['data']['market_pairs']:
            if pair['market_pair_quote']['symbol'] == 'USDT':
                quote_volume = pair['quote']['USD']['volume_24h']
                
                exchange_data = ExchangeData(
                    id=index,
                    exchange=pair['exchange']['name'],
                    pair='LTC/USDT',
                    price=f"{float(pair['quote']['USD']['price']):.4f}",
                    plusTwoPercentDepth=f"${math.floor(quote_volume * 0.05):,}",
                    minusTwoPercentDepth=f"${math.floor(quote_volume * 0.04):,}",
                    volume24h=f"${math.floor(quote_volume):,}",
                    volumePercentage="1.23%",  # Заглушка - замените на реальные данные
                    lastUpdated='Recently'
                )
                
                exchanges.append(exchange_data)
                index += 1
        
        exchanges.sort(key=lambda x: float(x.volume24h.replace('$', '').replace(',', '')), reverse=True)
        top_10_exchanges = exchanges[:10]
        
        return {
            'status': 'success',
            'data': top_10_exchanges
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, 
                            detail=f"Ошибка при получении данных по LTC через CoinMarketCap: {str(e)}")

@app.get("/api/ltc-depth/{exchange}", response_model=DepthResponse, tags=["depth"])
async def get_ltc_depth(exchange: str):
    """
    Получает подробную информацию о глубине рынка для конкретной биржи.
    Пример для биржи Binance (для других бирж может потребоваться другая логика).
    
    - **exchange**: Название биржи (например, 'binance')
    """
    try:
        depth_data = None
        
        # Логика получения книги ордеров с разных бирж
        if exchange.lower() == 'binance':
            response = requests.get('https://api.binance.com/api/v3/depth', 
                                    params={'symbol': 'LTCUSDT', 'limit': 100})
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, 
                                    detail=f"Ошибка API Binance: {response.text}")
            
            depth_data = response.json()
        else:
            raise HTTPException(status_code=404, 
                                detail=f"Данные о глубине рынка для биржи {exchange} недоступны")
        
        # Получаем текущую цену LTC
        current_price = await get_current_ltc_price()
        plus_2_percent = current_price * 1.02
        minus_2_percent = current_price * 0.98
        
        # Расчет суммарного объема до +2% и -2% от текущей цены
        plus_2_percent_depth = 0
        minus_2_percent_depth = 0
        
        # Расчет для ордеров на покупку (bid)
        for price, volume in depth_data['bids']:
            if float(price) >= minus_2_percent:
                minus_2_percent_depth += float(price) * float(volume)
            else:
                break
        
        # Расчет для ордеров на продажу (ask)
        for price, volume in depth_data['asks']:
            if float(price) <= plus_2_percent:
                plus_2_percent_depth += float(price) * float(volume)
            else:
                break
        
        return {
            'status': 'success',
            'data': {
                'exchange': exchange,
                'currentPrice': current_price,
                'plus2PercentDepth': f"${math.floor(plus_2_percent_depth):,}",
                'minus2PercentDepth': f"${math.floor(minus_2_percent_depth):,}"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, 
                            detail=f"Ошибка при получении данных о глубине рынка для {exchange}: {str(e)}")

async def get_current_ltc_price() -> float:
    """
    Вспомогательная функция для получения текущей цены LTC
    """
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price', 
                                params={'ids': 'litecoin', 'vs_currencies': 'usd'})
        if response.status_code != 200:
            return 0
        
        return response.json()['litecoin']['usd']
    except Exception as e:
        print(f"Ошибка при получении текущей цены LTC: {str(e)}")
        return 0

# Добавление эндпоинта для графика цены LTC

class PriceHistoryItem(BaseModel):
    """Модель для элемента истории цены"""
    date: str       # Дата в формате "месяц/день" (например, "3/23")
    price: float    # Цена в USD

class PriceHistoryResponse(BaseModel):
    """Модель для ответа с историей цены"""
    status: str
    data: List[PriceHistoryItem]
    currency: str = "USD"
    period: str

@app.get("/api/ltc-price-history", tags=["prices"])
async def get_ltc_price_history(days: int = 30, daily_close: bool = True):
    """
    Получает историю цены Litecoin за указанный период для построения графика.
    
    - **days**: Количество дней истории (по умолчанию 30 дней)
    - **daily_close**: Если True, возвращает только цены закрытия дня
    """
    try:
        # Ограничиваем maximum до 90 дней
        if days > 90:
            days = 90
        elif days < 1:
            days = 1
            
        # Проверяем наличие данных в кэше Redis с учетом параметра daily_close
        cache_key = f"ltc_price_history_new_format:{days}:{daily_close}"
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            # Если данные найдены в кэше, возвращаем их
            print(f"Возвращаем данные истории цен из кэша Redis за {days} дней")
            return json.loads(cached_data)
        
        # Если данных в кэше нет, получаем их из API CoinGecko
        print(f"Получаем данные истории цен из API CoinGecko за {days} дней")
        
        # Убираем параметр interval, так как API автоматически определит нужный интервал
        params = {
            'vs_currency': 'usd',
            'days': days
        }
        
        response = requests.get(
            'https://api.coingecko.com/api/v3/coins/litecoin/market_chart',
            params=params
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, 
                                detail=f"Ошибка API CoinGecko: {response.text}")
        
        data = response.json()
        prices = data.get('prices', [])  # Исторические цены в формате [timestamp, price]
        
        # Если нужны только цены закрытия дня
        if daily_close:
            # Группируем данные по дням и берем последнее значение для каждого дня
            daily_prices = {}
            for item in prices:
                timestamp, price = item
                # Преобразуем timestamp в дату без времени
                date_obj = datetime.fromtimestamp(timestamp / 1000)
                date_key = f"{date_obj.year}-{date_obj.month}-{date_obj.day}"
                
                # Сохраняем или обновляем цену для этого дня
                # Последняя запись для каждого дня будет перезаписывать предыдущие
                daily_prices[date_key] = {
                    'date': f"{date_obj.month}/{date_obj.day}",
                    'price': round(price, 2)
                }
            
            # Преобразуем словарь в список, сортируя по дате
            price_history = [daily_prices[key] for key in sorted(daily_prices.keys())]
        else:
            # Преобразуем данные в прежний формат с почасовой детализацией
            price_history = []
            for item in prices:
                timestamp, price = item
                date_obj = datetime.fromtimestamp(timestamp / 1000)
                formatted_date = f"{date_obj.month}/{date_obj.day}"
                
                price_history.append({
                    'date': formatted_date,
                    'price': round(price, 2)
                })
        
        # Определяем период
        if days <= 1:
            period = "24 часа"
        elif days <= 7:
            period = "7 дней"
        elif days <= 30:
            period = "1 месяц"
        else:
            period = f"{days} дней"
        
        result = {
            'status': 'success',
            'data': price_history,
            'currency': 'USD',
            'period': period
        }
        
        # Устанавливаем время кэширования в зависимости от запрошенного периода
        if days >= 30:
            ttl = 43200  # 12 часов в секундах
        elif days >= 7:
            ttl = 21600  # 6 часов в секундах
        else:
            ttl = 3600   # 1 час в секундах
            
        # Сохраняем результат в Redis с новым TTL
        redis_client.setex(cache_key, ttl, json.dumps(result, default=lambda o: o.__dict__))
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении истории цен LTC: {str(e)}")

# Корневой маршрут с информацией об API
@app.get("/", tags=["info"])
async def root():
    """
    Возвращает общую информацию об API
    """
    return {
        "name": "LTC Exchange API",
        "version": "1.0.0",
        "description": "API для получения данных о биржах, торгующих Litecoin (LTC)",
        "endpoints": [
            {
                "path": "/api/ltc-exchanges",
                "description": "Получить данные о биржах LTC/USDT через CoinGecko"
            },
            {
                "path": "/api/ltc-exchanges-cmc",
                "description": "Получить данные о биржах LTC/USDT через CoinMarketCap"
            },
            {
                "path": "/api/ltc-depth/{exchange}",
                "description": "Получить данные о глубине рынка для конкретной биржи"
            },
            {
                "path": "/api/ltc-price-history",
                "description": "Получить историю цены Litecoin за указанный период для построения графика"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
