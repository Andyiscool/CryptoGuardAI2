import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score

def load_data(filepath):
    data = pd.read_csv(filepath)
    return data['email_text'], data['label']

def preprocess_and_vectorize(texts):
    vectorizer = TfidfVectorizer(stop_words='english')
    x = vectorizer.fit_transform(texts)
    return x, vectorizer

def train_model(x, labels):
    x_train, y_train, x_test, y_test = train_test_split(x, labels, test_size=0.3, random_state=42)
    model = MultinomialNB()
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)
    print(f"Model accuracy: {accuracy}")
    return model

def classify_email(email_text, vectorizer, model):
    email_vector = vectorizer.transform([email_text])
    prediction = model.predict(email_vector)
    return "Phishing" if prediction[0] == 1 else "Not Phishing"

if __name__=="__main__":
    texts, labels = load_data('emails.csv')
    x, vectorizer = preprocess_and_vectorize(texts)
    model = train_model(x, labels)

    new_email = "Example email text to classify."
    result = classify_email(new_email, vectorizer, model)
    print(f"Email classification: {result}")

