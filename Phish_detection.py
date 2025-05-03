"""
File: Phish_detection.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024-25). ChatGPT. Retrieved from https://chatgpt.com/
- Pandas: Pandas Development Team. (2024). Pandas (version 2.0.2). Retrieved from https://pandas.pydata.org/
- Scikit-learn: Scikit-learn developers. (2024, August 29). Scikit-learn: Machine learning in Python (version 1.2.2). Retrieved from https://scikit-learn.org/
"""
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV

def load_data(filepath):
    data = pd.read_csv(filepath)
    return data['email_text'], data['label']

def preprocess_and_vectorize(texts):
    vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
    x = vectorizer.fit_transform(texts)
    return x, vectorizer

def train_model(x, labels):
    # Correctly unpack the split data
    x_train, x_test, y_train, y_test = train_test_split(x, labels, test_size=0.3, random_state=42)
    model = LogisticRegression()
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)
    print(f"Model accuracy: {accuracy}")
    return model

def classify_email(email_text, vectorizer, model):
    email_vector = vectorizer.transform([email_text])
    prediction = model.predict(email_vector)
    return "Phishing" if prediction[0] == 1 else "Not Phishing"
