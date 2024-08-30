"""
File: Main.py
Author: Andy Xiao

References:
- Flask: Pallets Projects. (2023). Flask (version 2.2.3). Retrieved from https://flask.palletsprojects.com/
- ChatGPT: OpenAI. (2024, August 29). ChatGPT. Retrieved from https://chatgpt.com/
- Werkzeug: Pallets Projects. (2023). Werkzeug (version 2.2.3). Retrieved from https://werkzeug.palletsprojects.com/
"""
from Phish_detection import load_data, preprocess_and_vectorize, train_model, classify_email
from Filter import filter_emails
from app import allowed_file, upload_file
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
if __name__ == "__main__":
    texts, labels = load_data('email.csv')
    x, vectorizer = preprocess_and_vectorize(texts)
    model = train_model(x, labels)

    new_email = "Example email text to classify."
    result = classify_email(new_email, vectorizer, model)
    filter_emails('email.csv')
    print(f"Email classification: {result}")


    
