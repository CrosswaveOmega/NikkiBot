import datetime
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, r2_score

import matplotlib.pyplot as plt

# Regression models
from sklearn.linear_model import LinearRegression, ElasticNet
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from scipy import stats
from io import BytesIO
from PIL import Image

# Load your dataset (Assume your dataset is in a CSV file)
# Replace 'your_dataset.csv' with your actual dataset file

# List of regression models to use


data = pd.read_csv("statistics.csv")
data = data[
    (data["wins_per_sec"] >= 0)
    & (data["loss_per_sec"] >= 0)
    & (data["kills_per_sec"] >= 0)
    & (data["deaths_per_sec"] >= 0)
]


# Extract features and target
T = data["timestamp"]
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


# XE = data[["eps", "mp_mult",'wins_per_sec','loss_per_sec','kills_per_sec','deaths_per_sec']]
XE = data[["eps"]]
YE = data["player_count"]
model = LinearRegression()
model.fit(X, Y)

# Fit the linear regression model
players_needed_model = LinearRegression()
players_needed_model.fit(XE[["eps"]], YE)

XE2 = data[["player_count"]]
YE2 = data["eps"]
players_to_eps_model = LinearRegression()
players_to_eps_model.fit(XE2[["player_count"]], YE2)


# Predict values
predicted_eps = players_needed_model.predict(XE[["eps"]])

# Calculate the mean squared error
mse = mean_squared_error(YE, predicted_eps)
# print(f"Mean Squared Error: {mse}")


def experiment_models():
    models = [
        ("Linear Regression", LinearRegression()),
        ("ElasticNet", ElasticNet()),
        ("Decision Tree", DecisionTreeRegressor(random_state=42)),
        # ("Random Forest", RandomForestRegressor(n_estimators=1000)),
        # (            "Gradient Boosting",    GradientBoostingRegressor(n_estimators=1000),        ),
        ("KNeighbors", KNeighborsRegressor()),
    ]
    # Train and evaluate each model
    mse_results = {name: [] for name, _ in models}
    r2_results = {name: [] for name, _ in models}

    for i in range(2):
        # Split the data into training and testing sets
        XE_train, XE_test, YE_train, YE_test = train_test_split(XE, YE, test_size=0.1)

        for name, lmodel in models:
            lmodel.fit(XE_train, YE_train)
            y_pred = lmodel.predict(XE_test)

            mse = mean_squared_error(YE_test, y_pred)
            r2 = r2_score(YE_test, y_pred)
            mse_results[name].append(mse)
            r2_results[name].append(r2)
            # print(i, name, mse, r2)

    for name in mse_results:
        avg_mse = np.mean(mse_results[name])
        avg_r2 = np.mean(r2_results[name])
        # print(f"{name}:")
        # print(f"  Average Mean Squared Error: {avg_mse:.4f}")
        # print(f"  Average R^2 Score: {avg_r2:.4f}\n")


# experiment_models()


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
    # print(eps_prediction)

    return eps_prediction[0]


def predict_needed_players(target_eps, mp_mult):
    prediction_features = {
        "eps": target_eps,
        "mp_mult": mp_mult,
    }
    # Extract features for prediction
    features_for_prediction = pd.DataFrame([prediction_features])
    # X_new = features_for_prediction[["eps", "mp_mult"]]
    X_new = features_for_prediction[["eps"]]
    y_pred = players_needed_model.predict(X_new)
    needed = y_pred[0]

    y = YE
    # Calculate the standard error of the prediction
    X_with_intercept = np.hstack((np.ones((XE.shape[0], 1)), XE))
    X_new_with_intercept = np.hstack((np.ones((X_new.shape[0], 1)), X_new))
    se_of_prediction = np.sqrt(
        mse
        * (
            1
            + np.dot(
                np.dot(
                    X_new_with_intercept,
                    np.linalg.inv(np.dot(X_with_intercept.T, X_with_intercept)),
                ),
                X_new_with_intercept.T,
            )
        )
    )
    return needed, se_of_prediction


def predict_eps_for_players(players, mp_mult):
    prediction_features = {
        "player_count": players,
        "mp_mult": mp_mult,
    }
    # Extract features for prediction
    features_for_prediction = pd.DataFrame([prediction_features])
    # X_new = features_for_prediction[["eps", "mp_mult"]]
    X_new = features_for_prediction[["player_count"]]
    y_pred = players_to_eps_model.predict(X_new)
    needed = y_pred[0]

    # Calculate the standard error of the prediction
    X_with_intercept = np.hstack((np.ones((XE2.shape[0], 1)), XE2))
    X_new_with_intercept = np.hstack((np.ones((X_new.shape[0], 1)), X_new))
    se_of_prediction = np.sqrt(
        mse
        * (
            1
            + np.dot(
                np.dot(
                    X_new_with_intercept,
                    np.linalg.inv(np.dot(X_with_intercept.T, X_with_intercept)),
                ),
                X_new_with_intercept.T,
            )
        )
    )
    return needed, se_of_prediction


