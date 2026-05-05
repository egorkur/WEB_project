from flask import Flask, render_template, request, redirect, send_file
import sqlite3
import csv
import io
import json
from itertools import combinations
from urllib.parse import quote

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nutrition_secret_key'
DB_NAME = 'nutrition.db'

# Коэффициенты для расчета калорий
ACTIVITY_FACTORS = {
    'Минимальная (сидячая работа)': 1.2,
    'Легкая (тренировки 1-3 раза в нед)': 1.375,
    'Средняя (тренировки 3-5 раз в нед)': 1.55,
    'Высокая (тяжелые тренировки 6-7 раз в нед)': 1.725,
    'Экстремальная (очень тяжелая работа/тренировки)': 1.9
}

GOAL_FACTORS = {
    'Похудеть (дефицит ~20%)': 0.8,
    'Сохранить вес': 1.0,
    'Набрать массу (профицит ~20%)': 1.2
}

MEAL_SCHEDULES = {
    3: ['Завтрак', 'Обед', 'Ужин'],
    4: ['Завтрак', 'Обед', 'Перекус', 'Ужин'],
    5: ['Завтрак', 'Перекус', 'Обед', 'Перекус', 'Ужин']
}

CALORIE_DISTRIBUTION = {
    3: [0.30, 0.40, 0.30],
    4: [0.30, 0.35, 0.10, 0.25],
    5: [0.25, 0.10, 0.30, 0.10, 0.25]
}


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def load_products():
    conn = get_db()
    products = {}
    cursor = conn.execute('SELECT * FROM Products')
    for row in cursor:
        products[row['id']] = dict(row)
    conn.close()
    return products


def load_dishes():
    conn = get_db()
    dishes = {}
    cursor = conn.execute('SELECT * FROM Dishes')
    for row in cursor:
        dish = dict(row)
        total_prot, total_fat, total_carb, total_kcal = 0, 0, 0, 0
        products = load_products()
        if dish['composition']:
            for ingredient in dish['composition'].split(','):
                if ':' in ingredient:
                    try:
                        p_id_str, qty_str = ingredient.split(':')
                        p_id = int(p_id_str.strip())
                        qty = float(qty_str.strip())
                        if p_id in products and qty > 0:
                            product = products[p_id]
                            total_prot += product['protein'] * qty
                            total_fat += product['fat'] * qty
                            total_carb += product['carbs'] * qty
                            total_kcal += product['kcal'] * qty
                    except ValueError:
                        pass
        dish['total_prot'] = total_prot
        dish['total_fat'] = total_fat
        dish['total_carb'] = total_carb
        dish['total_kcal'] = total_kcal
        dishes[dish['id']] = dish
    conn.close()
    return dishes


def calculate_tdee(age, weight, height, sex, activity):
    # Формула Миффлина-Сан Жеора
    if sex == 'Мужской':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    return bmr * ACTIVITY_FACTORS[activity]


def find_best_dish_combination(meal_type, target_kcal, dishes):
    # Подбор оптимальной комбинации блюд для приема пищи
    candidates = [d for d in dishes.values() if d['application'] == meal_type]
    if not candidates:
        return []

    best_combo = []
    min_diff = float('inf')

    for k in [1, 2, 3]:
        if len(candidates) < k:
            continue
        for combo in combinations(candidates, k):
            combo_kcal = sum(d['total_kcal'] for d in combo)
            diff = abs(combo_kcal - target_kcal)
            if diff < min_diff:
                min_diff = diff
                best_combo = list(combo)

    return best_combo


def get_market_url(product_name):
    # Генерация ссылки на Яндекс.Маркет для продукта
    return f"https://market.yandex.ru/search?text={quote(product_name)}"


def get_estimated_price(product_name):
    # Примерные цены на продукты (руб. за порцию 100 г / 1 шт.)
    prices = {
        'Овсянка': 50, 'Молоко': 80, 'Мёд': 300, 'Яйцо': 100,
        'Творог': 120, 'Сыр': 400, 'Хлеб': 45, 'Йогурт': 60,
        'Банан': 80, 'Яблоко': 70, 'Куриное филе': 350, 'Индейка': 450,
        'Гречка': 90, 'Рис': 80, 'Макароны': 70, 'Картофель': 40,
        'Огурец': 60, 'Томаты': 100, 'Лосось': 800, 'Фисташки': 500,
        'Сметана': 100
    }
    for key, price in prices.items():
        if key.lower() in product_name.lower():
            return price
    return 150


def calculate_total_price(plan, products_db):
    # Расчет примерной стоимости плана питания
    used_products = {}

    for meal_type, dishes in plan:
        for dish in dishes:
            if dish['composition']:
                for ingredient in dish['composition'].split(','):
                    if ':' in ingredient:
                        try:
                            p_id_str, qty_str = ingredient.split(':')
                            p_id = int(p_id_str.strip())
                            qty = float(qty_str.strip())
                            if p_id in products_db and qty > 0:
                                if p_id not in used_products:
                                    used_products[p_id] = {
                                        'name': products_db[p_id]['name'],
                                        'quantity': 0,
                                        'price_per_portion': get_estimated_price(products_db[p_id]['name'])
                                    }
                                used_products[p_id]['quantity'] += qty
                        except ValueError:
                            pass

    total_price = sum(data['price_per_portion'] * data['quantity'] for data in used_products.values())

    # Ссылка на Яндекс.Маркет со всеми продуктами
    product_names = [data['name'] for data in used_products.values()]
    market_url = f"https://market.yandex.ru/search?text={quote('+'.join(product_names))}"

    return int(total_price), market_url


