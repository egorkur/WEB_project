from flask import Flask, render_template, request, redirect, send_file, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import csv
import io
import json
from itertools import combinations
from urllib.parse import quote

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nutrition_secret_key_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nutrition.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/images', exist_ok=True)

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


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    portion_volume = db.Column(db.String(50), nullable=False)
    protein = db.Column(db.Float, nullable=False)
    fat = db.Column(db.Float, nullable=False)
    carbs = db.Column(db.Float, nullable=False)
    kcal = db.Column(db.Float, nullable=False)


class Dish(db.Model):
    __tablename__ = 'dishes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    composition = db.Column(db.Text, nullable=False)
    application = db.Column(db.String(50), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def get_nutrition(dish):
    total_kcal = total_prot = total_fat = total_carb = 0
    if dish.composition:
        for ing in dish.composition.split(','):
            if ':' in ing:
                try:
                    pid, qty = ing.split(':')
                    p = Product.query.get(int(pid.strip()))
                    q = float(qty.strip())
                    if p and q > 0:
                        total_kcal += p.kcal * q
                        total_prot += p.protein * q
                        total_fat += p.fat * q
                        total_carb += p.carbs * q
                except:
                    pass
    return total_kcal, total_prot, total_fat, total_carb


def get_price(name):
    prices = {
        'Овсянка': 50, 'Молоко': 80, 'Мёд': 300, 'Яйцо': 100,
        'Творог': 120, 'Сыр': 400, 'Хлеб': 45, 'Йогурт': 60,
        'Банан': 80, 'Яблоко': 70, 'Куриное филе': 350, 'Индейка': 450,
        'Гречка': 90, 'Рис': 80, 'Макароны': 70, 'Картофель': 40,
        'Огурец': 60, 'Томаты': 100, 'Лосось': 800, 'Фисташки': 500,
        'Сметана': 100
    }
    for k, v in prices.items():
        if k.lower() in name.lower():
            return v
    return 150


def calc_tdee(age, weight, height, sex, activity):
    if sex == 'Мужской':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    return bmr * ACTIVITY_FACTORS[activity]


def find_best(meal_type, target_kcal, dishes):
    candidates = []
    for d in dishes:
        kcal, _, _, _ = get_nutrition(d)
        d.kcal_value = kcal
        if d.application == meal_type:
            candidates.append(d)

    if not candidates:
        return []

    best = []
    best_diff = float('inf')

    for k in [1, 2, 3]:
        if len(candidates) < k:
            continue
        for combo in combinations(candidates, k):
            total = sum(d.kcal_value for d in combo)
            diff = abs(total - target_kcal)
            if diff < best_diff:
                best_diff = diff
                best = list(combo)

    return best


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
    except:
        return render_template('calculator.html',
                               activity_factors=ACTIVITY_FACTORS,
                               goal_factors=GOAL_FACTORS,
                               meal_schedules=MEAL_SCHEDULES,
                               error='Ошибка ввода')

    tdee = calc_tdee(age, weight, height, sex, activity)
    target = tdee * GOAL_FACTORS[goal]

    schedule = MEAL_SCHEDULES[num_meals]
    distribution = CALORIE_DISTRIBUTION[num_meals]

    dishes = Dish.query.all()
    products = {p.id: p for p in Product.query.all()}

    plan = []
    all_kcal = 0

    for i, meal_type in enumerate(schedule):
        meal_kcal = target * distribution[i]
        combo = find_best(meal_type, meal_kcal, dishes)

        meal_dishes = []
        for d in combo:
            kcal, prot, fat, carb = get_nutrition(d)
            meal_dishes.append({
                'name': d.name,
                'kcal': round(kcal, 1),
                'prot': round(prot, 1),
                'fat': round(fat, 1),
                'carb': round(carb, 1),
                'composition': d.composition
            })
            all_kcal += kcal

        plan.append((meal_type, meal_dishes))

    total_price = int(all_kcal * 2.5)
    market_url = "https://market.yandex.ru/search?text=продукты+для+правильного+питания"

    return render_template('calculator.html',
                           activity_factors=ACTIVITY_FACTORS,
                           goal_factors=GOAL_FACTORS,
                           meal_schedules=MEAL_SCHEDULES,
                           plan=plan,
                           target_calories=round(target, 1),
                           estimated_price=total_price,
                           all_kcal=round(all_kcal, 1),
                           market_url=market_url,
                           products=products)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Пользователь уже существует', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.password_hash = generate_password_hash(password)
        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Войдите.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Вы вошли!', 'success')
            return redirect(url_for('index'))

        flash('Неверный логин или пароль', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/catalog')
def catalog():
    dishes = Dish.query.all()
    products = {p.id: p for p in Product.query.all()}
    return render_template('catalog.html', dishes=dishes, products=products)


@app.route('/editor')
@login_required
def editor():
    products = Product.query.all()
    return render_template('editor.html', products=products)


@app.route('/add_product', methods=['POST'])
@login_required
def add_product():
    p = Product(
        name=request.form['name'],
        portion_volume=request.form['portion'],
        protein=float(request.form['prot']),
        fat=float(request.form['fat']),
        carbs=float(request.form['carb']),
        kcal=float(request.form['kcal'])
    )
    db.session.add(p)
    db.session.commit()
    flash('Продукт добавлен!', 'success')
    return redirect('/editor')


@app.route('/add_dish', methods=['POST'])
@login_required
def add_dish():
    image_path = 'static/images/default.jpg'
    if 'image' in request.files:
        file = request.files['image']
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f'static/uploads/{filename}'

    ingredients = []
    for key, value in request.form.items():
        if key.startswith('qty_') and float(value) > 0:
            pid = key.split('_')[1]
            ingredients.append(f"{pid}:{value}")

    d = Dish(
        name=request.form['name'],
        composition=','.join(ingredients),
        application=request.form['application'],
        image_path=image_path
    )
    db.session.add(d)
    db.session.commit()
    flash('Блюдо добавлено!', 'success')
    return redirect('/catalog')


@app.route('/delete_dish/<int:id>')
@login_required
def delete_dish(id):
    Dish.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect('/catalog')


@app.route('/delete_product/<int:id>')
@login_required
def delete_product(id):
    Product.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect('/catalog')


@app.route('/export_csv')
def export_csv():
    plan = json.loads(request.args.get('plan', '[]'))

    si = io.StringIO()
    writer = csv.writer(si, delimiter=';')
    writer.writerow(['Прием пищи', 'Блюдо', 'Ккал', 'Белки', 'Жиры', 'Углеводы'])

    for meal in plan:
        for dish in meal['dishes']:
            writer.writerow([meal['meal_type'], dish['name'], dish['kcal'],
                             dish['prot'], dish['fat'], dish['carb']])

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)

    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='план.csv')