def make_graph():
    se = np.sqrt(mse)

    from matplotlib.font_manager import FontProperties

    terminal_font = FontProperties(
        fname=r"./assets/ChakraPetch-SemiBold.ttf"
    )  # Update the path to your font file

    # Calculate the confidence intervals
    confidence_level = 0.5
    degrees_of_freedom = len(XE) - 2
    t_value = stats.t.ppf((1 + confidence_level) / 2, degrees_of_freedom)

    # Prediction intervals
    predicted_std = np.std(predicted_eps)
    interval = t_value * predicted_std

    lower_bound = predicted_eps - interval
    upper_bound = predicted_eps + interval

    plt.figure(figsize=(20, 12), facecolor="black")
    # Create a colormap that transitions from blue to red
    colors = plt.colormaps["cool"](np.linspace(0, 1, len(YE)))

    # Adjust alpha value to make colors opaque by about 0.2
    colors[:, -1] = 0.5  # Setting the alpha channel to 0.2
    ax = plt.gca()
    maxy = 50 + np.max(YE)
    maxx = 50 + np.max(XE["eps"])
    # Set the background color to black
    ax.set_facecolor("black")

    plt.scatter(
        YE, XE["eps"], color=colors, label="Recorded influence Per Second", marker="+"
    )
    plt.plot(predicted_eps, XE["eps"], color="#FFE702", label="Regression Line")
    plt.plot(
        lower_bound,
        XE["eps"],
        color="#706CD6",
        alpha=0.2,
        label=f"{round(confidence_level*100.0,0)}% Confidence Interval",
    )
    plt.plot(
        upper_bound,
        XE["eps"],
        color="#706CD6",
        alpha=0.2,
        label=f"{round(confidence_level*100.0,0)}% Confidence Interval",
    )
    plt.xlim(left=0, right=maxy)  # Lower limit set to 0,0
    plt.ylim(bottom=0, top=maxx)

    plt.xticks(np.arange(0, maxy, 5000), color="white", fontproperties=terminal_font)

    plt.xticks(
        np.arange(0, maxy, 1000),
        minor=True,
    )
    plt.yticks(np.arange(0, maxx, 50), color="white", fontproperties=terminal_font)

    plt.yticks(np.arange(0, maxx, 10), minor=True)

    plt.grid(True, which="major", color="white", linestyle="--", linewidth=0.5)

    plt.grid(True, which="minor", color="#323232", linestyle=":", linewidth=0.5)

    # Plot confidenc
    plt.xlabel("Player Count", color="white", fontproperties=terminal_font)
    plt.ylabel("Influence per second", color="white", fontproperties=terminal_font)
    legend = ax.legend(
        facecolor="black",
        edgecolor="white",
        framealpha=1,
        loc="upper left",
        prop=terminal_font,
    )
    plt.setp(
        legend.get_texts(), color="white"
    )  # Set the color of the legend text to white

    # Customize the spines to be white
    ax.spines["bottom"].set_color("white")
    ax.spines["left"].set_color("white")
    ax.spines["top"].set_color("white")
    ax.spines["right"].set_color("white")

    plt.title(
        "Scatter plot of player count vs influence per second with confidence intervals",
        color="white",
        fontproperties=terminal_font,
    )

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)

    # Convert the plot to a PIL image
    image = Image.open(BytesIO(buffer.read()))

    # Close buffer
    buffer.close()

    # Save the image
    image.save("saveData/graph1.png")

    # Return the image
    return image


