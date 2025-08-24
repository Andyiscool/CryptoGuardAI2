# CryptoGuardAI

CryptoGuardAI is aimed at detecting phishing emails and securing email communications using AI, cryptography, and cybersecurity.
# How To Run
1) run "docker-compose up --build -d" - start servers and database
2) run "docker-compose run --rm alice_client" - send to bob
3) run "docker-compose run --rm bob_client_receive" - message from alice
4) run "docker-compose run --rm bob_client" - send to alice
5) run "docker-compose run --rm alice_client_receive" - message from bob
6) run "docker-compose down" - shut down servers and database

# How To Rerun After Change
1) save files
2) run "docker-compose down" - shut down servers and database
3) run "docker-compose up --build -d" - start servers and database
4) Do Steps 2 to 5 in "How To Run"

# Manual Delete Database Or Check Data
1) run "docker-compose down" - shut down servers and database
2) start "mongo_primary" and "mongo_backup"
3) in "mongo_primary" type "use email_db"
4) type "db.dropDatabase()" to drop or "db.messages.find().pretty()" to check message
5) if dropping database, type "use email_db_backup" and type "db.dropDatabase()" again
6) if dropping database, check both "mongo_primary" and "mongo_backup" by typing "db.messages.find().pretty()" for both "email_db" and "email_db_backup"

## Features

- **Phishing Email Detection**: Classify emails as phishing or not phishing using machine learning models.
- **Email Filtering**: Automatically separating phishing emails from legitimate emails.
- **Web Interface**: Upload and process emails through a Flask-based web application.
- **User Privacy**: Use end to end encryption methods to safely send and receive emails and protect confidentiallity.

### Prerequisites

- Python 3.10.9
- Required Python libraries: `flask`, `werkzeug`, `pandas`, `scikit-learn`

### References
### Code
[1] Flask: Pallets Projects. (2023). Flask (version 3.0.3). https://flask.palletsprojects.com/

[2] ChatGPT: OpenAI. (2024-25). ChatGPT. https://chatgpt.com/

[3] GitHub Copilot: GitHub. (2025). Github Copilot. https://github.com/features/copilot

[4] Pandas: Pandas Development Team. (2024). Pandas (version 2.2.2). https://pandas.pydata.org/

[5] Scikit-learn: Scikit-learn developers. (2024, August 29). Scikit-learn: Machine learning in Python (version 1.5.1). https://scikit-learn.org/

[6] Werkzeug: Pallets Projects. (2023). Werkzeug (version 3.0.3). https://werkzeug.palletsprojects.com/

### Datasets
[1] ChatGPT: OpenAI. (2024-25). ChatGPT. https://chatgpt.com/