@app.route('/')
def index():
    return render_template('calculator.html',
                           activity_factors=ACTIVITY_FACTORS,
                           goal_factors=GOAL_FACTORS,
                           meal_schedules=MEAL_SCHEDULES)


@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        age = int(request.form['age'])
        weight = float(request.form['weight'])
        height = float(request.form['height'])
        sex = request.form['sex']
        activity = request.form['activity']
        goal = request.form['goal']
        num_meals = int(request.form['meals'])
    except (ValueError, KeyError):
        return render_template('calculator.html',
                               activity_factors=ACTIVITY_FACTORS,
                               goal_factors=GOAL_FACTORS,
                               meal_schedules=MEAL_SCHEDULES,
                               error='Ошибка ввода данных')

    tdee = calculate_tdee(age, weight, height, sex, activity)
    target_calories = tdee * GOAL_FACTORS[goal]

    meal_schedule = MEAL_SCHEDULES[num_meals]
    calorie_distribution = CALORIE_DISTRIBUTION[num_meals]

    dishes = load_dishes()
    products = load_products()

    plan = []
    for i, meal_type in enumerate(meal_schedule):
        meal_target_kcal = target_calories * calorie_distribution[i]
        combo = find_best_dish_combination(meal_type, meal_target_kcal, dishes)
        plan.append((meal_type, combo))

    estimated_price, market_url = calculate_total_price(plan, products)

    # Сохранение плана для экспорта в CSV
    plan_json = []
    for meal_type, dishes_list in plan:
        meal_data = {
            'meal_type': meal_type,
            'dishes': []
        }
        for dish in dishes_list:
            meal_data['dishes'].append({
                'name': dish['name'],
                'kcal': round(dish['total_kcal'], 1),
                'prot': round(dish['total_prot'], 1),
                'fat': round(dish['total_fat'], 1),
                'carb': round(dish['total_carb'], 1)
            })
        plan_json.append(meal_data)

    return render_template('calculator.html',
                           activity_factors=ACTIVITY_FACTORS,
                           goal_factors=GOAL_FACTORS,
                           meal_schedules=MEAL_SCHEDULES,
                           plan=plan,
                           target_calories=target_calories,
                           estimated_price=estimated_price,
                           market_url=market_url,
                           plan_json=json.dumps(plan_json),
                           products=products)


@app.route('/catalog')
def catalog():
    dishes = load_dishes()
    products = load_products()
    return render_template('catalog.html', dishes=dishes, products=products)


@app.route('/editor')
def editor():
    products = load_products()
    applications = ['Завтрак', 'Обед', 'Ужин', 'Перекус']
    return render_template('editor.html', products=products, applications=applications)


@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['name']
    portion = request.form['portion']
    prot = float(request.form['prot'])
    fat = float(request.form['fat'])
    carb = float(request.form['carb'])
    kcal = float(request.form['kcal'])

    conn = get_db()
    conn.execute(
        'INSERT INTO Products (name, portion_volume, protein, fat, carbs, kcal) VALUES (?, ?, ?, ?, ?, ?)',
        (name, portion, prot, fat, carb, kcal)
    )
    conn.commit()
    conn.close()
    return redirect('/editor')


@app.route('/add_dish', methods=['POST'])
def add_dish():
    name = request.form['name']
    application = request.form['application']
    image_path = request.form.get('image_path', 'images/default.jpg')

    ingredients = []
    for key, value in request.form.items():
        if key.startswith('qty_') and float(value) > 0:
            prod_id = key.split('_')[1]
            ingredients.append(f"{prod_id}:{value}")

    composition = ','.join(ingredients)

    conn = get_db()
    conn.execute(
        'INSERT INTO Dishes (name, composition, application, image_path) VALUES (?, ?, ?, ?)',
        (name, composition, application, image_path)
    )
    conn.commit()
    conn.close()
    return redirect('/catalog')


@app.route('/delete_dish/<int:id>')
def delete_dish(id):
    conn = get_db()
    conn.execute('DELETE FROM Dishes WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect('/catalog')


@app.route('/delete_product/<int:id>')
def delete_product(id):
    conn = get_db()
    conn.execute('DELETE FROM Products WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect('/catalog')


@app.route('/export_csv')
def export_csv():
    plan_json = request.args.get('plan')
    if not plan_json:
        return redirect('/')

    plan = json.loads(plan_json)

    si = io.StringIO()
    writer = csv.writer(si, delimiter=';')
    writer.writerow(['Прием пищи', 'Блюдо', 'Ккал', 'Белки (г)', 'Жиры (г)', 'Углеводы (г)'])

    total_kcal = total_prot = total_fat = total_carb = 0

    for meal in plan:
        for dish in meal['dishes']:
            writer.writerow([meal['meal_type'], dish['name'], dish['kcal'],
                             dish['prot'], dish['fat'], dish['carb']])
            total_kcal += dish['kcal']
            total_prot += dish['prot']
            total_fat += dish['fat']
            total_carb += dish['carb']

    writer.writerow([])
    writer.writerow(['ИТОГО ЗА ДЕНЬ', '', round(total_kcal, 1),
                     round(total_prot, 1), round(total_fat, 1), round(total_carb, 1)])

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)

    return send_file(output, mimetype='text/csv', as_attachment=True,
                     download_name='план_питания.csv')


if __name__ == '__main__':
    app.run(debug=True)