def make_graph2():

    from matplotlib.font_manager import FontProperties

    terminal_font = FontProperties(
        fname=r"./assets/ChakraPetch-SemiBold.ttf"
    )  # Update the path to your font file

    # Calculate the confidence intervals
    confidence_level = 0.5
    degrees_of_freedom = len(XE) - 2
    t_value = stats.t.ppf((1 + confidence_level) / 2, degrees_of_freedom)

    # Prediction intervals
    import random

    chosen_entry = X.sample(n=1, random_state=random.randint(0, 100)).iloc[0]
    # print(chosen_entry)

    predicted = []
    for i in np.linspace(0, 140, num=500):
        cho = chosen_entry
        cho["deaths_per_sec"] = i
        out = model.predict(pd.DataFrame([cho]))
        predicted.append(out)

    # predicted=model.predict(X)
    # print(predicted)
    predicted_std = np.std(predicted)
    interval = t_value * predicted_std

    lower_bound = predicted - interval
    upper_bound = predicted + interval

    plt.figure(figsize=(20, 12), facecolor="black")
    # Create a colormap that transitions from blue to red
    colors = plt.colormaps["cool"](np.linspace(0, 1, len(YE)))

    # Adjust alpha value to make colors opaque by about 0.2
    colors[:, -1] = 0.5  # Setting the alpha channel to 0.2
    ax = plt.gca()

    maxy = np.max(Y)
    maxx = np.max(X["deaths_per_sec"])
    # Set the background color to black
    ax.set_facecolor("black")

    plt.scatter(
        X["deaths_per_sec"],
        Y,
        color=colors,
        label="Recorded deaths Per Second",
        marker="+",
    )
    plt.scatter(
        np.linspace(0, 140, num=500),
        predicted,
        color="#FFE702",
        marker="+",
        label="Regression Line",
    )
    # plt.xlim(left=0,right=maxy)  # Lower limit set to 0,0
    # plt.ylim(bottom=0,top=maxx)

    plt.xticks(color="white", fontproperties=terminal_font)

    plt.yticks(color="white", fontproperties=terminal_font)

    plt.grid(True, which="major", color="white", linestyle="--", linewidth=0.5)

    plt.grid(True, which="minor", color="#323232", linestyle=":", linewidth=0.5)

    # Plot confidenc
    plt.xlabel("deaths per second", color="white", fontproperties=terminal_font)
    plt.ylabel("Influence per second", color="white", fontproperties=terminal_font)
    legend = ax.legend(
        facecolor="black",
        edgecolor="white",
        framealpha=1,
        loc="upper left",
        prop=terminal_font,
    )
    plt.setp(
        legend.get_texts(), color="white"
    )  # Set the color of the legend text to white

    # Customize the spines to be white
    ax.spines["bottom"].set_color("white")
    ax.spines["left"].set_color("white")
    ax.spines["top"].set_color("white")
    ax.spines["right"].set_color("white")

    plt.title("Graph", color="white", fontproperties=terminal_font)

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)

    # Convert the plot to a PIL image
    image = Image.open(BytesIO(buffer.read()))

    # Close buffer
    buffer.close()

    # Save the image
    image.save("saveData/graph2.png")

    # Return the image
    return image


def make_graph3():
    se = np.sqrt(mse)

    from matplotlib.font_manager import FontProperties

    terminal_font = FontProperties(
        fname=r"./assets/ChakraPetch-SemiBold.ttf"
    )  # Update the path to your font file

    plt.figure(figsize=(20, 12), facecolor="black")
    # Create a colormap that transitions from blue to red
    ax = plt.gca()
    ax.set_facecolor("black")

    maxy = np.max(T)
    maxx = max(
        X["deaths_per_sec"].max(),
        X["loss_per_sec"].max(),
        X["wins_per_sec"].max(),
        X["kills_per_sec"].max(),
    )
    plt.plot(T, X["deaths_per_sec"], label="Deaths per second")

    plt.plot(T, X["loss_per_sec"], label="loss per second")

    plt.plot(T, X["wins_per_sec"], label="wins per second")

    plt.plot(T, X["kills_per_sec"], label="deaths per second")

    plt.xlim(left=0, right=maxy)  # Lower limit set to 0,0
    plt.ylim(bottom=0, top=maxx)

    plt.xticks(np.arange(0, maxy, 5000), color="white", fontproperties=terminal_font)

    plt.xticks(
        np.arange(0, maxy, 1000),
        minor=True,
    )
    plt.yticks(np.arange(0, maxx, 50), color="white", fontproperties=terminal_font)

    plt.yticks(np.arange(0, maxx, 10), minor=True)

    plt.grid(True, which="major", color="white", linestyle="--", linewidth=0.5)

    plt.grid(True, which="minor", color="#323232", linestyle=":", linewidth=0.5)

    # Plot confidenc
    plt.xlabel("Timestamp", color="white", fontproperties=terminal_font)
    plt.ylabel("Influence per second", color="white", fontproperties=terminal_font)
    legend = ax.legend(
        facecolor="black",
        edgecolor="white",
        framealpha=1,
        loc="upper left",
        prop=terminal_font,
    )
    plt.setp(
        legend.get_texts(), color="white"
    )  # Set the color of the legend text to white

    # Customize the spines to be white
    ax.spines["bottom"].set_color("white")
    ax.spines["left"].set_color("white")
    ax.spines["top"].set_color("white")
    ax.spines["right"].set_color("white")

    plt.title(
        "Scatter plot of player count vs influence per second with confidence intervals",
        color="white",
        fontproperties=terminal_font,
    )

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)

    # Convert the plot to a PIL image
    image = Image.open(BytesIO(buffer.read()))

    # Close buffer
    buffer.close()

    # Save the image
    image.save("saveData/graph3.png")

    # Return the image
    return image


img = make_graph()
img2 = make_graph2()
