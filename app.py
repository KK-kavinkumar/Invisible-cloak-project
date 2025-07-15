
from flask import Flask, render_template, request, redirect, session, send_from_directory, url_for
import sqlite3
import os
from datetime import datetime
import psutil
import subprocess

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
process = None

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS history (username TEXT, filename TEXT, uploaded_at TEXT)')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def dashboard():
    username = session.get('username')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    history = []
    latest = None

    if username:
        c.execute("SELECT filename, uploaded_at FROM history WHERE username=? ORDER BY uploaded_at DESC", (username,))
        history = c.fetchall()
        latest = history[0][0] if history else None

    return render_template('dashboard.html', username=username, history=history, latest_video=latest, datetime=datetime)


@app.route('/process')
def process_video():
    if 'username' not in session:
        return redirect(url_for('login', next='process'))
    global process
    process = subprocess.Popen(['python', 'process_video.py'])
    return redirect('/')

@app.route('/stop')
def stop_video():
    global process
    if 'username' in session and process:
        try:
            # Kill all child processes as well
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except Exception as e:
            print(f"Failed to kill process: {e}")
        finally:
            process = None

        # Save to history
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("INSERT INTO history VALUES (?, ?, ?)", (session['username'], 'output.avi', str(datetime.now())))
        conn.commit()

    return redirect('/')

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next') or '/'
    if request.method == 'POST':
        u, p = request.form['username'], request.form['password']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
        if c.fetchone():
            session['username'] = u
            return redirect(next_page)
        else:
            return render_template('login.html', error='Invalid credentials', next=next_page)
    return render_template('login.html', next=next_page)

@app.route('/register', methods=['GET', 'POST'])
def register():
    next_page = request.args.get('next') or '/'
    if request.method == 'POST':
        u, p = request.form['username'], request.form['password']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users VALUES (?, ?)", (u, p))
            conn.commit()
            session['username'] = u
            return redirect(next_page)
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username already exists', next=next_page)
    return render_template('register.html', next=next_page)

@app.route('/video/<f>')
def serve(f):
    return send_from_directory(app.config['UPLOAD_FOLDER'], f)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/')

@app.route('/users')
def users():
    if session.get('username') != 'admin':
        return "Unauthorized", 403
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users = c.fetchall()
    return render_template('users.html', users=users)

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
