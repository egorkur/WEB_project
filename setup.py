# Файл setup.py запускается один раз для первичного наполнения БД.
# Для дальнейшей работы программы он не требуется.
# Повторный запуск удалит все изменения в БД и вернет ее наполнение к стартовому.
# Файл вспомогательный, не является частью основного функционала.

import sqlite3
import os

# Константы
DB_NAME = 'nutrition.db'


def create_and_populate_db():
    """Создаёт таблицы и заполняет их начальными данными."""

    # Удаляем старый файл базы данных, если он существует
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    ## 1. Создание таблицы Products
    cursor.execute('''
        CREATE TABLE Products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            portion_volume TEXT NOT NULL,
            protein REAL NOT NULL,
            fat REAL NOT NULL,
            carbs REAL NOT NULL,
            kcal REAL NOT NULL
        )
    ''')

    # Начальные данные для Products (порции 100 г или 1 шт/ед.)
    products_data = [
        # (name, portion_volume, protein, fat, carbs, kcal)
        ('Яйцо', '1 шт', 6.0, 5.0, 0.5, 74.0),  # ID 1
        ('Овсянка (сухая)', '100 г', 11.9, 6.9, 66.2, 389.0),  # ID 2
        ('Молоко 2.5%', '100 мл', 3.0, 2.5, 4.7, 54.0),  # ID 3
        ('Куриное филе (вар.)', '100 г', 31.0, 3.6, 0.0, 165.0),  # ID 4
        ('Рис (вар.)', '100 г', 2.6, 0.3, 28.2, 130.0),  # ID 5
        ('Огурец свежий', '100 г', 0.7, 0.1, 3.6, 15.0),  # ID 6
        ('Хлеб пшеничный', '100 г', 7.5, 2.9, 48.8, 265.0),  # ID 7
        ('Творог 5%', '100 г', 16.0, 5.0, 2.0, 121.0),  # ID 8
        ('Сыр твердый', '100 г', 25.0, 30.0, 0.0, 370.0),  # ID 9
        ('Яблоко', '1 шт', 0.4, 0.4, 11.8, 52.0),  # ID 10
        ('Банан', '1 шт', 1.1, 0.3, 22.8, 89.0),  # ID 11
        ('Гречка (вар.)', '100 г', 3.4, 1.0, 17.0, 92.0),  # ID 12
        ('Индейка (вар.)', '100 г', 25.0, 1.0, 0.0, 135.0),  # ID 13
        ('Макароны (вар.)', '100 г', 5.0, 1.0, 25.0, 150.0),  # ID 14
        ('Томаты', '100 г', 0.9, 0.2, 3.9, 20.0),  # ID 15
        ('Лосось (запеч.)', '100 г', 20.0, 12.0, 0.0, 208.0),  # ID 16
        ('Сметана 15%', '100 г', 2.6, 15.0, 3.0, 175.0),  # ID 17
        ('Йогурт натуральный', '100 г', 5.0, 3.2, 4.1, 68.0),  # ID 18
        ('Мёд', '100 г', 0.3, 0.0, 82.4, 329.0),  # ID 19
        ('Картофель (вар.)', '100 г', 2.0, 0.1, 18.0, 86.0),  # ID 20
        ('Фисташки', '100 г', 20.0, 45.0, 28.0, 560.0),  # ID 21
    ]

    cursor.executemany('''
        INSERT INTO Products (name, portion_volume, protein, fat, carbs, kcal)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', products_data)

    product_ids = {name: i + 1 for i, (name, *_) in enumerate(products_data)}

    ## 2. Создание таблицы Dishes
    cursor.execute('''
        CREATE TABLE Dishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            composition TEXT NOT NULL, -- Формат: ID1:QTY1,ID2:QTY2,...
            application TEXT NOT NULL, -- Завтрак, Обед, Ужин, Перекус
            image_path TEXT NOT NULL
        )
    ''')

    # Начальные данные для Dishes. Количество указано в ПОРЦИЯХ (100 г / 1 шт)!
    dishes_data = [
        # (name, composition, application, image_path)
        # --- ЗАВТРАК (6 блюд) ---
        ('Омлет из двух яиц', f"{product_ids['Яйцо']}:2,{product_ids['Молоко 2.5%']}:0.5", 'Завтрак',
         'images/omelet.jpg'),
        ('Овсянка с молоком и мёдом',
         f"{product_ids['Овсянка (сухая)']}:0.5,{product_ids['Молоко 2.5%']}:1.5,{product_ids['Мёд']}:0.2", 'Завтрак',
         'images/oatmeal.jpg'),
        ('Творог с яблоком', f"{product_ids['Творог 5%']}:1.5,{product_ids['Яблоко']}:1", 'Завтрак',
         'images/cottage_cheese.jpg'),
        ('Тосты с сыром', f"{product_ids['Хлеб пшеничный']}:2,{product_ids['Сыр твердый']}:0.5", 'Завтрак',
         'images/toast_cheese.jpg'),
        ('Гречка с сыром', f"{product_ids['Гречка (вар.)']}:1.5,{product_ids['Сыр твердый']}:0.3", 'Завтрак',
         'images/buckwheat_cheese.jpg'),
        ('Йогурт с бананом', f"{product_ids['Йогурт натуральный']}:2,{product_ids['Банан']}:1", 'Завтрак',
         'images/yogurt_banana.jpg'),

        # --- ОБЕД (6 блюд) ---
        ('Курица с рисом и огурцом',
         f"{product_ids['Куриное филе (вар.)']}:2,{product_ids['Рис (вар.)']}:1.5,{product_ids['Огурец свежий']}:1",
         'Обед', 'images/chicken_rice.jpg'),
        ('Индейка с картофелем и томатами',
         f"{product_ids['Индейка (вар.)']}:1.5,{product_ids['Картофель (вар.)']}:2,{product_ids['Томаты']}:1", 'Обед',
         'images/turkey_potato.jpg'),
        ('Лосось с гречкой', f"{product_ids['Лосось (запеч.)']}:1.5,{product_ids['Гречка (вар.)']}:1.5", 'Обед',
         'images/salmon_buckwheat.jpg'),
        ('Паста с курицей', f"{product_ids['Макароны (вар.)']}:2,{product_ids['Куриное филе (вар.)']}:1", 'Обед',
         'images/pasta_chicken.jpg'),
        ('Картофель с сыром и сметаной',
         f"{product_ids['Картофель (вар.)']}:2,{product_ids['Сыр твердый']}:0.5,{product_ids['Сметана 15%']}:0.5",
         'Обед', 'images/potato_sourcream.jpg'),
        ('Творожный обед с яблоком',
         f"{product_ids['Творог 5%']}:1,{product_ids['Сметана 15%']}:1,{product_ids['Яблоко']}:1", 'Обед',
         'images/cottage_lunch.jpg'),

        # --- УЖИН (5 блюд) ---
        ('Индейка и салат из огурцов', f"{product_ids['Индейка (вар.)']}:2,{product_ids['Огурец свежий']}:1.5", 'Ужин',
         'images/turkey_salad.jpg'),
        ('Легкий салат с лососем',
         f"{product_ids['Лосось (запеч.)']}:1,{product_ids['Томаты']}:1,{product_ids['Огурец свежий']}:1", 'Ужин',
         'images/salmon_salad.jpg'),
        ('Курица с томатами', f"{product_ids['Куриное филе (вар.)']}:1.5,{product_ids['Томаты']}:1.5", 'Ужин',
         'images/chicken_tomatoes.jpg'),
        (
        'Творог на ночь', f"{product_ids['Творог 5%']}:2,{product_ids['Мёд']}:0.1", 'Ужин', 'images/cottage_night.jpg'),
        ('Гречка со сметаной', f"{product_ids['Гречка (вар.)']}:2,{product_ids['Сметана 15%']}:0.5", 'Ужин',
         'images/buckwheat_sourcream.jpg'),

        # --- ПЕРЕКУС (3 блюда) ---
        ('Банан', f"{product_ids['Банан']}:1", 'Перекус', 'images/banana.jpg'),
        ('Яблоко', f"{product_ids['Яблоко']}:1", 'Перекус', 'images/apple.jpg'),
        ('Порция фисташек', f"{product_ids['Фисташки']}:0.5", 'Перекус', 'images/pistachios.jpg'),
    ]

    cursor.executemany('''
        INSERT INTO Dishes (name, composition, application, image_path)
        VALUES (?, ?, ?, ?)
    ''', dishes_data)

    conn.commit()
    conn.close()

    print(f"База данных '{DB_NAME}' успешно создана и наполнена 20 блюдами и {len(products_data)} продуктами.")


if __name__ == '__main__':
    create_and_populate_db()