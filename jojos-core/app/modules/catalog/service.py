CATALOG = {
    "groups": [
        {
            "id": "pizza",
            "name": "Пицца",
            "items": [
                {
                    "id": "pizza23",
                    "name": "Пицца 23 см",
                    "price": 2400,
                    "prep_seconds": 420,
                    "description": "Компактная пицца с ярким вкусом.",
                    "image_url": "/placeholder/pizza23.jpg",
                    "options": [
                        {
                            "id": "cheese",
                            "name": "Сыр",
                            "mode": "multi",
                            "items": [
                                {"id": "mozzarella", "name": "Моцарелла", "price": 100},
                                {"id": "cheddar", "name": "Чеддер", "price": 100},
                                {"id": "parmesan", "name": "Пармезан", "price": 100},
                                {"id": "blue", "name": "Голубой сыр", "price": 100},
                            ],
                        },
                        {
                            "id": "extras",
                            "name": "Дополнительно",
                            "mode": "multi",
                            "items": [
                                {"id": "onion", "name": "Лук", "price": 100},
                                {"id": "jalapeno", "name": "Халапеньо", "price": 100},
                                {"id": "pineapple", "name": "Ананас", "price": 100},
                                {"id": "chorizo", "name": "Колбаски чироззо", "price": 100},
                            ],
                        },
                    ],
                },
                {
                    "id": "pizza30",
                    "name": "Пицца 30 см",
                    "price": 3200,
                    "prep_seconds": 480,
                    "description": "Самый популярный размер.",
                    "image_url": "/placeholder/pizza30.jpg",
                    "options": [],
                },
                {
                    "id": "pizza45",
                    "name": "Пицца 45 см",
                    "price": 4700,
                    "prep_seconds": 600,
                    "description": "Большой формат для компании.",
                    "image_url": "/placeholder/pizza45.jpg",
                    "options": [],
                },
            ],
        },
        {
            "id": "icecream",
            "name": "Мороженое",
            "items": [
                {
                    "id": "ice_cream",
                    "name": "Сливочное",
                    "price": 1600,
                    "prep_seconds": 60,
                    "description": "Нежная сливочная база.",
                    "image_url": "/placeholder/ice_cream.jpg",
                    "options": [],
                },
                {
                    "id": "ice_choco",
                    "name": "Шоколадное",
                    "price": 1700,
                    "prep_seconds": 60,
                    "description": "Насыщенный шоколад.",
                    "image_url": "/placeholder/ice_choco.jpg",
                    "options": [],
                },
                {
                    "id": "ice_matcha",
                    "name": "Матча",
                    "price": 1800,
                    "prep_seconds": 70,
                    "description": "Матча и сливочная текстура.",
                    "image_url": "/placeholder/ice_matcha.jpg",
                    "options": [],
                },
            ],
        },
        {
            "id": "tea",
            "name": "Чай",
            "items": [
                {
                    "id": "tea_black",
                    "name": "Черный чай",
                    "price": 900,
                    "prep_seconds": 90,
                    "description": "Классический ароматный чай.",
                    "image_url": "/placeholder/tea_black.jpg",
                    "options": [
                        {
                            "id": "temperature",
                            "name": "Температура подачи",
                            "mode": "single",
                            "items": [
                                {"id": "hot", "name": "Горячий", "price": 0},
                                {"id": "cold", "name": "Холодный", "price": 0},
                            ],
                        }
                    ],
                },
                {
                    "id": "tea_green",
                    "name": "Зеленый чай",
                    "price": 950,
                    "prep_seconds": 90,
                    "description": "Свежий и мягкий вкус.",
                    "image_url": "/placeholder/tea_green.jpg",
                    "options": [],
                },
                {
                    "id": "tea_milk",
                    "name": "Молочный чай",
                    "price": 1200,
                    "prep_seconds": 120,
                    "description": "Бархатистая текстура.",
                    "image_url": "/placeholder/tea_milk.jpg",
                    "options": [],
                },
            ],
        },
        {
            "id": "drinks",
            "name": "Напитки",
            "items": [
                {
                    "id": "lemonade",
                    "name": "Лимонад",
                    "price": 1100,
                    "prep_seconds": 70,
                    "description": "Освежающий напиток.",
                    "image_url": "/placeholder/lemonade.jpg",
                    "options": [],
                },
                {
                    "id": "hotdrink",
                    "name": "Горячий напиток",
                    "price": 1250,
                    "prep_seconds": 90,
                    "description": "Уютный вариант.",
                    "image_url": "/placeholder/hotdrink.jpg",
                    "options": [],
                },
                {
                    "id": "water",
                    "name": "Вода",
                    "price": 500,
                    "prep_seconds": 20,
                    "description": "Чистая вода.",
                    "image_url": "/placeholder/water.jpg",
                    "options": [],
                },
            ],
        },
        {
            "id": "burger",
            "name": "Бургер",
            "items": [
                {
                    "id": "burger_chicken",
                    "name": "Курица",
                    "price": 1900,
                    "prep_seconds": 300,
                    "description": "Сочный бургер с курицей.",
                    "image_url": "/placeholder/burger_chicken.jpg",
                    "options": [],
                },
                {
                    "id": "burger_beef",
                    "name": "Говядина",
                    "price": 2300,
                    "prep_seconds": 330,
                    "description": "Классический бургер с говядиной.",
                    "image_url": "/placeholder/burger_beef.jpg",
                    "options": [],
                },
                {
                    "id": "burger_fish",
                    "name": "Рыба",
                    "price": 2100,
                    "prep_seconds": 320,
                    "description": "Легкий рыбный бургер.",
                    "image_url": "/placeholder/burger_fish.jpg",
                    "options": [],
                },
            ],
        },
        {
            "id": "coffee",
            "name": "Кофе",
            "items": [
                {
                    "id": "coffee_americano",
                    "name": "Американо",
                    "price": 900,
                    "prep_seconds": 80,
                    "description": "Чистый кофейный профиль.",
                    "image_url": "/placeholder/coffee_americano.jpg",
                    "options": [],
                },
                {
                    "id": "coffee_latte",
                    "name": "Латте",
                    "price": 1200,
                    "prep_seconds": 100,
                    "description": "Нежный кофейный вкус.",
                    "image_url": "/placeholder/coffee_latte.jpg",
                    "options": [],
                },
                {
                    "id": "coffee_cappuccino",
                    "name": "Капучино",
                    "price": 1300,
                    "prep_seconds": 110,
                    "description": "Пышная пенка и аромат.",
                    "image_url": "/placeholder/coffee_cappuccino.jpg",
                    "options": [],
                },
            ],
        },
    ]
}


def get_catalog_data():
    # Central point for future DB/sync-backed catalog loading.
    return CATALOG
