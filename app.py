"""
File: app.py
Author: Andy Xiao

References:
- Flask: Pallets Projects. (2023). Flask (version 2.2.3). Retrieved from https://flask.palletsprojects.com/
- ChatGPT: OpenAI. (2024, August 29). ChatGPT. Retrieved from https://chatgpt.com/
- Werkzeug: Pallets Projects. (2023). Werkzeug (version 2.2.3). Retrieved from https://werkzeug.palletsprojects.com/
"""
from flask import Flask, render_template, request, redirect, url_for
import os
from Filter import filter_emails
from Phish_detection import load_data, preprocess_and_vectorize, train_model, classify_email
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/',methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            filter_emails(filepath)
            return redirect(url_for('results', filename=filename))
    return render_template('item.html')

@app.route('/results/<filename>')
def results(filename):
    return f"Results for file: {filename}"

if __name__ == "__main__":
    # Ensure the uploads folder exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    app.run(host='127.0.0.1', port=5000, debug=True)
