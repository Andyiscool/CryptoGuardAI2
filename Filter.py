"""
File: Filter.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024-25). ChatGPT. Retrieved from https://chatgpt.com/
"""
import os
from Phish_detection import load_data, preprocess_and_vectorize, train_model, classify_email
def filter_emails(email_file, legit_dir="NotPhishing", phishing_dir = "Phishing"):
    os.makedirs(legit_dir, exist_ok = True)
    os.makedirs(phishing_dir, exist_ok = True)
    texts, labels = load_data(email_file)
    x, vectorizer = preprocess_and_vectorize(texts)
    model = train_model(x,labels)

    for i, text in enumerate(texts):
        classification = classify_email(text, vectorizer, model)
        if classification == "Not Phishing":
            with open(f"{legit_dir}/email_{i}.txt", "w") as f:
                f.write(text)
        else:
            with open(f"{phishing_dir}/email_{i}.txt", "w") as f:
                f.write(text)
