import datetime
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, r2_score

# Regression models
from sklearn.linear_model import LinearRegression, ElasticNet
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor

# Load your dataset (Assume your dataset is in a CSV file)
# Replace 'your_dataset.csv' with your actual dataset file

# List of regression models to use


data = pd.read_csv('statistics.csv')

# Extract features and target
X = data[['player_count', 'mp_mult', 'wins_per_sec', 'loss_per_sec', 'decay_rate', 'kills_per_sec', 'deaths_per_sec']]
Y = data['eps']


model=GradientBoostingRegressor(random_state=42,n_estimators=1000)
model.fit(X, Y)
def experiment_models():
    models = [
        ('Linear Regression', LinearRegression()),
        ('Elastinet',ElasticNet()),
        ('Decision Tree', DecisionTreeRegressor(random_state=42)),
        ('Random Forest', RandomForestRegressor(random_state=42,max_depth=50,n_estimators=1000)),
        ('Gradient Boosting', GradientBoostingRegressor(random_state=42,n_estimators=1000)),
    ]
    # Train and evaluate each model
    for i in range(1):
        # Split the data into training and testing sets
        
        for name, model in models:
            model.fit(X, Y)
            y_pred = model.predict(X)
            
            mse = mean_squared_error(Y, y_pred)
            r2 = r2_score(Y, y_pred)
            print(f'{name}:')
            print(f'  Mean Squared Error: {mse:.4f}')
            print(f'  R^2 Score: {r2:.4f}\n')

def make_prediction(data_dict):

    prediction_features = {
        'timestamp': data_dict['timestamp'],
        'player_count': data_dict['player_count'],
        'mode': data_dict['mode'],
        'mp_mult': data_dict['mp_mult'],
        'wins_per_sec': data_dict['wins_per_sec'],
        'loss_per_sec': data_dict['loss_per_sec'],
        'decay_rate': data_dict['decay_rate'],
        'kills_per_sec': data_dict['kills_per_sec'],
        'deaths_per_sec': data_dict['deaths_per_sec']
    }

    # Extract features for prediction
    features_for_prediction = pd.DataFrame([prediction_features])

    # Predict using the model
    eps_prediction = model.predict(features_for_prediction[['player_count', 'mp_mult', 'wins_per_sec', 'loss_per_sec', 'decay_rate', 'kills_per_sec', 'deaths_per_sec']])

    # Add the prediction result to the schema
    print(eps_prediction)
    prediction_features['eps'] = eps_prediction[0]

    return eps_prediction[0]