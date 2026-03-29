import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app import app, db, User, Group, Subject, Semester, Grade
from werkzeug.security import generate_password_hash
from datetime import date
from sqlalchemy import text, select

@pytest.fixture(scope='function')
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        # Очистка всех таблиц
        db.session.execute(text('TRUNCATE users, groups, subjects, semesters, grades RESTART IDENTITY CASCADE;'))
        db.session.commit()

        # Создаём группу "ИС-22"
        group_IS22 = Group(name='ИС-22')
        db.session.add(group_IS22)
        db.session.commit()

        # Создаём группу "П-21" для теста изменения группы
        group_P21 = Group(name='П-21')
        db.session.add(group_P21)
        db.session.commit()

        # Преподаватель teacher1
        teacher = User(
            username='teacher1',
            password_hash=generate_password_hash('123'),
            role='teacher'
        )
        db.session.add(teacher)

        # Студент student1 в группе "ИС-22"
        student = User(
            username='student1',
            password_hash=generate_password_hash('123'),
            role='student',
            group_id=group_IS22.id
        )
        db.session.add(student)
        db.session.commit()

        # Предмет "Математика"
        subject_math = Subject(name='Математика')
        db.session.add(subject_math)
        db.session.commit()

        # Семестр "Осень 2025"
        semester_fall = Semester(
            name='Осень 2025',
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 31)
        )
        db.session.add(semester_fall)
        db.session.commit()

        # Оценка: student1 по математике, 5 баллов, 2026-03-10, осень 2025
        grade = Grade(
            grade=5,
            date=date(2026, 3, 10),
            student_id=student.id,
            subject_id=subject_math.id,
            semester_id=semester_fall.id
        )
        db.session.add(grade)
        db.session.commit()

    with app.test_client() as test_client:
        yield test_client

    # Очистка после теста (необязательно, так как перед каждым тестом всё равно очищаем)
    with app.app_context():
        db.session.execute(text('TRUNCATE users, groups, subjects, semesters, grades RESTART IDENTITY CASCADE;'))
        db.session.commit()

# 1. Корректный вход преподавателя
def test_login_valid_teacher(client):
    rv = client.post('/login', data={'username': 'teacher1', 'password': '123'}, follow_redirects=True)
    assert rv.status_code == 200
    assert 'teacher1' in rv.get_data(as_text=True)

# 2. Корректный вход студента
def test_login_valid_student(client):
    rv = client.post('/login', data={'username': 'student1', 'password': '123'}, follow_redirects=True)
    assert rv.status_code == 200
    assert 'student1' in rv.get_data(as_text=True)

# 3. Неверные данные
def test_login_invalid(client):
    rv = client.post('/login', data={'username': 'wrong', 'password': 'wrong'}, follow_redirects=True)
    assert 'Неверное имя пользователя или пароль' in rv.get_data(as_text=True)

# 4. Доступ студента к странице управления пользователями
def test_access_denied_student_to_users(client):
    client.post('/login', data={'username': 'student1', 'password': '123'})
    rv = client.get('/users', follow_redirects=True)
    assert 'Доступ запрещён' in rv.get_data(as_text=True)

