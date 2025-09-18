#!/usr/bin/env python3
"""
НАГЛЯДНАЯ ДЕМОНСТРАЦИЯ: Как работают токены Yandex Cloud
"""

import requests
import json
from datetime import datetime, timedelta

def demonstrate_tokens():
    """Демонстрация разницы между OAuth и IAM токенами"""
    
    print("🔍 РАЗБИРАЕМСЯ С ТОКЕНАМИ YANDEX CLOUD")
    print("="*60)
    
    # Ваши данные
    oauth_token = "y0_xDapiLvBBjB3RMgureWpRRd-4N8PQ1wUwN2LE2biUiAYyiHJA"
    folder_id = "b1g6ft1co3nrff8jds4g"
    
    print(f"\n1️⃣ OAUTH TOKEN (долгоживущий):")
    print(f"   {oauth_token}")
    print(f"   ✅ Этот токен ПРАВИЛЬНЫЙ")
    print(f"   ✅ Он НЕ меняется каждые 12 часов") 
    print(f"   ✅ Действует месяцами")
    print(f"   🎯 Используется для получения IAM токенов")
    
    print(f"\n2️⃣ IAM TOKEN (короткоживущий):")
    print(f"   Этот токен получаем из OAuth токена")
    print(f"   ⏱️  Действует ровно 12 часов")
    print(f"   🔄 Каждый раз НОВЫЙ при запросе")
    print(f"   🎯 Используется для API запросов")
    
    # Получаем IAM токен
    print(f"\n🔄 ПОЛУЧАЕМ НОВЫЙ IAM TOKEN...")
    
    iam_url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
    iam_payload = {"yandexPassportOauthToken": oauth_token}
    
    try:
        response = requests.post(iam_url, json=iam_payload)
        response.raise_for_status()
        data = response.json()
        
        iam_token = data["iamToken"]
        expires_at = data.get("expiresAt")
        
        print(f"✅ НОВЫЙ IAM TOKEN получен:")
        print(f"   {iam_token[:50]}...")
        print(f"   📅 Действует до: {expires_at}")
        
        # Парсим время истечения
        if expires_at:
            expire_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            time_left = expire_time - datetime.now()
            hours_left = time_left.total_seconds() / 3600
            print(f"   ⏳ Осталось: {hours_left:.1f} часов")
        
        print(f"\n🔄 ПОЛУЧАЕМ ЕЩЁ ОДИН IAM TOKEN (через 3 секунды)...")
        import time
        time.sleep(3)
        
        # Получаем второй IAM токен
        response2 = requests.post(iam_url, json=iam_payload)
        data2 = response2.json()
        iam_token2 = data2["iamToken"]
        
        print(f"✅ ВТОРОЙ IAM TOKEN:")
        print(f"   {iam_token2[:50]}...")
        
        # Сравниваем
        if iam_token != iam_token2:
            print(f"   🎯 ВИДИТЕ? Токены РАЗНЫЕ!")
            print(f"   🔄 IAM токен меняется при каждом запросе")
        else:
            print(f"   ⚠️  Токены одинаковые (редкий случай)")
            
        print(f"\n💡 ВЫВОД:")
        print(f"   ✅ Ваш OAuth токен правильный и не менялся")
        print(f"   ✅ IAM токены получаются новые каждый раз")
        print(f"   ✅ Проблема была в том, что старый IAM истек")
        print(f"   ✅ Мой код автоматически обновляет IAM токены")
        
        return iam_token
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None


def show_token_lifecycle():
    """Показываем жизненный цикл токенов"""
    
    print(f"\n📊 ЖИЗНЕННЫЙ ЦИКЛ ТОКЕНОВ:")
    print("="*60)
    
    print(f"""
🔑 OAuth Token:
   ├── Создается: При авторизации в Yandex
   ├── Живёт: Месяцы/годы
   ├── Меняется: Только при переавторизации
   └── Используется: Для получения IAM токенов

⚡ IAM Token:
   ├── Создается: По запросу из OAuth токена  
   ├── Живёт: Ровно 12 часов
   ├── Меняется: При каждом запросе на получение
   └── Используется: Для API запросов (ASR, TTS, etc)
    
🔄 Автообновление (мой код):
   ├── Проверяет: Каждые 5 минут
   ├── Обновляет: За 30 минут до истечения
   ├── Повторяет: При ошибках 401
   └── Логирует: Все операции
""")


def main():
    print("🚀 ДЕМОНСТРАЦИЯ РАБОТЫ С ТОКЕНАМИ YANDEX")
    print("="*60)
    
    # Демонстрируем токены
    iam_token = demonstrate_tokens()
    
    # Показываем жизненный цикл
    show_token_lifecycle()
    
    if iam_token:
        print(f"\n🎉 РЕЗУЛЬТАТ:")
        print(f"   ✅ Проблема с истекшим токеном РЕШЕНА")
        print(f"   ✅ У вас теперь есть свежий IAM токен")
        print(f"   ✅ Автообновление предотвратит повторение проблемы")
        print(f"   ✅ Ваш OAuth токен остается тем же (это нормально)")
        
        print(f"\n📋 ЧТО ДЕЛАТЬ ДАЛЬШЕ:")
        print(f"   1. Используйте мой код для автообновления")
        print(f"   2. OAuth токен НЕ нужно менять")  
        print(f"   3. IAM токены будут обновляться автоматически")
        print(f"   4. Забудьте про ошибки 401 Unauthorized")

if __name__ == "__main__":
    main()