if os.path.exists('nutrition.db'):
    os.remove('nutrition.db')

with app.app_context():
    db.create_all()

    products_data = [
        ('Яйцо', '1 шт', 6.0, 5.0, 0.5, 74.0),
        ('Овсянка (сухая)', '100 г', 11.9, 6.9, 66.2, 389.0),
        ('Молоко 2.5%', '100 мл', 3.0, 2.5, 4.7, 54.0),
        ('Куриное филе (вар.)', '100 г', 31.0, 3.6, 0.0, 165.0),
        ('Рис (вар.)', '100 г', 2.6, 0.3, 28.2, 130.0),
        ('Огурец свежий', '100 г', 0.7, 0.1, 3.6, 15.0),
        ('Хлеб пшеничный', '100 г', 7.5, 2.9, 48.8, 265.0),
        ('Творог 5%', '100 г', 16.0, 5.0, 2.0, 121.0),
        ('Сыр твердый', '100 г', 25.0, 30.0, 0.0, 370.0),
        ('Яблоко', '1 шт', 0.4, 0.4, 11.8, 52.0),
        ('Банан', '1 шт', 1.1, 0.3, 22.8, 89.0),
        ('Гречка (вар.)', '100 г', 3.4, 1.0, 17.0, 92.0),
        ('Индейка (вар.)', '100 г', 25.0, 1.0, 0.0, 135.0),
        ('Макароны (вар.)', '100 г', 5.0, 1.0, 25.0, 150.0),
        ('Томаты', '100 г', 0.9, 0.2, 3.9, 20.0),
        ('Лосось (запеч.)', '100 г', 20.0, 12.0, 0.0, 208.0),
        ('Сметана 15%', '100 г', 2.6, 15.0, 3.0, 175.0),
        ('Йогурт натуральный', '100 г', 5.0, 3.2, 4.1, 68.0),
        ('Мёд', '100 г', 0.3, 0.0, 82.4, 329.0),
        ('Картофель (вар.)', '100 г', 2.0, 0.1, 18.0, 86.0),
        ('Фисташки', '100 г', 20.0, 45.0, 28.0, 560.0),
    ]

    for name, portion, prot, fat, carb, kcal in products_data:
        db.session.add(Product(name=name, portion_volume=portion, protein=prot, fat=fat, carbs=carb, kcal=kcal))

    db.session.commit()

    products = {p.name: p.id for p in Product.query.all()}

    dishes_data = [
        ('Омлет', f"{products['Яйцо']}:2,{products['Молоко 2.5%']}:0.5", 'Завтрак', 'static/images/omelet.jpg'),
        ('Овсянка с молоком', f"{products['Овсянка (сухая)']}:0.5,{products['Молоко 2.5%']}:1.5", 'Завтрак',
         'static/images/oatmeal.jpg'),
        ('Творог с яблоком', f"{products['Творог 5%']}:1.5,{products['Яблоко']}:1", 'Завтрак', 'static/images'
                                                                                               '/cottage_cheese.jpg'),
        ('Тосты с сыром', f"{products['Хлеб пшеничный']}:2,{products['Сыр твердый']}:0.5", 'Завтрак',
         'static/images/toast_cheese.jpg'),
        ('Гречка с сыром', f"{products['Гречка (вар.)']}:1.5,{products['Сыр твердый']}:0.3", 'Завтрак',
         'static/images/buckwheat_cheese.jpg'),
        ('Йогурт с бананом', f"{products['Йогурт натуральный']}:2,{products['Банан']}:1", 'Завтрак',
         'static/images/yogurt_banana.jpg'),
        ('Курица с рисом и огурцом', f"{products['Куриное филе (вар.)']}:2,{products['Рис (вар.)']}:1.5,"
                                     f"{products['Огурец свежий']}:1", 'Обед', 'static/images/chicken_rice.jpg'),
        ('Индейка с картофелем',
         f"{products['Индейка (вар.)']}:1.5,{products['Картофель (вар.)']}:2,{products['Томаты']}:1",
         'Обед', 'static/images/turkey_potato.jpg'),
        ('Лосось с гречкой', f"{products['Лосось (запеч.)']}:1.5,{products['Гречка (вар.)']}:1.5", 'Обед',
         'static/images/salmon_buckwheat.jpg'),
        ('Паста с курицей', f"{products['Макароны (вар.)']}:2,{products['Куриное филе (вар.)']}:1", 'Обед',
         'static/images/pasta_chicken.jpg'),
        ('Картофель с сыром', f"{products['Картофель (вар.)']}:2,{products['Сыр твердый']}:0.5,"
                              f"{products['Сметана 15%']}:0.5", 'Обед', 'static/images/potato_sourcream.jpg'),
        ('Творожный обед', f"{products['Творог 5%']}:1,{products['Сметана 15%']}:1,{products['Яблоко']}:1", 'Обед',
         'static/images/cottage_lunch.jpg'),
        ('Индейка с огурцами', f"{products['Индейка (вар.)']}:2,{products['Огурец свежий']}:1.5", 'Ужин',
         'static/images/turkey_salad.jpg'),
        ('Салат с лососем', f"{products['Лосось (запеч.)']}:1,{products['Томаты']}:1,{products['Огурец свежий']}:1",
         'Ужин', 'static/images/salmon_salad.jpg'),
        ('Курица с томатами', f"{products['Куриное филе (вар.)']}:1.5,{products['Томаты']}:1.5", 'Ужин',
         'static/images/chicken_tomatoes.jpg'),
        ('Творог с мёдом', f"{products['Творог 5%']}:2,{products['Мёд']}:0.1", 'Ужин',
         'static/images/cottage_night.jpg'),
        ('Гречка со сметаной', f"{products['Гречка (вар.)']}:2,{products['Сметана 15%']}:0.5", 'Ужин',
         'static/images/buckwheat_sourcream.jpg'),
        ('Банан', f"{products['Банан']}:1", 'Перекус', 'static/images/banana.jpg'),
        ('Яблоко', f"{products['Яблоко']}:1", 'Перекус', 'static/images/apple.jpg'),
        ('Фисташки', f"{products['Фисташки']}:0.5", 'Перекус', 'static/images/pistachios.jpg'),
    ]

    for name, comp, app_type, img in dishes_data:
        db.session.add(Dish(name=name, composition=comp, application=app_type, image_path=img))

    db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)