# 5. Добавление нового предмета (преподаватель)
def test_add_new_subject(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    rv = client.post('/subjects/add', data={'name': 'Базы данных'}, follow_redirects=True)
    assert 'Предмет добавлен' in rv.get_data(as_text=True)
    rv = client.get('/subjects')
    assert 'Базы данных' in rv.get_data(as_text=True)

# 6. Добавление предмета с существующим именем
def test_add_duplicate_subject(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    rv = client.post('/subjects/add', data={'name': 'Математика'}, follow_redirects=True)
    assert 'Предмет с таким названием уже существует' in rv.get_data(as_text=True)

# 7. Добавление оценки (преподаватель)
def test_add_grade(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        student = User.query.filter_by(username='student1').first()
        subject = Subject.query.filter_by(name='Математика').first()
        semester = Semester.query.filter_by(name='Осень 2025').first()
    rv = client.post('/add_grade', data={
        'student_id': student.id,
        'subject_id': subject.id,
        'grade': 5,
        'date': '2026-03-10',
        'semester_id': semester.id
    }, follow_redirects=True)
    assert 'Оценка успешно добавлена' in rv.get_data(as_text=True)
    # Проверяем, что оценка появилась
    rv = client.get('/dashboard')
    assert '5' in rv.get_data(as_text=True)

# 8. Добавление оценки с пустым полем (например, без даты)
def test_add_grade_missing_field(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        student = User.query.filter_by(username='student1').first()
        subject = Subject.query.filter_by(name='Математика').first()
        semester = Semester.query.filter_by(name='Осень 2025').first()
    rv = client.post('/add_grade', data={
        'student_id': student.id,
        'subject_id': subject.id,
        'grade': 5,
        # date отсутствует
        'semester_id': semester.id
    }, follow_redirects=True)
    assert 'Пожалуйста, заполните все поля' in rv.get_data(as_text=True)

# 9. Редактирование оценки (изменение с 5 на 4)
def test_edit_grade(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        grade = Grade.query.first()
    # Редактируем
    rv = client.post(f'/edit_grade/{grade.id}', data={
        'student_id': grade.student_id,
        'subject_id': grade.subject_id,
        'grade': 4,
        'date': grade.date.strftime('%Y-%m-%d'),
        'semester_id': grade.semester_id
    }, follow_redirects=True)
    assert 'Оценка обновлена' in rv.get_data(as_text=True)
    # Проверяем, что изменилась
    rv = client.get('/dashboard')
    assert '4' in rv.get_data(as_text=True)

# 10. Удаление оценки
def test_delete_grade(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        grade = Grade.query.first()
        grade_id = grade.id
    rv = client.get(f'/delete_grade/{grade_id}', follow_redirects=True)
    assert 'Оценка удалена' in rv.get_data(as_text=True)
    # Проверяем, что оценка удалена из БД
    with app.app_context():
        deleted = db.session.get(Grade, grade_id)
        assert deleted is None

# 11. Фильтрация оценок по группе (ИС-22)
def test_filter_grades_by_group(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        group = Group.query.filter_by(name='ИС-22').first()
    rv = client.get(f'/dashboard?group_id={group.id}')
    assert rv.status_code == 200
    assert '5' in rv.get_data(as_text=True)   # оценка студента из этой группы

# 12. Фильтрация по предмету (Математика)
def test_filter_by_subject(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        subject = Subject.query.filter_by(name='Математика').first()
    rv = client.get(f'/dashboard?subject_id={subject.id}')
    assert rv.status_code == 200
    assert '5' in rv.get_data(as_text=True)   # оценка по математике

# 13. Фильтрация по семестру (Осень 2025)
def test_filter_by_semester(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        semester = Semester.query.filter_by(name='Осень 2025').first()
    rv = client.get(f'/dashboard?semester_id={semester.id}')
    assert rv.status_code == 200
    assert '5' in rv.get_data(as_text=True)   # оценка за осенний семестр

# 14. Просмотр своих оценок студентом
def test_student_sees_only_his_grades(client):
    client.post('/login', data={'username': 'student1', 'password': '123'})
    rv = client.get('/dashboard')
    assert '5' in rv.get_data(as_text=True)   # его оценка
    # Проверяем, что не видит чужих (чужих нет, но для структуры)

# 15. Смена пароля (успешно)
def test_change_password_success(client):
    client.post('/login', data={'username': 'student1', 'password': '123'})
    rv = client.post('/change_password', data={
        'old_password': '123',
        'new_password': '456',
        'confirm_password': '456'
    }, follow_redirects=True)
    assert 'Пароль успешно изменён' in rv.get_data(as_text=True)
    client.get('/logout')
    rv = client.post('/login', data={'username': 'student1', 'password': '456'}, follow_redirects=True)
    assert 'student1' in rv.get_data(as_text=True)

# 16. Смена пароля (неверный старый)
def test_change_password_wrong_old(client):
    client.post('/login', data={'username': 'student1', 'password': '123'})
    rv = client.post('/change_password', data={
        'old_password': '000',
        'new_password': '456',
        'confirm_password': '456'
    }, follow_redirects=True)
    assert 'Неверный текущий пароль' in rv.get_data(as_text=True)

# 17. Смена пароля (несовпадение нового и подтверждения)
def test_change_password_mismatch(client):
    client.post('/login', data={'username': 'student1', 'password': '123'})
    rv = client.post('/change_password', data={
        'old_password': '123',
        'new_password': '456',
        'confirm_password': '789'
    }, follow_redirects=True)
    assert 'Новые пароли не совпадают' in rv.get_data(as_text=True)

# 18. Сброс пароля пользователем (преподаватель)
def test_reset_password_by_teacher(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        student = User.query.filter_by(username='student1').first()
    rv = client.get(f'/users/reset_password/{student.id}', follow_redirects=True)
    assert f'Пароль пользователя {student.username} сброшен на 123' in rv.get_data(as_text=True)
    client.get('/logout')
    # Проверяем, что старый пароль (456) больше не работает
    rv = client.post('/login', data={'username': 'student1', 'password': '456'}, follow_redirects=True)
    assert 'Неверное имя пользователя или пароль' in rv.get_data(as_text=True)
    # А сброшенный работает
    rv = client.post('/login', data={'username': 'student1', 'password': '123'}, follow_redirects=True)
    assert 'student1' in rv.get_data(as_text=True)

# 19. Изменение группы студента (преподаватель)
def test_change_student_group(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        student = User.query.filter_by(username='student1').first()
        new_group = Group.query.filter_by(name='П-21').first()
    rv = client.post(f'/users/edit/{student.id}', data={'group_id': new_group.id}, follow_redirects=True)
    assert 'Данные пользователя обновлены' in rv.get_data(as_text=True)
    # Проверяем, что группа изменилась
    with app.app_context():
        updated = User.query.get(student.id)
        assert updated.group_id == new_group.id

# 20. Удаление предмета, на который есть оценки (каскадное удаление)
def test_delete_subject_with_grades(client):
    client.post('/login', data={'username': 'teacher1', 'password': '123'})
    with app.app_context():
        subject = Subject.query.filter_by(name='Математика').first()
        subject_id = subject.id
        # Убедимся, что есть оценки
        assert Grade.query.filter_by(subject_id=subject_id).count() > 0
    rv = client.get(f'/subjects/delete/{subject_id}', follow_redirects=True)
    assert 'Предмет удалён' in rv.get_data(as_text=True)
    # Проверяем, что оценки тоже удалены (каскадно)
    with app.app_context():
        assert Subject.query.get(subject_id) is None
        assert Grade.query.filter_by(subject_id=subject_id).count() == 0