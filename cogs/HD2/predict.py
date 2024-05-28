import datetime
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, r2_score

# Regression models
from sklearn.linear_model import LinearRegression, ElasticNet
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor

# Load your dataset (Assume your dataset is in a CSV file)
# Replace 'your_dataset.csv' with your actual dataset file

# List of regression models to use


data = pd.read_csv("statistics.csv")

# Extract features and target
X = data[
    [
        "player_count",
        "mp_mult",
        "wins_per_sec",
        "loss_per_sec",
        "decay_rate",
        "kills_per_sec",
        "deaths_per_sec",
    ]
]
Y = data["eps"]


#XE = data[["eps", "mp_mult",'wins_per_sec','loss_per_sec','kills_per_sec','deaths_per_sec']]
XE= data[['eps','mp_mult']]
YE = data["player_count"]
model = LinearRegression()
model.fit(X, Y)

players_needed_model=LinearRegression()
players_needed_model.fit(data[['eps','mp_mult']],YE)

def experiment_models():
    models = [
        ("Linear Regression", LinearRegression()),
        ("ElasticNet", ElasticNet()),
        ("Decision Tree", DecisionTreeRegressor(random_state=42)),
        ("Random Forest", RandomForestRegressor(n_estimators=1000)),
        (
            "Gradient Boosting",
            GradientBoostingRegressor(n_estimators=1000),
        ),
        ("KNeighbors", KNeighborsRegressor()),
        ("SVR", SVR(kernel='poly'))
    ]
    # Train and evaluate each model
    mse_results = {name: [] for name, _ in models}
    r2_results = {name: [] for name, _ in models}

    for i in range(10):
        # Split the data into training and testing sets
        XE_train, XE_test, YE_train, YE_test = train_test_split(XE, YE, test_size=0.1)

        for name, lmodel in models:
            lmodel.fit(XE_train, YE_train)
            y_pred = lmodel.predict(XE_test)

            mse = mean_squared_error(YE_test, y_pred)
            r2 = r2_score(YE_test, y_pred)
            mse_results[name].append(mse)
            r2_results[name].append(r2)
            print(i, name, mse, r2)

    for name in mse_results:
        avg_mse = np.mean(mse_results[name])
        avg_r2 = np.mean(r2_results[name])
        print(f"{name}:")
        print(f"  Average Mean Squared Error: {avg_mse:.4f}")
        print(f"  Average R^2 Score: {avg_r2:.4f}\n")

#experiment_models()

def make_prediction_for_eps(data_dict):

    prediction_features = {
        "timestamp": data_dict["timestamp"],
        "player_count": data_dict["player_count"],
        "mode": data_dict["mode"],
        "mp_mult": data_dict["mp_mult"],
        "wins_per_sec": data_dict["wins_per_sec"],
        "loss_per_sec": data_dict["loss_per_sec"],
        "decay_rate": data_dict["decay_rate"],
        "kills_per_sec": data_dict["kills_per_sec"],
        "deaths_per_sec": data_dict["deaths_per_sec"],
    }

    # Extract features for prediction
    features_for_prediction = pd.DataFrame([prediction_features])

    # Predict using the model
    eps_prediction = model.predict(
        features_for_prediction[
            [
                "player_count",
                "mp_mult",
                "wins_per_sec",
                "loss_per_sec",
                "decay_rate",
                "kills_per_sec",
                "deaths_per_sec",
            ]
        ]
    )

    # Add the prediction result to the schema
    print(eps_prediction)

    return eps_prediction[0]

def predict_needed_players(target_eps,mp_mult):

    prediction_features = {
        "eps": target_eps,
        "mp_mult": mp_mult,
    }

    # Extract features for prediction
    features_for_prediction = pd.DataFrame([prediction_features])

    needed=players_needed_model.predict(features_for_prediction[['eps','mp_mult']])
    return needed[0]