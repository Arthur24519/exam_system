# 🎓 Информационная система учёта экзаменов и зачётов

![Python](https://img.shields.io/badge/Python-3.13%2B-blue)
![Flask](https://img.shields.io/badge/Flask-2.3%2B-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17%2B-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

Веб-приложение для автоматизации учёта результатов промежуточной аттестации (экзаменов и зачётов).  
Поддерживаются две роли: **преподаватель** (управление справочниками, выставление оценок) и **студент** (просмотр своих оценок).

## 🚀 Быстрый старт

### 1. Клонирование и установка

```bash
git clone https://github.com/ВАШ_ЛОГИН/exam-accounting-system.git
cd exam-accounting-system
python -m venv venv
```
#### Активация виртуального окружения
```
venv\Scripts\activate  # Windows
```

### 2. Настройка PostgreSQL

#### В psql от имени postgres:
```
CREATE DATABASE exam_results_db;
CREATE USER postgres WITH PASSWORD 'ваш_пароль';
GRANT ALL PRIVILEGES ON DATABASE exam_results_db TO postgres;
```
#### Инициализация БД:
```
psql -U postgres -d exam_results_db -f "Создание БД.txt"
```
### 3. Настройка окружения
#### Создайте файл .env в корне проекта:
```
DB_HOST=localhost
DB_PORT=5433
DB_NAME=exam_results_db
DB_USER=postgres
DB_PASSWORD=ваш_пароль
SECRET_KEY=ваш_секретный_ключ
```
### 4. Запуск приложения
```
python app.py
```
#### Откройте в браузере: http://localhost:5000

### 5. Тестовые аккаунты

| Роль | Логин | Пароль |
|------|-------|--------|
| 👨‍🏫 Преподаватель | `teacher1` | `123` |
| 👨‍🎓 Студент | `student1` | `123` |
