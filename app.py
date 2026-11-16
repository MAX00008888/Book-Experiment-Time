import csv
import io
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, session, url_for

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('DATABASE_PATH', str(BASE / 'reservations.db')))
TZ_NAME = os.environ.get('EXPERIMENT_TIMEZONE', 'America/Toronto')
TZ = ZoneInfo(TZ_NAME)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'change-me-before-deploying')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'development-only-change-this-secret')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1')


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=15000')
    return conn


def init_db():
    with db() as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                starts_at TEXT NOT NULL UNIQUE,
                ends_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL UNIQUE REFERENCES slots(id),
                participant_name TEXT NOT NULL,
                email TEXT NOT NULL,
                confirmation_code TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
        ''')


def admin_only(fn):
    @wraps(fn)
    def guarded(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return guarded


def read_slots(include_past=False):
    cutoff = datetime.now(TZ).strftime('%Y-%m-%dT%H:%M')
    with db() as conn:
        sql = '''SELECT s.id, s.starts_at, s.ends_at, b.participant_name,
                    b.email, b.confirmation_code, b.id as booking_id
                 FROM slots s LEFT JOIN bookings b ON b.slot_id=s.id'''
        if not include_past:
            sql += ' WHERE s.starts_at > ?'
            rows = conn.execute(sql + ' ORDER BY s.starts_at', (cutoff,)).fetchall()
        else:
            rows = conn.execute(sql + ' ORDER BY s.starts_at').fetchall()
    return [dict(row) for row in rows]


@app.get('/')
def index():
    return render_template('index.html', slots=[s for s in read_slots() if not s['booking_id']], timezone=TZ_NAME)


@app.post('/book')
def book():
    try:
        slot_id = int(request.form.get('slot_id', ''))
    except ValueError:
        abort(400)
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    if not (2 <= len(name) <= 100 and 3 <= len(email) <= 150 and '@' in email):
        flash('Please enter your name and a valid email address.', 'error')
        return redirect(url_for('index'))
    code = secrets.token_urlsafe(12)
    now = datetime.now(TZ).isoformat(timespec='seconds')
    try:
        with db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            slot = conn.execute('SELECT starts_at FROM slots WHERE id=?', (slot_id,)).fetchone()
            if not slot or slot['starts_at'] <= datetime.now(TZ).strftime('%Y-%m-%dT%H:%M'):
                flash('That time slot is no longer available.', 'error')
                return redirect(url_for('index'))
            conn.execute('INSERT INTO bookings(slot_id,participant_name,email,confirmation_code,created_at) VALUES (?,?,?,?,?)',
                         (slot_id, name, email, code, now))
    except sqlite3.IntegrityError:
        flash('Someone has already booked that slot. Please choose another.', 'error')
        return redirect(url_for('index'))
    return redirect(url_for('confirmation', code=code))


@app.get('/confirmation/<code>')
def confirmation(code):
    with db() as conn:
        row = conn.execute('''SELECT s.starts_at, s.ends_at, b.participant_name,
                          b.email, b.confirmation_code FROM bookings b
                          JOIN slots s ON b.slot_id=s.id WHERE b.confirmation_code=?''', (code,)).fetchone()
    if not row:
        abort(404)
    return render_template('confirmation.html', booking=dict(row), timezone=TZ_NAME)


@app.route('/cancel/<code>', methods=['GET', 'POST'])
def cancel(code):
    with db() as conn:
        booking = conn.execute('''SELECT b.id, b.participant_name, s.starts_at
                      FROM bookings b JOIN slots s ON b.slot_id=s.id
                      WHERE b.confirmation_code=?''', (code,)).fetchone()
        if not booking:
            abort(404)
        if request.method == 'POST':
            conn.execute('DELETE FROM bookings WHERE id=?', (booking['id'],))
            flash('Your reservation has been cancelled.', 'success')
            return redirect(url_for('index'))
    return render_template('cancel.html', booking=dict(booking), timezone=TZ_NAME)


@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if secrets.compare_digest(request.form.get('password', ''), ADMIN_PASSWORD):
            session.clear()
            session['admin'] = True
            return redirect(url_for('admin'))
        flash('Incorrect password.', 'error')
    return render_template('login.html')


@app.post('/admin/logout')
@admin_only
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.get('/admin')
@admin_only
def admin():
    return render_template('admin.html', slots=read_slots(include_past=True), timezone=TZ_NAME)


@app.post('/admin/slots')
@admin_only
def add_slots():
    try:
        day_from = datetime.strptime(request.form['date_from'], '%Y-%m-%d').date()
        day_to = datetime.strptime(request.form['date_to'], '%Y-%m-%d').date()
        start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        end_time = datetime.strptime(request.form['end_time'], '%H:%M').time()
        duration = int(request.form['duration'])
        if not (1 <= (day_to - day_from).days + 1 <= 90 and 15 <= duration <= 240):
            raise ValueError('Invalid date range or duration')
        if datetime.combine(day_from, start_time) >= datetime.combine(day_from, end_time):
            raise ValueError('End time must be later than start time')
        made = 0
        with db() as conn:
            for offset in range((day_to-day_from).days+1):
                day = day_from + timedelta(days=offset)
                if request.form.get('weekdays_only') and day.weekday() >= 5:
                    continue
                current = datetime.combine(day, start_time)
                end = datetime.combine(day, end_time)
                while current + timedelta(minutes=duration) <= end:
                    start_iso = current.strftime('%Y-%m-%dT%H:%M')
                    end_iso = (current + timedelta(minutes=duration)).strftime('%Y-%m-%dT%H:%M')
                    if current.replace(tzinfo=TZ) > datetime.now(TZ):
                        exists = conn.execute('SELECT 1 FROM slots WHERE starts_at < ? AND ends_at > ?', (end_iso, start_iso)).fetchone()
                        if not exists:
                            conn.execute('INSERT INTO slots(starts_at, ends_at) VALUES (?,?)', (start_iso, end_iso))
                            made += 1
                    current += timedelta(minutes=duration)
        flash(f'{made} new time slots created. Existing overlaps were skipped.', 'success')
    except (ValueError, KeyError) as ex:
        flash(f'Please check your slot settings: {ex}', 'error')
    return redirect(url_for('admin'))


@app.post('/admin/slots/<int:slot_id>/delete')
@admin_only
def delete_slot(slot_id):
    with db() as conn:
        if conn.execute('SELECT 1 FROM bookings WHERE slot_id=?', (slot_id,)).fetchone():
            flash('Booked sessions must be cancelled before a slot can be deleted.', 'error')
        else:
            conn.execute('DELETE FROM slots WHERE id=?', (slot_id,))
            flash('Time slot deleted.', 'success')
    return redirect(url_for('admin'))


@app.post('/admin/bookings/<int:booking_id>/cancel')
@admin_only
def admin_cancel(booking_id):
    with db() as conn:
        conn.execute('DELETE FROM bookings WHERE id=?', (booking_id,))
    flash('Reservation cancelled. The slot is available again.', 'success')
    return redirect(url_for('admin'))


@app.get('/admin/export.csv')
@admin_only
def export():
    data = io.StringIO()
    writer = csv.writer(data)
    writer.writerow(['date', 'start', 'end', 'participant_name', 'email', 'confirmation_code', 'created_at'])
    with db() as conn:
        rows = conn.execute('''SELECT s.starts_at,s.ends_at,b.participant_name,b.email,b.confirmation_code,b.created_at
              FROM bookings b JOIN slots s ON s.id=b.slot_id ORDER BY s.starts_at''')
        for r in rows:
            writer.writerow([r['starts_at'][:10], r['starts_at'][11:], r['ends_at'][11:], r['participant_name'], r['email'], r['confirmation_code'], r['created_at']])
    return Response(data.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=experiment_reservations.csv'})


@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store'
    return response


init_db()
if __name__ == '__main__':
    app.run(debug=False, port=int(os.environ.get('PORT', '5000')))
