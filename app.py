from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from firebase_admin import credentials, auth
from flask_mail import Mail, Message
import firebase_admin
import joblib
import pandas as pd
from sklearn.preprocessing import StandardScaler
from flask_cors import CORS
import openai
import os
import json
import re

app = Flask(__name__)
CORS(app)

# Firebase setup
service_account_info = json.loads(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred)

# Secret key for session management
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')

# MongoDB Connection
client = MongoClient(os.environ.get('MONGO_URI', 'your_connection_string'))
db = client['my_database']  # Replace 'my_database' with your database name
users_collection = db['users']  # Replace 'users' with your collection name

# Load the model and scaler
rf_model = joblib.load('rf_model.joblib')
scaler = joblib.load('scaler.joblib')
X_columns = joblib.load('X_columns.joblib')

# Set OpenAI API key directly
openai.api_key = os.environ.get('OPENAI_API_KEY')

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER')  # Your email address
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS')  # Your email password
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('EMAIL_USER')  # Default sender

# Initialize Flask-Mail
mail = Mail(app)
app.config['MAIL_ASCII_ATTACHMENTS'] = False 

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

@app.route('/')
def root():
    # Redirect to login if not authenticated
    if 'user_logged_in' in session and session['user_logged_in']:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.json
        id_token = data.get('idToken')
        name = data.get('name')  # Capture name from frontend
        email = None

        try:
            if id_token:
                # Google Signup
                decoded_token = auth.verify_id_token(id_token)
                email = decoded_token['email']
                name = decoded_token.get('name', '')
            elif name and 'email' in data and 'password' in data:
                # Email/Password Signup
                email = data['email']
                password = data['password']
                # Check if email already exists
                if users_collection.find_one({"email": email}):
                    return jsonify({"error": "Email already registered. Please log in."}), 400
                # Hash password before saving to the database
                hashed_password = generate_password_hash(password)
                users_collection.insert_one({
                    "name": name,
                    "email": email,
                    "password": hashed_password
                })
            else:
                return jsonify({"error": "Invalid signup data"}), 400

            # Create session
            session['user_logged_in'] = True
            session['user_email'] = email
            return jsonify({"message": "Signup successful"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 401

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        id_token = data.get('idToken')
        email = data.get('email')
        password = data.get('password')

        try:
            if id_token:
                # Google Login
                decoded_token = auth.verify_id_token(id_token)
                email = decoded_token['email']
            elif email and password:
                # Email/Password Login
                user = users_collection.find_one({"email": email})
                if not user or not check_password_hash(user['password'], password):
                    return jsonify({"error": "Invalid credentials"}), 401
            else:
                return jsonify({"error": "No authentication method provided"}), 400

            # Start a session
            session['user_logged_in'] = True
            session['user_email'] = email
            return jsonify({"message": "Login successful"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 401

    return render_template('login.html')

@app.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('login'))

@app.route('/home')
def home():
    # Check if user is logged in
    if 'user_logged_in' not in session or not session['user_logged_in']:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/send-survey', methods=['POST'])
def send_survey():
    data = request.json
    employee_email = data.get('email', '').strip()  # Get and sanitize email input

    if not employee_email:
        return jsonify({'error': 'Email is required'}), 400

    try:
        # Create the Google Form link (update with your actual form link)
        google_form_link = "https://forms.gle/sbFx3bZSXLREa1Uu8"

        # Compose the email
        msg = Message(
            subject='Employee Satisfaction Survey',
            sender=app.config['MAIL_USERNAME'],
            recipients=[employee_email]
        )
        msg.body = f"""
        Dear Employee,

        Please fill out this survey to provide feedback on your satisfaction and engagement:

        {google_form_link}

        Best regards,
        HR Team
        """

        # Send the email
        mail.send(msg)
        return jsonify({'message': 'Survey sent successfully!'}), 200

    except Exception as e:
        print(f"Error sending survey email: {e}")  # Log the error for debugging
        return jsonify({'error': f"Email sending error: {str(e)}"}), 500



@app.route('/verify-token', methods=['POST'])
def verify_token():
    id_token = request.json.get('idToken')
    try:
        # Verify the token with Firebase Admin
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token['uid']
        return jsonify({'status': 'success', 'uid': user_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 401

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        input_df = pd.DataFrame([data])
        
        # Convert numeric strings to float
        numeric_columns = ['satisfaction_level', 'last_evaluation', 'average_monthly_hours']
        for col in numeric_columns:
            if col in input_df.columns:
                input_df[col] = input_df[col].astype(float)
        
        # Convert salary to numeric if present
        if 'salary' in input_df.columns:
            input_df['salary'] = input_df['salary'].map({'low': 0, 'medium': 1, 'high': 2})
        
        # Handle department one-hot encoding
        if 'department' in input_df.columns:
            input_df = pd.get_dummies(input_df, columns=['department'])
        
        # Ensure all required columns exist
        for col in X_columns:
            if col not in input_df.columns:
                input_df[col] = 0
        
        # Select only the columns used during training
        input_df = input_df[X_columns]
        
        # Scale the features
        input_scaled = scaler.transform(input_df)
        
        # Make prediction
        prediction = rf_model.predict(input_scaled)[0]
        probabilities = rf_model.predict_proba(input_scaled)[0]
        
        # Handle probability calculation
        leaving_probability = float(probabilities[1]) if len(probabilities) > 1 else 0.0
        
        # Ensure probability is not NaN
        if pd.isna(leaving_probability):
            leaving_probability = 0.0
        
        recommendations = generate_recommendations(prediction, leaving_probability, data)
        
        return jsonify({
            'prediction': int(prediction),
            'probability': leaving_probability,
            'recommendations': recommendations,
            'employee_data': data
        })
    except Exception as e:
        print(f"Error in prediction: {str(e)}")  # For debugging
        return jsonify({'error': str(e)}), 500

def generate_recommendations(prediction, probability, employee_data):
    """
    Generate concise recommendations for employee retention.
    Limits output to 4 lines with complete sentences.
    """
    prompt = f"""
    Prediction: {'Likely to leave' if prediction == 1 else 'Likely to stay'}.
    Probability of leaving: {probability:.2f}.
    Key employee details: {employee_data}.

    Provide 3-4 actionable HR recommendations to improve retention or engagement in no more than 4 sentences.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an HR assistant providing concise retention advice."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=450,
            temperature=0.7
        )
        recommendations = response.choices[0].message.content.strip()
        return recommendations
    except Exception as e:
        return f"Error generating recommendations: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)
