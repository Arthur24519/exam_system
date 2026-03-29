import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'  # Замените на свой!
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:07111969@localhost:5433/exam_results_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ---------- МОДЕЛИ ----------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    students = db.relationship('User', backref='group', lazy=True)

class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    grades = db.relationship('Grade', backref='subject', lazy=True, passive_deletes=True)

class Semester(db.Model):
    __tablename__ = 'semesters'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    grades = db.relationship('Grade', backref='semester', lazy=True)

class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    grade = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey('semesters.id', ondelete='SET NULL'))
    
    student = db.relationship('User', foreign_keys=[student_id], backref='grades')

# ---------- ЗАГРУЗЧИК ПОЛЬЗОВАТЕЛЯ ----------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ---------- МАРШРУТЫ ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'teacher':
        # Преподаватель: применяем фильтры из GET-параметров
        query = Grade.query
        group_id = request.args.get('group_id', type=int)
        if group_id:
            students_in_group = db.session.query(User.id).filter_by(group_id=group_id, role='student').subquery()
            query = query.filter(Grade.student_id.in_(students_in_group))
        subject_id = request.args.get('subject_id', type=int)
        if subject_id:
            query = query.filter_by(subject_id=subject_id)
        semester_id = request.args.get('semester_id', type=int)
        if semester_id:
            query = query.filter_by(semester_id=semester_id)
        all_grades = query.order_by(Grade.date.desc()).all()
        students = User.query.filter_by(role='student').all()
        subjects = Subject.query.all()
        groups = Group.query.all()
        semesters = Semester.query.all()
        return render_template('dashboard.html',
                               grades=all_grades,
                               students=students,
                               subjects=subjects,
                               groups=groups,
                               semesters=semesters,
                               is_teacher=True)
    else:
        # Студент: только свои оценки
        my_grades = Grade.query.filter_by(student_id=current_user.id).order_by(Grade.date.desc()).all()
        return render_template('dashboard.html', grades=my_grades, is_teacher=False)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old = request.form.get('old_password')
    new = request.form.get('new_password')
    confirm = request.form.get('confirm_password')
    if not current_user.check_password(old):
        flash('Неверный текущий пароль')
        return redirect(url_for('profile'))
    if new != confirm:
        flash('Новые пароли не совпадают')
        return redirect(url_for('profile'))
    current_user.set_password(new)
    db.session.commit()
    flash('Пароль успешно изменён')
    return redirect(url_for('profile'))

# Управление предметами (только преподаватель)
@app.route('/subjects')
@login_required
def subjects_list():
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    subjects = Subject.query.all()
    return render_template('subjects_list.html', subjects=subjects)

@app.route('/subjects/add', methods=['GET', 'POST'])
@login_required
def subject_add():
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name')
        if Subject.query.filter_by(name=name).first():
            flash('Предмет с таким названием уже существует')
            return redirect(url_for('subject_add'))
        subject = Subject(name=name)
        db.session.add(subject)
        db.session.commit()
        flash('Предмет добавлен')
        return redirect(url_for('subjects_list'))
    return render_template('subject_form.html')

@app.route('/subjects/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def subject_edit(id):
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    subject = Subject.query.get_or_404(id)
    if request.method == 'POST':
        name = request.form.get('name')
        if name != subject.name and Subject.query.filter_by(name=name).first():
            flash('Предмет с таким названием уже существует')
            return redirect(url_for('subject_edit', id=id))
        subject.name = name
        db.session.commit()
        flash('Предмет обновлён')
        return redirect(url_for('subjects_list'))
    return render_template('subject_form.html', subject=subject)

@app.route('/subjects/delete/<int:id>')
@login_required
def subject_delete(id):
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    subject = Subject.query.get_or_404(id)
    db.session.delete(subject)
    db.session.commit()
    flash('Предмет удалён')
    return redirect(url_for('subjects_list'))

# Управление оценками
@app.route('/add_grade', methods=['GET', 'POST'])
@login_required
def add_grade():
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        subject_id = request.form.get('subject_id')
        grade_value = request.form.get('grade')
        date_str = request.form.get('date')
        semester_id = request.form.get('semester_id')
        if not (student_id and subject_id and grade_value and date_str and semester_id):
            flash('Пожалуйста, заполните все поля')
            return redirect(url_for('add_grade'))
        try:
            new_grade = Grade(
                student_id=student_id,
                subject_id=subject_id,
                grade=grade_value,
                date=datetime.strptime(date_str, '%Y-%m-%d'),
                semester_id=semester_id
            )
            db.session.add(new_grade)
            db.session.commit()
            flash('Оценка успешно добавлена')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении оценки: {e}')
    students = User.query.filter_by(role='student').all()
    subjects = Subject.query.all()
    semesters = Semester.query.all()
    return render_template('add_grade.html', students=students, subjects=subjects, semesters=semesters)

@app.route('/edit_grade/<int:grade_id>', methods=['GET', 'POST'])
@login_required
def edit_grade(grade_id):
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    grade = Grade.query.get_or_404(grade_id)
    if request.method == 'POST':
        grade.student_id = request.form.get('student_id')
        grade.subject_id = request.form.get('subject_id')
        grade.grade = request.form.get('grade')
        date_str = request.form.get('date')
        grade.date = datetime.strptime(date_str, '%Y-%m-%d')
        grade.semester_id = request.form.get('semester_id')
        try:
            db.session.commit()
            flash('Оценка обновлена')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка обновления: {e}')
    students = User.query.filter_by(role='student').all()
    subjects = Subject.query.all()
    semesters = Semester.query.all()
    return render_template('edit_grade.html', grade=grade, students=students, subjects=subjects, semesters=semesters)

@app.route('/delete_grade/<int:grade_id>')
@login_required
def delete_grade(grade_id):
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    grade = Grade.query.get_or_404(grade_id)
    db.session.delete(grade)
    db.session.commit()
    flash('Оценка удалена')
    return redirect(url_for('dashboard'))

# Управление пользователями (только преподаватель)
@app.route('/users')
@login_required
def users_list():
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    users = User.query.all()
    groups = Group.query.all()
    return render_template('users_list.html', users=users, groups=groups)

@app.route('/users/edit/<int:id>', methods=['POST'])
@login_required
def user_edit(id):
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(id)
    user.group_id = request.form.get('group_id') or None
    db.session.commit()
    flash('Данные пользователя обновлены')
    return redirect(url_for('users_list'))

@app.route('/users/reset_password/<int:id>')
@login_required
def user_reset_password(id):
    if current_user.role != 'teacher':
        flash('Доступ запрещён')
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(id)
    user.set_password('123')  # Сброс на стандартный пароль
    db.session.commit()
    flash(f'Пароль пользователя {user.username} сброшен на 123')
    return redirect(url_for('users_list'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создаст таблицы, если их ещё нет (но мы уже создали через SQL)
    app.run(debug=True)