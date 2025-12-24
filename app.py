import os
import logging
import threading
import time
from flask import Flask, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import requests
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем Flask приложение
app = Flask(__name__)

# ВАШИ ДАННЫЕ - теперь из переменных окружения
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'suvtekin-secret-key-2024-muha-muhamed')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8586126815:AAHAGyah7Oz-8mHzUcFvRcHV3Dsug3sPT4g')
TELEGRAM_ADMIN_ID = os.environ.get('TELEGRAM_ADMIN_ID', '6349730260')

# База данных
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///cars.db').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализируем базу данных
db = SQLAlchemy(app)

# Модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    telegram_id = db.Column(db.String(50))
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)

class Brand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return self.name

class CarModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey('brand.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    brand = db.relationship('Brand', backref='models')
    
    def __repr__(self):
        return self.name

class Manager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    telegram_username = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return self.name

class PriceCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    min_price_usd = db.Column(db.Float)
    max_price_usd = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return self.name

class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price_usd = db.Column(db.Float, nullable=False)
    price_category_id = db.Column(db.Integer, db.ForeignKey('price_category.id'))
    brand_id = db.Column(db.Integer, db.ForeignKey('brand.id'))
    model_id = db.Column(db.Integer, db.ForeignKey('car_model.id'))
    year = db.Column(db.Integer)
    mileage_km = db.Column(db.Integer)
    fuel_type = db.Column(db.String(50))
    transmission = db.Column(db.String(50))
    color = db.Column(db.String(50))
    engine_capacity = db.Column(db.Float)
    photo_url = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    price_category = db.relationship('PriceCategory')
    brand = db.relationship('Brand')
    model = db.relationship('CarModel')
    
    def __repr__(self):
        return f'{self.title}'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('car.id'))
    telegram_user_id = db.Column(db.String(50))
    telegram_username = db.Column(db.String(100))
    telegram_first_name = db.Column(db.String(100))
    full_name = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    car = db.relationship('Car')

class SellRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.String(50))
    telegram_username = db.Column(db.String(100))
    telegram_first_name = db.Column(db.String(100))
    
    car_brand = db.Column(db.String(100))
    car_model = db.Column(db.String(100))
    car_year = db.Column(db.Integer)
    car_mileage = db.Column(db.Integer)
    car_price = db.Column(db.Float)
    car_description = db.Column(db.Text)
    
    phone = db.Column(db.String(50))
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Создаем таблицы
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Таблицы базы данных созданы")
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")

    # Создаем админа если нет
    if not User.query.filter_by(username='muha').first():
        try:
            admin = User(
                username='muha',
                password=generate_password_hash('muhamed'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            logger.info("✅ Создан администратор muha")
        except Exception as e:
            logger.error(f"❌ Ошибка создания администратора: {e}")
            db.session.rollback()
    
    # Создаем ценовые категории если нет
    if PriceCategory.query.count() == 0:
        try:
            categories = [
                ('0-3000$', 0, 3000),
                ('3000-6000$', 3000, 6000),
                ('6000-10000$', 6000, 10000),
                ('10000-20000$', 10000, 20000),
                ('20000+$', 20000, 1000000)
            ]
            
            for name, min_p, max_p in categories:
                if not PriceCategory.query.filter_by(name=name).first():
                    category = PriceCategory(
                        name=name,
                        min_price_usd=min_p,
                        max_price_usd=max_p
                    )
                    db.session.add(category)
            
            db.session.commit()
            logger.info(f"✅ Создано {len(categories)} ценовых категорий")
        except Exception as e:
            logger.error(f"❌ Ошибка создания ценовых категорий: {e}")
            db.session.rollback()
    
    # Создаем бренды если нет
    if Brand.query.count() == 0:
        try:
            brands = ['Toyota', 'Honda', 'BMW', 'Chevrolet', 'Mazda', 'Ford', 'Hyundai', 'Kia', 'Mercedes', 'Audi']
            for brand_name in brands:
                if not Brand.query.filter_by(name=brand_name).first():
                    brand = Brand(name=brand_name)
                    db.session.add(brand)
            
            db.session.commit()
            logger.info(f"✅ Создано {len(brands)} брендов")
        except Exception as e:
            logger.error(f"❌ Ошибка создания брендов: {e}")
            db.session.rollback()
    
    # Создаем модели если нет
    if CarModel.query.count() == 0:
        try:
            models_data = [
                ('Camry', 'Toyota'),
                ('Corolla', 'Toyota'),
                ('RAV4', 'Toyota'),
                ('Civic', 'Honda'),
                ('Accord', 'Honda'),
                ('CR-V', 'Honda'),
                ('X5', 'BMW'),
                ('3 Series', 'BMW'),
                ('Malibu', 'Chevrolet'),
                ('Camaro', 'Chevrolet'),
                ('CX-5', 'Mazda'),
                ('Mazda3', 'Mazda'),
                ('Focus', 'Ford'),
                ('F-150', 'Ford')
            ]
            
            for model_name, brand_name in models_data:
                brand = Brand.query.filter_by(name=brand_name).first()
                if brand and not CarModel.query.filter_by(name=model_name, brand_id=brand.id).first():
                    car_model = CarModel(name=model_name, brand_id=brand.id)
                    db.session.add(car_model)
            
            db.session.commit()
            logger.info(f"✅ Создано {len(models_data)} моделей")
        except Exception as e:
            logger.error(f"❌ Ошибка создания моделей: {e}")
            db.session.rollback()
    
    # Создаем менеджеров если нет
    if Manager.query.count() == 0:
        try:
            managers = [
                ('Мухаммед', 'muhamed', '+996 555 123 456', 'info@suvtekin.kg'),
                ('Алишер', 'alisher_auto', '+996 555 789 012', 'sales@suvtekin.kg'),
                ('Айгерим', 'aigerim_cars', '+996 555 345 678', 'support@suvtekin.kg')
            ]
            
            for name, telegram, phone, email in managers:
                if not Manager.query.filter_by(name=name).first():
                    manager = Manager(
                        name=name,
                        telegram_username=telegram,
                        phone=phone,
                        email=email
                    )
                    db.session.add(manager)
            
            db.session.commit()
            logger.info(f"✅ Создано {len(managers)} менеджеров")
        except Exception as e:
            logger.error(f"❌ Ошибка создания менеджеров: {e}")
            db.session.rollback()
    
    # Создаем примерные автомобили если нет
    if Car.query.count() == 0:
        try:
            # Получаем первые 5 брендов и модели
            brands = Brand.query.limit(5).all()
            
            for i, brand in enumerate(brands):
                models = CarModel.query.filter_by(brand_id=brand.id).limit(2).all()
                
                for j, model in enumerate(models):
                    car = Car(
                        title=f'{brand.name} {model.name} {2020 - i}',
                        description=f'Отличное состояние, полная комплектация. {["Первый владелец", "Без ДТП", "Обслужен у дилера"][j%3]}.',
                        price_usd=15000 + (i * 5000) + (j * 2000),
                        brand_id=brand.id,
                        model_id=model.id,
                        year=2020 - i,
                        mileage_km=30000 + (i * 10000) + (j * 5000),
                        fuel_type=['Бензин', 'Дизель'][i % 2],
                        transmission=['Автомат', 'Механика'][j % 2],
                        color=['Черный', 'Белый', 'Серый', 'Синий'][(i+j) % 4],
                        engine_capacity=1.8 + (i * 0.3),
                        photo_url='https://images.unsplash.com/photo-1549399542-7e3f8b79c341?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
                        is_active=True
                    )
                    db.session.add(car)
            
            db.session.commit()
            logger.info(f"✅ Создано {Car.query.count()} автомобилей")
        except Exception as e:
            logger.error(f"❌ Ошибка создания автомобилей: {e}")
            db.session.rollback()

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ИСПРАВЛЕННЫЕ ModelView для админки - Теперь с правильными формами
class CarModelView(ModelView):
    column_list = ['id', 'title', 'price_usd', 'brand', 'model', 'year', 'is_active']
    column_searchable_list = ['title']
    column_filters = ['year', 'is_active', 'price_usd']
    column_labels = {
        'price_usd': 'Цена ($)',
        'mileage_km': 'Пробег (км)',
        'brand': 'Бренд',
        'model': 'Модель'
    }
    
    # ВАЖНО: Правильные поля формы
    form_columns = ['title', 'description', 'price_usd', 'price_category', 'brand', 'model', 
                   'year', 'mileage_km', 'fuel_type', 'transmission', 'color', 
                   'engine_capacity', 'photo_url', 'is_active']
    
    # ВАЖНО: Разрешаем создание, редактирование, удаление
    can_create = True
    can_edit = True
    can_delete = True
    can_export = True
    can_view_details = True
    
    # Упрощенные настройки формы
    form_choices = {
        'fuel_type': [
            ('Бензин', 'Бензин'),
            ('Дизель', 'Дизель'),
            ('Газ', 'Газ'),
            ('Электричество', 'Электричество'),
            ('Гибрид', 'Гибрид')
        ],
        'transmission': [
            ('Автомат', 'Автомат'),
            ('Механика', 'Механика'),
            ('Вариатор', 'Вариатор'),
            ('Робот', 'Робот')
        ],
        'color': [
            ('Черный', 'Черный'),
            ('Белый', 'Белый'),
            ('Серый', 'Серый'),
            ('Синий', 'Синий'),
            ('Красный', 'Красный'),
            ('Зеленый', 'Зеленый'),
            ('Желтый', 'Желтый'),
            ('Серебристый', 'Серебристый')
        ]
    }
    
    form_args = {
        'title': {
            'label': 'Название автомобиля',
            'description': 'Например: Toyota Camry 2020'
        },
        'price_usd': {
            'label': 'Цена в USD',
            'description': 'Введите цену в долларах'
        },
        'year': {
            'label': 'Год выпуска',
            'description': 'Например: 2020'
        },
        'mileage_km': {
            'label': 'Пробег (км)',
            'description': 'Введите пробег в километрах'
        },
        'engine_capacity': {
            'label': 'Объем двигателя (л)',
            'description': 'Например: 2.0'
        }
    }
    
    form_widget_args = {
        'description': {
            'rows': 5,
            'style': 'width: 100%'
        },
        'photo_url': {
            'placeholder': 'https://example.com/photo.jpg',
            'style': 'width: 100%'
        },
        'title': {
            'style': 'width: 100%'
        }
    }
    
    def on_model_change(self, form, model, is_created):
        # Автоматически определяем ценовую категорию
        if model.price_usd is not None:
            categories = PriceCategory.query.filter_by(is_active=True).all()
            for category in categories:
                if category.min_price_usd <= model.price_usd <= category.max_price_usd:
                    model.price_category_id = category.id
                    break
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class BrandModelView(ModelView):
    column_list = ['id', 'name', 'is_active', 'created_at']
    form_columns = ['name', 'is_active']
    column_searchable_list = ['name']
    column_filters = ['is_active']
    
    # ВАЖНО: Разрешаем создание
    can_create = True
    can_edit = True
    can_delete = True
    
    form_args = {
        'name': {
            'label': 'Название бренда',
            'description': 'Например: Toyota, BMW'
        }
    }
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class CarModelModelView(ModelView):
    column_list = ['id', 'name', 'brand', 'is_active', 'created_at']
    form_columns = ['name', 'brand', 'is_active']
    column_searchable_list = ['name']
    column_filters = ['is_active', 'brand']
    
    # ВАЖНО: Разрешаем создание
    can_create = True
    can_edit = True
    can_delete = True
    
    form_args = {
        'name': {
            'label': 'Название модели',
            'description': 'Например: Camry, X5'
        }
    }
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class ManagerModelView(ModelView):
    column_list = ['id', 'name', 'telegram_username', 'phone', 'email', 'is_active']
    form_columns = ['name', 'telegram_username', 'phone', 'email', 'is_active']
    column_searchable_list = ['name', 'phone']
    column_filters = ['is_active']
    
    # ВАЖНО: Разрешаем создание
    can_create = True
    can_edit = True
    can_delete = True
    
    form_widget_args = {
        'name': {
            'placeholder': 'Имя менеджера',
            'style': 'width: 100%'
        },
        'telegram_username': {
            'placeholder': '@username (без @)',
            'style': 'width: 100%'
        },
        'phone': {
            'placeholder': '+996 555 123 456',
            'style': 'width: 100%'
        },
        'email': {
            'placeholder': 'example@email.com',
            'style': 'width: 100%'
        }
    }
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class OrderModelView(ModelView):
    column_list = ['id', 'car', 'full_name', 'phone', 'status', 'created_at']
    form_columns = ['status', 'phone', 'full_name']
    column_filters = ['status', 'created_at']
    column_searchable_list = ['full_name', 'phone']
    
    can_create = False  # Заказы создаются только через бота
    can_edit = True
    can_delete = True
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class SellRequestModelView(ModelView):
    column_list = ['id', 'car_brand', 'car_model', 'car_year', 'car_price', 'phone', 'status', 'created_at']
    form_columns = ['status', 'phone']
    column_filters = ['status', 'created_at']
    column_searchable_list = ['car_brand', 'car_model', 'phone']
    
    can_create = False  # Заявки создаются только через бота
    can_edit = True
    can_delete = True
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class PriceCategoryModelView(ModelView):
    column_list = ['id', 'name', 'min_price_usd', 'max_price_usd', 'is_active']
    form_columns = ['name', 'min_price_usd', 'max_price_usd', 'is_active']
    column_searchable_list = ['name']
    column_filters = ['is_active']
    
    # ВАЖНО: Разрешаем создание
    can_create = True
    can_edit = True
    can_delete = True
    
    form_widget_args = {
        'name': {
            'placeholder': '0-3000$',
            'style': 'width: 100%'
        },
        'min_price_usd': {
            'placeholder': '0',
            'style': 'width: 100%'
        },
        'max_price_usd': {
            'placeholder': '3000',
            'style': 'width: 100%'
        }
    }
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class UserModelView(ModelView):
    column_list = ['id', 'username', 'role', 'telegram_id', 'created_at']
    form_columns = ['username', 'password', 'role', 'telegram_id']
    column_searchable_list = ['username']
    column_filters = ['role', 'created_at']
    
    # ВАЖНО: Разрешаем создание
    can_create = True
    can_edit = True
    can_delete = True
    
    form_widget_args = {
        'password': {
            'type': 'password',
            'style': 'width: 100%'
        },
        'telegram_id': {
            'placeholder': '1234567890',
            'style': 'width: 100%'
        },
        'username': {
            'style': 'width: 100%'
        }
    }
    
    def on_model_change(self, form, model, is_created):
        if form.password.data:
            model.password = generate_password_hash(form.password.data)
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

# Создаем админку
admin = Admin(app, name='Suvtekin Auto', template_mode='bootstrap3', url='/admin')
admin.add_view(CarModelView(Car, db.session, name='Автомобили', category='Авто'))
admin.add_view(BrandModelView(Brand, db.session, name='Бренды', category='Справочники'))
admin.add_view(CarModelModelView(CarModel, db.session, name='Модели', category='Справочники'))
admin.add_view(PriceCategoryModelView(PriceCategory, db.session, name='Категории цен', category='Справочники'))
admin.add_view(ManagerModelView(Manager, db.session, name='Менеджеры', category='Персонал'))
admin.add_view(OrderModelView(Order, db.session, name='Заказы', category='Заявки'))
admin.add_view(SellRequestModelView(SellRequest, db.session, name='Заявки на продажу', category='Заявки'))
admin.add_view(UserModelView(User, db.session, name='Пользователи', category='Система'))

# Роуты
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Успешный вход!', 'success')
            return redirect(url_for('admin.index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Вход - Suvtekin Auto</title>
        <style>
            body { font-family: Arial; background: #f5f5f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .login-container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
            h2 { color: #333; text-align: center; margin-bottom: 10px; }
            p { color: #666; text-align: center; margin-bottom: 30px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; color: #555; }
            input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            button { background: #007bff; color: white; border: none; padding: 12px 20px; border-radius: 5px; width: 100%; cursor: pointer; font-size: 16px; }
            button:hover { background: #0056b3; }
            .alert { padding: 10px; border-radius: 5px; margin-bottom: 20px; }
            .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .demo-creds { background: #e9ecef; padding: 10px; border-radius: 5px; margin-top: 20px; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2>🚗 Suvtekin Auto</h2>
            <p>Панель управления автосалоном</p>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            
            <form method="POST">
                <div class="form-group">
                    <label for="username">Логин</label>
                    <input type="text" id="username" name="username" value="muha" required>
                </div>
                
                <div class="form-group">
                    <label for="password">Пароль</label>
                    <input type="password" id="password" name="password" value="muhamed" required>
                </div>
                
                <button type="submit">Войти в систему</button>
            </form>
            
            <div class="demo-creds">
                <strong>Тестовые данные:</strong><br>
                Логин: <strong>muha</strong><br>
                Пароль: <strong>muhamed</strong>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('login'))

# TELEGRAM БОТ НА ВЕБХУКАХ (работает на Render)
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Словари для языков
TEXTS = {
    'ru': {
        'choose_language': 'Выберите язык:\n\nTilni tanlang:',
        'welcome': '🚗 Добро пожаловать в Suvtekin Auto!',
        'help': '📋 Используйте кнопки ниже для навигации',
        'main_menu': 'Главное меню:',
        'show_cars': '🚗 Посмотреть авто',
        'price_categories': '💰 Категории цен',
        'select_by_brand': '🏭 Поиск по марке',
        'contact_manager': '📞 Контакты',
        'sell_car': '💰 Продать авто',
        'help_btn': 'ℹ️ Помощь',
        'no_cars': '🚗 Автомобилей нет в наличии',
        'car_info': '🚗 *{title}*\n\n💰 *Цена:* ${price:,.0f}\n📏 *Пробег:* {mileage:,} км\n🏭 *Марка:* {brand}\n📅 *Год:* {year}\n⛽ *Топливо:* {fuel}\n⚙️ *КПП:* {transmission}\n🎨 *Цвет:* {color}\n🔧 *Объем:* {engine} л\n\n{description}',
        'order_btn': '🛒 Заказать',
        'order_phone': '📞 Введите ваш номер телефона для связи:',
        'order_success': '✅ Заказ оформлен! Менеджер свяжется с вами.',
        'choose_category': 'Выберите категорию цены:',
        'choose_brand': 'Выберите марку автомобиля:',
        'choose_model': 'Выберите модель:',
        'managers': '📞 *Наши менеджеры:*\n\n{managers}',
        'sell_car_welcome': '💰 *Продать автомобиль*\n\nВыберите марку вашего авто:',
        'other_brand': '➡️ Другая марка',
        'sell_car_model': 'Введите модель автомобиля:',
        'sell_car_year': 'Введите год выпуска автомобиля:',
        'sell_car_mileage': 'Введите пробег (в км):',
        'sell_car_price': 'Введите желаемую цену ($):',
        'sell_car_description': 'Опишите состояние автомобиля:',
        'sell_car_phone': 'Введите ваш номер телефона:',
        'sell_car_success': '✅ Заявка отправлена! Менеджер свяжется с вами.',
        'back': '🔙 Назад',
        'cancel': '❌ Отмена',
        'all_brands': 'Все марки',
        'error': '❌ Произошла ошибка. Попробуйте еще раз.'
    },
    'uz': {
        'choose_language': 'Tilni tanlang:\n\nВыберите язык:',
        'welcome': '🚗 Suvtekin Auto ga xush kelibsiz!',
        'help': '📋 Navigatsiya uchun pastdagi tugmalardan foydalaning',
        'main_menu': 'Asosiy menyu:',
        'show_cars': '🚗 Avtomobillarni ko\'rish',
        'price_categories': '💰 Narx kategoriyalari',
        'select_by_brand': '🏭 Marka bo\'yicha qidirish',
        'contact_manager': '📞 Kontaktlar',
        'sell_car': '💰 Avtomobil sotish',
        'help_btn': 'ℹ️ Yordam',
        'no_cars': '🚗 Mavjud avtomobillar yo\'q',
        'car_info': '🚗 *{title}*\n\n💰 *Narx:* ${price:,.0f}\n📏 *Yurgan:* {mileage:,} km\n🏭 *Marka:* {brand}\n📅 *Yil:* {year}\n⛽ *Yoqilg\'i:* {fuel}\n⚙️ *Uzatma:* {transmission}\n🎨 *Rang:* {color}\n🔧 *Hajm:* {engine} l\n\n{description}',
        'order_btn': '🛒 Buyurtma',
        'order_phone': '📞 Aloqa uchun telefon raqamingizni kiriting:',
        'order_success': '✅ Buyurtma qabul qilindi! Menejer siz bilan bog\'lanadi.',
        'choose_category': 'Narx kategoriyasini tanlang:',
        'choose_brand': 'Avtomobil markasini tanlang:',
        'choose_model': 'Modelni tanlang:',
        'managers': '📞 *Bizning menejerlarimiz:*\n\n{managers}',
        'sell_car_welcome': '💰 *Avtomobil sotish*\n\nAvtomobilingiz markasini tanlang:',
        'other_brand': '➡️ Boshqa marka',
        'sell_car_model': 'Avtomobil modelini kiriting:',
        'sell_car_year': 'Avtomobil ishlab chiqarilgan yilini kiriting:',
        'sell_car_mileage': 'Yurgan masofani kiriting (km):',
        'sell_car_price': 'Istalgan narxni kiriting ($):',
        'sell_car_description': 'Avtomobil holatini tasvirlang:',
        'sell_car_phone': 'Telefon raqamingizni kiriting:',
        'sell_car_success': '✅ Ariza yuborildi! Menejer siz bilan bog\'lanadi.',
        'back': '🔙 Orqaga',
        'cancel': '❌ Bekor qilish',
        'all_brands': 'Barcha markalar',
        'error': '❌ Xatolik yuz berdi. Qaytadan urinib ko\'ring.'
    }
}

# Словари для состояний (храним в памяти, для продакшена лучше Redis)
user_languages = {}
user_states = {}
user_data = {}

def get_language(chat_id):
    return user_languages.get(chat_id, 'ru')

def t(chat_id, key):
    return TEXTS[get_language(chat_id)].get(key, key)

def send_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    url = f"{BASE_URL}/sendMessage"
    params = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    try:
        response = requests.post(url, params=params, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return None

def send_photo(chat_id, photo_url, caption, reply_markup=None):
    url = f"{BASE_URL}/sendPhoto"
    params = {'chat_id': chat_id, 'photo': photo_url, 'caption': caption, 'parse_mode': 'Markdown'}
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    try:
        requests.post(url, params=params, timeout=10)
    except:
        pass

# Меню выбора языка
def get_language_menu():
    return {
        'keyboard': [
            ['🇷🇺 Русский', '🇺🇿 O\'zbek']
        ],
        'resize_keyboard': True,
        'one_time_keyboard': True
    }

# Главное меню
def get_main_menu(chat_id):
    keyboard = [
        [t(chat_id, 'show_cars'), t(chat_id, 'price_categories')],
        [t(chat_id, 'select_by_brand'), t(chat_id, 'contact_manager')],
        [t(chat_id, 'sell_car'), t(chat_id, 'help_btn')]
    ]
    return {
        'keyboard': keyboard,
        'resize_keyboard': True,
        'one_time_keyboard': False
    }

# Меню отмены
def get_cancel_menu(chat_id):
    return {
        'keyboard': [[t(chat_id, 'cancel')]],
        'resize_keyboard': True,
        'one_time_keyboard': True
    }

# Кнопка заказа
def get_order_button(chat_id, car_id):
    return {
        'inline_keyboard': [[
            {'text': t(chat_id, 'order_btn'), 'callback_data': f'order_{car_id}'}
        ]]
    }

# Основной обработчик вебхука
@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    try:
        update = request.get_json()
        
        if 'callback_query' in update:
            handle_callback(update['callback_query'])
        elif 'message' in update:
            handle_message(update['message'])
        
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Ошибка в вебхуке: {e}")
        return jsonify({'ok': False, 'error': str(e)})

def handle_callback(callback_query):
    try:
        data = callback_query['data']
        chat_id = callback_query['message']['chat']['id']
        username = callback_query['from'].get('username', '')
        first_name = callback_query['from'].get('first_name', '')
        
        if data == 'back_menu':
            send_message(chat_id, t(chat_id, 'main_menu'), get_main_menu(chat_id))
        
        elif data.startswith('order_'):
            car_id = int(data.split('_')[1])
            start_order(chat_id, car_id)
        
        elif data.startswith('cat_'):
            category_id = int(data.split('_')[1])
            show_cars(chat_id, 'category', category_id)
        
        # Ответ на callback
        url = f"{BASE_URL}/answerCallbackQuery"
        params = {'callback_query_id': callback_query['id']}
        requests.post(url, params=params)
        
    except Exception as e:
        logger.error(f"Ошибка callback: {e}")
        send_message(chat_id, t(chat_id, 'error'), get_main_menu(chat_id))

def handle_message(message):
    chat_id = message['chat']['id']
    text = message.get('text', '')
    username = message['chat'].get('username', '')
    first_name = message['chat'].get('first_name', '')
    
    # Проверяем выбран ли язык
    if chat_id not in user_languages:
        if text in ['🇷🇺 Русский', 'Русский', 'RU', 'ru', '/start']:
            handle_language_selection(chat_id, 'ru')
        elif text in ['🇺🇿 O\'zbek', 'O\'zbek', 'UZ', 'uz']:
            handle_language_selection(chat_id, 'uz')
        else:
            handle_start(chat_id, first_name)
        return
    
    # Получаем состояние пользователя
    state = user_states.get(chat_id, {})
    action = state.get('action')
    
    # Отмена
    if text == t(chat_id, 'cancel'):
        user_states.pop(chat_id, None)
        user_data.pop(chat_id, None)
        send_message(chat_id, t(chat_id, 'main_menu'), get_main_menu(chat_id))
        return
    
    # Обработка процесса продажи
    if action == 'sell_car':
        step = state.get('step')
        data = user_data.get(chat_id, {})
        
        if step == 'brand_other':
            # Пользователь вводит свою марку
            data['brand'] = text
            user_states[chat_id]['step'] = 'model'
            send_message(chat_id, t(chat_id, 'sell_car_model'), get_cancel_menu(chat_id))
        
        elif step == 'model':
            data['model'] = text
            user_states[chat_id]['step'] = 'year'
            send_message(chat_id, t(chat_id, 'sell_car_year'), get_cancel_menu(chat_id))
        
        elif step == 'year':
            try:
                data['year'] = int(text)
                user_states[chat_id]['step'] = 'mileage'
                send_message(chat_id, t(chat_id, 'sell_car_mileage'), get_cancel_menu(chat_id))
            except:
                send_message(chat_id, "Пожалуйста, введите правильный год (например: 2020)")
        
        elif step == 'mileage':
            try:
                data['mileage'] = int(text)
                user_states[chat_id]['step'] = 'price'
                send_message(chat_id, t(chat_id, 'sell_car_price'), get_cancel_menu(chat_id))
            except:
                send_message(chat_id, "Пожалуйста, введите правильный пробег (например: 50000)")
        
        elif step == 'price':
            try:
                data['price'] = float(text)
                user_states[chat_id]['step'] = 'description'
                send_message(chat_id, t(chat_id, 'sell_car_description'), get_cancel_menu(chat_id))
            except:
                send_message(chat_id, "Пожалуйста, введите правильную цену (например: 15000)")
        
        elif step == 'description':
            data['description'] = text
            user_states[chat_id]['step'] = 'phone'
            send_message(chat_id, t(chat_id, 'sell_car_phone'), get_cancel_menu(chat_id))
        
        elif step == 'phone':
            data['phone'] = text
            complete_sell(chat_id, username, first_name)
        
        user_data[chat_id] = data
        return
    
    # Обработка заказа с телефоном
    elif action == 'order':
        car_id = state.get('car_id')
        if car_id:
            complete_order(chat_id, car_id, text, username, first_name)
        return
    
    # Обработка команд
    if text == '/start':
        handle_start(chat_id, first_name)
    elif text == '/help' or text == t(chat_id, 'help_btn'):
        send_message(chat_id, t(chat_id, 'help'), get_main_menu(chat_id))
    elif text == t(chat_id, 'show_cars'):
        show_cars(chat_id)
    elif text == t(chat_id, 'price_categories'):
        send_message(chat_id, t(chat_id, 'choose_category'), get_category_menu(chat_id))
    elif text == t(chat_id, 'contact_manager'):
        show_managers(chat_id)
    elif text == t(chat_id, 'sell_car'):
        start_sell_car(chat_id)
    elif text.startswith('/'):
        send_message(chat_id, t(chat_id, 'help'), get_main_menu(chat_id))

def handle_start(chat_id, first_name):
    user_languages.pop(chat_id, None)
    user_states.pop(chat_id, None)
    user_data.pop(chat_id, None)
    
    message = TEXTS['ru']['choose_language']
    send_message(chat_id, message, get_language_menu())

def handle_language_selection(chat_id, language):
    user_languages[chat_id] = language
    send_message(chat_id, TEXTS[language]['welcome'], get_main_menu(chat_id))

def show_cars(chat_id, filter_type=None, filter_id=None):
    with app.app_context():
        query = Car.query.filter_by(is_active=True)
        
        if filter_type == 'category' and filter_id:
            category = PriceCategory.query.get(filter_id)
            if category:
                query = query.filter(
                    Car.price_usd >= category.min_price_usd,
                    Car.price_usd <= category.max_price_usd
                )
        
        cars = query.limit(5).all()
        
        if not cars:
            send_message(chat_id, t(chat_id, 'no_cars'), get_main_menu(chat_id))
            return
        
        for car in cars:
            brand_name = car.brand.name if car.brand else ""
            model_name = car.model.name if car.model else ""
            full_brand = f"{brand_name} {model_name}".strip()
            
            caption = t(chat_id, 'car_info').format(
                title=car.title,
                price=car.price_usd,
                mileage=car.mileage_km,
                brand=full_brand,
                year=car.year,
                fuel=car.fuel_type,
                transmission=car.transmission,
                color=car.color,
                engine=car.engine_capacity,
                description=car.description or ''
            )
            
            if car.photo_url:
                send_photo(chat_id, car.photo_url, caption, get_order_button(chat_id, car.id))
            else:
                send_message(chat_id, caption, get_order_button(chat_id, car.id))

def get_category_menu(chat_id):
    with app.app_context():
        categories = PriceCategory.query.filter_by(is_active=True).all()
        keyboard = []
        
        for category in categories:
            count = Car.query.filter(
                Car.price_usd >= category.min_price_usd,
                Car.price_usd <= category.max_price_usd,
                Car.is_active == True
            ).count()
            if count > 0:
                keyboard.append([{'text': f"{category.name} ({count})", 'callback_data': f'cat_{category.id}'}])
        
        keyboard.append([{'text': t(chat_id, 'back'), 'callback_data': 'back_menu'}])
        return {'inline_keyboard': keyboard}

def show_managers(chat_id):
    with app.app_context():
        managers = Manager.query.filter_by(is_active=True).all()
        
        if not managers:
            managers_text = "👨‍💼 Мухаммед\n📞 +996 555 123 456\n📧 info@suvtekin.kg"
        else:
            managers_text = ""
            for manager in managers:
                managers_text += f"👨‍💼 *{manager.name}*\n"
                if manager.telegram_username:
                    managers_text += f"📞 @{manager.telegram_username}\n"
                if manager.phone:
                    managers_text += f"📱 {manager.phone}\n"
                if manager.email:
                    managers_text += f"📧 {manager.email}\n"
                managers_text += "\n"
        
        message = t(chat_id, 'managers').format(managers=managers_text.strip())
        send_message(chat_id, message, get_main_menu(chat_id))

def start_sell_car(chat_id):
    user_states[chat_id] = {'action': 'sell_car', 'step': 'brand'}
    user_data[chat_id] = {}
    send_message(chat_id, t(chat_id, 'sell_car_welcome'))

def start_order(chat_id, car_id):
    user_states[chat_id] = {'action': 'order', 'car_id': car_id}
    send_message(chat_id, t(chat_id, 'order_phone'), get_cancel_menu(chat_id))

def complete_order(chat_id, car_id, phone, username, first_name):
    with app.app_context():
        car = Car.query.get(car_id)
        if car:
            order = Order(
                car_id=car.id,
                telegram_user_id=chat_id,
                telegram_username=username,
                telegram_first_name=first_name,
                full_name=first_name,
                phone=phone,
                status='new'
            )
            db.session.add(order)
            db.session.commit()
            
            # Уведомление админу
            admin_msg = f"📥 НОВЫЙ ЗАКАЗ!\n\nАвто: {car.title}\nЦена: ${car.price_usd:,.0f}\nКлиент: @{username}\nТелефон: {phone}\nID: {chat_id}"
            send_message(TELEGRAM_ADMIN_ID, admin_msg)
        
        send_message(chat_id, t(chat_id, 'order_success'), get_main_menu(chat_id))
        user_states.pop(chat_id, None)

def complete_sell(chat_id, username, first_name):
    data = user_data.get(chat_id, {})
    
    with app.app_context():
        sell_request = SellRequest(
            telegram_user_id=chat_id,
            telegram_username=username,
            telegram_first_name=first_name,
            car_brand=data.get('brand', ''),
            car_model=data.get('model', ''),
            car_year=data.get('year'),
            car_mileage=data.get('mileage'),
            car_price=data.get('price'),
            car_description=data.get('description', ''),
            phone=data.get('phone', ''),
            status='new'
        )
        db.session.add(sell_request)
        db.session.commit()
        
        # Уведомление админу
        admin_msg = f"💰 НОВАЯ ЗАЯВКА НА ПРОДАЖУ!\n\nМарка: {data.get('brand', '')}\nМодель: {data.get('model', '')}\nГод: {data.get('year', '')}\nПробег: {data.get('mileage', '')} км\nЦена: ${data.get('price', 0):,.0f}\nТелефон: {data.get('phone', '')}\nКлиент: @{username}\nID: {chat_id}"
        send_message(TELEGRAM_ADMIN_ID, admin_msg)
    
    send_message(chat_id, t(chat_id, 'sell_car_success'), get_main_menu(chat_id))
    user_states.pop(chat_id, None)
    user_data.pop(chat_id, None)

# Настройка вебхука при запуске
@app.before_first_request
def setup_webhook():
    try:
        # Получаем URL приложения на Render
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if not render_url:
            # Если нет переменной окружения, используем текущий хост
            render_url = f"https://{request.host}" if request.host else "https://suvtekin.onrender.com"
        
        webhook_url = f"{render_url}/webhook/{TELEGRAM_TOKEN}"
        
        # Устанавливаем вебхук
        response = requests.get(f"{BASE_URL}/setWebhook?url={webhook_url}")
        
        if response.status_code == 200:
            logger.info(f"✅ Вебхук установлен: {webhook_url}")
        else:
            logger.error(f"❌ Ошибка установки вебхука: {response.text}")
    except Exception as e:
        logger.error(f"❌ Ошибка настройки вебхука: {e}")

# Страница проверки
@app.route('/test')
def test():
    with app.app_context():
        cars_count = Car.query.count()
        brands_count = Brand.query.count()
        models_count = CarModel.query.count()
        managers_count = Manager.query.count()
        
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Suvtekin Auto - Статус</title>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            .status {{ padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .success {{ background: #d4edda; color: #155724; }}
            .info {{ background: #d1ecf1; color: #0c5460; }}
            .stats {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 20px 0; }}
            .stat-card {{ background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        </style>
    </head>
    <body>
        <h1>🚗 Suvtekin Auto - Статус системы</h1>
        
        <div class="status success">
            ✅ Система работает нормально
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>Автомобили</h3>
                <p>{cars_count} шт.</p>
            </div>
            <div class="stat-card">
                <h3>Бренды</h3>
                <p>{brands_count} шт.</p>
            </div>
            <div class="stat-card">
                <h3>Модели</h3>
                <p>{models_count} шт.</p>
            </div>
            <div class="stat-card">
                <h3>Менеджеры</h3>
                <p>{managers_count} шт.</p>
            </div>
        </div>
        
        <p><strong>Админка:</strong> <a href="/admin">/admin</a></p>
        <p><strong>Логин:</strong> muha</p>
        <p><strong>Пароль:</strong> muhamed</p>
        
        <p><strong>Telegram бот:</strong> @suvtekinn_bot</p>
        <p>1. Откройте Telegram</p>
        <p>2. Найдите бота: <strong>@suvtekinn_bot</strong></p>
        <p>3. Напишите: <code>/start</code> - выберите язык</p>
        <p>4. Используйте кнопки для навигации</p>
        
        <div class="status info">
            <strong>Примечание:</strong> Бот работает на вебхуках, что позволяет ему работать на Render.com
        </div>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    return 'OK'

# Ручная настройка вебхука
@app.route('/setup-webhook')
def manual_setup_webhook():
    try:
        render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://suvtekin.onrender.com')
        webhook_url = f"{render_url}/webhook/{TELEGRAM_TOKEN}"
        
        response = requests.get(f"{BASE_URL}/setWebhook?url={webhook_url}")
        
        if response.status_code == 200:
            return f"✅ Вебхук установлен: {webhook_url}<br><br>Ответ Telegram: {response.text}"
        else:
            return f"❌ Ошибка установки вебхука: {response.text}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Запуск Suvtekin Auto на порту {port}")
    logger.info(f"🌐 Адрес: http://localhost:{port}")
    logger.info(f"🔗 Админка: http://localhost:{port}/admin")
    logger.info(f"🔑 Логин: muha, Пароль: muhamed")
    logger.info(f"🤖 Telegram бот: @suvtekinn_bot")
    
    # Запускаем Flask
    app.run(host='0.0.0.0', port=port, debug=False)
