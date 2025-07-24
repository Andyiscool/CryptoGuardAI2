"""
File: app.py
Author: Andy Xiao

References:
- Flask: Pallets Projects. (2023). Flask (version 2.2.3). Retrieved from https://flask.palletsprojects.com/
- ChatGPT: OpenAI. (2024-25). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025). Github Copilot. Retrieved from https://github.com/features/copilot
- Werkzeug: Pallets Projects. (2023). Werkzeug (version 2.2.3). Retrieved from https://werkzeug.palletsprojects.com/
"""
from flask import Flask, render_template, request, redirect, url_for, flash
import os
from Filter import filter_emails
from Phish_detection import load_data, preprocess_and_vectorize, train_model, classify_email
from werkzeug.utils import secure_filename
from user_management import register_user, authenticate_user
import secrets
secret_key = secrets.token_hex(32)

app = Flask(__name__)
app.secret_key = secret_key

UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/',methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return 'No selected file'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            filter_emails(filepath)
            return redirect(url_for('results', filename=filename))
    return render_template('upload.html')

@app.route('/results/<filename>')
def results(filename):
    return f"Results for file: {filename}"
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match.')
            return render_template('register.html')
        response = register_user(email, password)
        if response != "User registered successfully.":
            flash(response)
            return render_template('register.html')
        flash(response)
        return redirect(url_for('upload_file'))
    return render_template('register.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if authenticate_user(email, password):
            flash('Login successful.')
            return redirect(url_for('upload_file'))
        else:
            flash('Login failed. Please check your credentials.')
            return redirect(request.url)
    return render_template('login.html')
if __name__ == "__main__":
    
    app.run(host='127.0.0.1', port=5000, debug=True)
